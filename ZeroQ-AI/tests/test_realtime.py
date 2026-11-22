"""Real-time broker: cross-worker fan-out via a shared bus, targeting, and socket lifecycle."""
import asyncio
import time
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.intelligence.realtime import EventBroker, InMemoryBus


class _Socket:
    def __init__(self):
        self.received = []

    async def send_json(self, data):
        self.received.append(data)


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


def test_event_published_on_one_worker_reaches_socket_on_another():
    async def scenario():
        bus = InMemoryBus()
        worker_a, worker_b = EventBroker(bus=bus), EventBroker(bus=bus)
        customer, admin, stranger = _Socket(), _Socket(), _Socket()
        worker_b.register(customer, user_id=7, role="customer")
        worker_b.register(admin, user_id=1, role="admin")
        worker_b.register(stranger, user_id=8, role="customer")
        event = worker_a.publish("complaint.resolved", {"complaint_id": "CMP1"}, user_ids=[7], to_admins=True)
        await _settle()
        assert [e["event_id"] for e in customer.received] == [event["event_id"]]
        assert [e["event_id"] for e in admin.received] == [event["event_id"]]
        assert stranger.received == []            # other customers never receive it
    asyncio.run(scenario())


def test_each_socket_gets_an_event_once_even_if_owner_is_admin():
    async def scenario():
        broker = EventBroker()
        sock = _Socket()
        broker.register(sock, user_id=1, role="admin")
        broker.publish("complaint.updated", {"complaint_id": "CMP2"}, user_ids=[1], to_admins=True)
        await _settle()
        assert len(sock.received) == 1
    asyncio.run(scenario())


def test_many_concurrent_connections_all_receive_admin_event():
    async def scenario():
        broker = EventBroker()
        sockets = [_Socket() for _ in range(200)]
        for i, s in enumerate(sockets):
            broker.register(s, user_id=1000 + i, role="admin")
        broker.publish("complaint.created", {"complaint_id": "CMP3"}, to_admins=True)
        await _settle()
        assert all(len(s.received) == 1 for s in sockets)
        for i, s in enumerate(sockets):
            broker.unregister(s, 1000 + i)
        assert broker.connection_count() == 0
    asyncio.run(scenario())


def test_socket_is_closed_when_token_expires(env):
    token = create_access_token({"sub": str(env["ids"]["cust"]), "role": "customer"},
                                expires_delta=timedelta(seconds=2))
    started = time.monotonic()
    with pytest.raises(WebSocketDisconnect) as exc:
        with env["client"].websocket_connect("/api/ws") as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json()["type"] == "connected"
            ws.receive_json()          # blocks until the server closes at expiry
    assert exc.value.code == 4401
    assert time.monotonic() - started < 10
