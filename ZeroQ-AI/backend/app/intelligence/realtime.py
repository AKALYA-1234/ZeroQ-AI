"""
In-process real-time event broker over WebSockets.

* Clients authenticate with their JWT in the first message (kept out of URLs/logs).
* Events are routed to a user (the complaint owner) and/or to all admins.
* publish() is thread-safe: sync FastAPI endpoints and background tasks run in a
  thread pool, so events are scheduled onto the server's event loop.
* Every event has a unique `event_id` and the complaint `version`
  (last_updated) so clients can drop duplicates and stale updates. The database
  stays the source of truth — clients re-fetch on reconnect.

Limitation: a single-process broker. Multiple uvicorn workers would need a
shared bus (e.g. Redis pub/sub) behind the same publish() interface.
"""
import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, Iterable, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"admin", "quality_manager"}


class EventBroker:
    def __init__(self):
        self._lock = threading.Lock()
        self._by_user: Dict[int, Set[WebSocket]] = {}
        self._admins: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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
            return targets

    async def _send(self, targets: Set[WebSocket], event: dict) -> None:
        for ws in list(targets):
            try:
                await ws.send_json(event)
            except Exception as exc:  # client went away mid-send
                logger.debug("Dropping websocket after send failure: %s", exc)

    def publish(self, event_type: str, payload: dict, user_ids: Iterable[int] = (),
                to_admins: bool = True) -> dict:
        event = {
            "event_id": uuid.uuid4().hex,
            "type": event_type,
            "emitted_at": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        targets = self._targets([u for u in user_ids if u is not None], to_admins)
        loop = self._loop
        if not targets or loop is None or loop.is_closed():
            return event
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self._send(targets, event))
        else:
            asyncio.run_coroutine_threadsafe(self._send(targets, event), loop)
        return event


broker = EventBroker()


def complaint_event_payload(complaint, extra: Optional[dict] = None) -> dict:
    payload = {
        "complaint_id": complaint.complaint_id,
        "status": complaint.status,
        "version": complaint.last_updated.isoformat() if complaint.last_updated else None,
    }
    if extra:
        payload.update(extra)
    return payload
