"""
In-process real-time event broker over WebSockets.

* Clients authenticate with their JWT in the first message (kept out of URLs/logs).
* Events are routed to a user (the complaint owner) and/or to all admins.
* publish() is thread-safe: sync FastAPI endpoints and background tasks run in a
  thread pool, so events are scheduled onto the server's event loop.
* Every event has a unique `event_id` and the complaint `version`
  (last_updated) so clients can drop duplicates and stale updates. The database
  stays the source of truth — clients re-fetch on reconnect.

Multi-worker: set REDIS_URL and every worker publishes to / listens on a Redis
pub/sub channel, so an event raised on one worker reaches sockets on all workers.
Without REDIS_URL the broker is in-process (correct for a single worker).
"""
import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"admin", "quality_manager"}


class InMemoryBus:
    """Shared bus for brokers in one process (tests / several brokers in one interpreter)."""

    def __init__(self):
        self._brokers: List["EventBroker"] = []

    def attach(self, broker: "EventBroker") -> None:
        self._brokers.append(broker)

    def publish(self, message: dict) -> None:
        for b in list(self._brokers):
            b.deliver_local(message["user_ids"], message["to_admins"], message["event"])


class RedisBus:
    """Redis pub/sub bus so every uvicorn worker fans out events to its own sockets.

    publish() is synchronous (called from request threads); listen() runs on each worker's
    event loop and reconnects with backoff if Redis drops."""
    CHANNEL = "zeroq:events"
    RECONNECT_MAX_SECONDS = 30

    def __init__(self, url: str):
        import redis
        self.url = url
        self._pub = redis.Redis.from_url(url, socket_timeout=2.0)
        self._brokers: List["EventBroker"] = []

    def attach(self, broker: "EventBroker") -> None:
        self._brokers.append(broker)

    def publish(self, message: dict) -> None:
        self._pub.publish(self.CHANNEL, json.dumps(message))

    async def listen(self) -> None:
        import redis.asyncio as aioredis
        delay = 1
        while True:
            try:
                client = aioredis.from_url(self.url)
                pubsub = client.pubsub()
                await pubsub.subscribe(self.CHANNEL)
                delay = 1
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    data = json.loads(msg["data"])
                    for b in self._brokers:
                        b.deliver_local(data["user_ids"], data["to_admins"], data["event"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Redis event bus disconnected (%s); retrying in %ss", exc, delay)
                await asyncio.sleep(delay)
                delay = min(self.RECONNECT_MAX_SECONDS, delay * 2)


class EventBroker:
    def __init__(self, bus=None):
        self._lock = threading.Lock()
        self._by_user: Dict[int, Set[WebSocket]] = {}
        self._admins: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.bus = bus
        if bus is not None:
            bus.attach(self)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    def register(self, ws: WebSocket, user_id: int, role: str) -> None:
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._by_user.setdefault(user_id, set()).add(ws)
            if role in ADMIN_ROLES:
                self._admins.add(ws)

    def unregister(self, ws: WebSocket, user_id: int) -> None:
        with self._lock:
            conns = self._by_user.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._by_user.pop(user_id, None)
            self._admins.discard(ws)

    def connection_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._by_user.values())

    def _targets(self, user_ids: Iterable[int], to_admins: bool) -> Set[WebSocket]:
        with self._lock:
            targets: Set[WebSocket] = set()
            for uid in user_ids:
                targets |= self._by_user.get(uid, set())
            if to_admins:
                targets |= self._admins
            return targets   # a set: a socket that is both owner and admin gets the event once

    async def _send(self, targets: Set[WebSocket], event: dict) -> None:
        for ws in list(targets):
            try:
                await ws.send_json(event)
            except Exception as exc:  # client went away mid-send
                logger.debug("Dropping websocket after send failure: %s", exc)

    def deliver_local(self, user_ids: Iterable[int], to_admins: bool, event: dict) -> None:
        """Send to this worker's matching sockets (thread-safe)."""
        targets = self._targets([u for u in user_ids if u is not None], to_admins)
        loop = self._loop
        if not targets or loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self._send(targets, event))
        else:
            asyncio.run_coroutine_threadsafe(self._send(targets, event), loop)

    def publish(self, event_type: str, payload: dict, user_ids: Iterable[int] = (),
                to_admins: bool = True) -> dict:
        event = {
            "event_id": uuid.uuid4().hex,
            "type": event_type,
            "emitted_at": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        ids = [u for u in user_ids if u is not None]
        if self.bus is None:
            self.deliver_local(ids, to_admins, event)
            return event
        try:
            self.bus.publish({"user_ids": ids, "to_admins": to_admins, "event": event})
        except Exception as exc:
            # Bus outage: at least clients connected to this worker still get the update;
            # others re-sync from the API when their socket reconnects.
            logger.error("Event bus publish failed (%s); delivering locally only", exc)
            self.deliver_local(ids, to_admins, event)
        return event


def _make_broker() -> "EventBroker":
    if settings.REDIS_URL:
        try:
            return EventBroker(bus=RedisBus(settings.REDIS_URL))
        except Exception as exc:
            if settings.is_production:
                raise
            logger.error("Redis bus unavailable (%s); using in-process broker", exc)
    return EventBroker()


broker = _make_broker()


def complaint_event_payload(complaint, extra: Optional[dict] = None) -> dict:
    payload = {
        "complaint_id": complaint.complaint_id,
        "status": complaint.status,
        "version": complaint.last_updated.isoformat() if complaint.last_updated else None,
    }
    if extra:
        payload.update(extra)
    return payload
