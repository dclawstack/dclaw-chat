import pytest

from app.services.messaging import ConnectionManager


class FakeWS:
    def __init__(self, fail=False):
        self.accepted = False
        self.sent = []
        self.fail = fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_connect_and_online_count():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, "u1")
    assert ws.accepted is True
    assert mgr.online_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_everywhere():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, "u1")
    mgr.subscribe("chan", "u1")
    mgr.set_typing("chan", "u1", "Alice")
    mgr.disconnect("u1")
    assert mgr.online_count == 0
    assert "u1" not in mgr._subscriptions.get("chan", set())
    assert "Alice" not in mgr.get_typing_names("chan")


def test_subscribe_unsubscribe():
    mgr = ConnectionManager()
    mgr.subscribe("c", "u1")
    mgr.subscribe("c", "u2")
    assert mgr._subscriptions["c"] == {"u1", "u2"}
    mgr.unsubscribe("c", "u1")
    assert mgr._subscriptions["c"] == {"u2"}


def test_unsubscribe_unknown_channel_no_error():
    mgr = ConnectionManager()
    mgr.unsubscribe("ghost", "u1")  # should not raise


@pytest.mark.asyncio
async def test_broadcast_sends_to_subscribers_except_excluded():
    mgr = ConnectionManager()
    a, b, c = FakeWS(), FakeWS(), FakeWS()
    await mgr.connect(a, "a")
    await mgr.connect(b, "b")
    await mgr.connect(c, "c")
    for u in ("a", "b", "c"):
        mgr.subscribe("room", u)
    await mgr.broadcast("room", {"hello": 1}, exclude_user="a")
    assert a.sent == []
    assert b.sent == [{"hello": 1}]
    assert c.sent == [{"hello": 1}]


@pytest.mark.asyncio
async def test_broadcast_prunes_dead_connections():
    mgr = ConnectionManager()
    good = FakeWS()
    bad = FakeWS(fail=True)
    await mgr.connect(good, "good")
    await mgr.connect(bad, "bad")
    mgr.subscribe("room", "good")
    mgr.subscribe("room", "bad")
    await mgr.broadcast("room", {"x": 1})
    assert good.sent == [{"x": 1}]
    # the failing socket got disconnected
    assert mgr.online_count == 1
    assert "bad" not in mgr._connections


@pytest.mark.asyncio
async def test_send_to_existing_and_missing():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, "u1")
    await mgr.send_to("u1", {"k": "v"})
    assert ws.sent == [{"k": "v"}]
    # missing user is a no-op
    await mgr.send_to("ghost", {"k": "v"})


@pytest.mark.asyncio
async def test_send_to_dead_disconnects():
    mgr = ConnectionManager()
    bad = FakeWS(fail=True)
    await mgr.connect(bad, "bad")
    await mgr.send_to("bad", {"k": "v"})
    assert "bad" not in mgr._connections


def test_typing_indicators():
    mgr = ConnectionManager()
    mgr.set_typing("c", "u1", "Alice")
    mgr.set_typing("c", "u2", "Bob")
    names = mgr.get_typing_names("c")
    assert set(names) == {"Alice", "Bob"}
    mgr.clear_typing("c", "u1")
    assert mgr.get_typing_names("c") == ["Bob"]


def test_get_typing_names_empty_channel():
    mgr = ConnectionManager()
    assert mgr.get_typing_names("none") == []
