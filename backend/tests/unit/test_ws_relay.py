"""Cross-replica WebSocket fan-out via Redis pub/sub (#23).

Two ConnectionManager instances stand in for two backend replicas. A fake
Redis bus routes published events to every manager's relay handler — the same
path a real pub/sub subscription drives — so these tests exercise origin
stamping, origin filtering, and remote delivery without a Redis server.
"""
import json

import pytest

from app.services.messaging import ConnectionManager

from tests.unit.test_messaging_manager import FakeWS


class FakeRedisBus:
    """Delivers published relay events to every attached manager, like Redis
    pub/sub delivers to every subscriber — including the publisher itself."""

    def __init__(self):
        self.managers: list[ConnectionManager] = []

    def attach(self, mgr: ConnectionManager) -> None:
        self.managers.append(mgr)
        mgr._redis = self  # broadcast/send_to publish through the bus

    async def publish(self, channel: str, data: str) -> None:
        event = json.loads(data)
        for mgr in self.managers:
            await mgr._handle_relay_event(event)


@pytest.mark.asyncio
async def test_broadcast_reaches_subscriber_on_other_replica():
    bus = FakeRedisBus()
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    bus.attach(replica_a)
    bus.attach(replica_b)

    remote = FakeWS()
    await replica_b.connect(remote, "user-on-b")
    replica_b.subscribe("room", "user-on-b")

    await replica_a.broadcast("room", {"type": "message", "content": "hi"})
    assert remote.sent == [{"type": "message", "content": "hi"}]


@pytest.mark.asyncio
async def test_own_echo_is_filtered_no_duplicate_delivery():
    """The publisher also receives its own event from Redis; origin filtering
    must prevent a second local delivery."""
    bus = FakeRedisBus()
    replica_a = ConnectionManager()
    bus.attach(replica_a)

    local = FakeWS()
    await replica_a.connect(local, "user-on-a")
    replica_a.subscribe("room", "user-on-a")

    await replica_a.broadcast("room", {"n": 1})
    assert local.sent == [{"n": 1}]  # exactly once


@pytest.mark.asyncio
async def test_exclude_user_respected_across_replicas():
    bus = FakeRedisBus()
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    bus.attach(replica_a)
    bus.attach(replica_b)

    excluded = FakeWS()
    other = FakeWS()
    await replica_b.connect(excluded, "sender")
    await replica_b.connect(other, "receiver")
    replica_b.subscribe("room", "sender")
    replica_b.subscribe("room", "receiver")

    await replica_a.broadcast("room", {"x": 1}, exclude_user="sender")
    assert excluded.sent == []
    assert other.sent == [{"x": 1}]


@pytest.mark.asyncio
async def test_typing_events_propagate_across_replicas():
    bus = FakeRedisBus()
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    bus.attach(replica_a)
    bus.attach(replica_b)

    watcher = FakeWS()
    await replica_b.connect(watcher, "watcher")
    replica_b.subscribe("room", "watcher")

    await replica_a.broadcast("room", {"type": "typing", "names": ["Alice"]})
    assert watcher.sent == [{"type": "typing", "names": ["Alice"]}]


@pytest.mark.asyncio
async def test_send_to_reaches_user_on_other_replica():
    bus = FakeRedisBus()
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    bus.attach(replica_a)
    bus.attach(replica_b)

    remote = FakeWS()
    await replica_b.connect(remote, "dm-target")

    await replica_a.send_to("dm-target", {"type": "dm", "content": "psst"})
    assert remote.sent == [{"type": "dm", "content": "psst"}]


@pytest.mark.asyncio
async def test_without_redis_behaves_single_process(monkeypatch):
    """REDIS_URL unset: no publish attempts, local delivery unchanged."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, "u1")
    mgr.subscribe("room", "u1")
    await mgr.broadcast("room", {"solo": True})
    assert ws.sent == [{"solo": True}]
    assert mgr._redis is None


@pytest.mark.asyncio
async def test_publish_failure_does_not_break_local_delivery():
    class ExplodingRedis:
        async def publish(self, channel, data):
            raise ConnectionError("redis down")

    mgr = ConnectionManager()
    mgr._redis = ExplodingRedis()
    ws = FakeWS()
    await mgr.connect(ws, "u1")
    mgr.subscribe("room", "u1")
    await mgr.broadcast("room", {"still": "works"})
    assert ws.sent == [{"still": "works"}]
