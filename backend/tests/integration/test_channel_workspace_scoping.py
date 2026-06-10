"""Channel workspace-scoping tests (GAP v2 T2-06 / T2-07).

States probed: a non-member of a workspace must not see, read, post to, or
upload into that workspace's channels; legacy NULL-workspace channels stay
open to any authenticated user.
"""
import contextlib

import pytest

from app.core.deps import get_current_user, CurrentUser
from app.main import app


@contextlib.contextmanager
def _as_user(user_id: str, email: str = "b@dclawstack.io"):
    async def _override():
        return CurrentUser(user_id=user_id, email=email, role="User")

    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _override
    try:
        yield
    finally:
        app.dependency_overrides[get_current_user] = original


async def _make_workspace_channel(client) -> tuple[str, str]:
    ws = await client.post("/api/v1/workspaces", json={"name": "Acme"})
    assert ws.status_code == 201
    ws_id = ws.json()["id"]
    ch = await client.post(
        "/api/v1/messaging/channels",
        json={"name": "private-eng", "workspace_id": ws_id},
    )
    assert ch.status_code == 201
    assert ch.json()["workspace_id"] == ws_id
    return ws_id, ch.json()["id"]


@pytest.mark.asyncio
async def test_non_member_cannot_create_channel_in_foreign_workspace(client):
    ws = await client.post("/api/v1/workspaces", json={"name": "Acme"})
    ws_id = ws.json()["id"]

    with _as_user("outsider-1"):
        resp = await client.post(
            "/api/v1/messaging/channels",
            json={"name": "sneak", "workspace_id": ws_id},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_workspace_channel_hidden_from_non_members(client):
    _, ch_id = await _make_workspace_channel(client)

    with _as_user("outsider-1"):
        listing = await client.get("/api/v1/messaging/channels")
    visible_ids = [c["id"] for c in listing.json()]
    assert ch_id not in visible_ids

    # Member still sees it
    listing = await client.get("/api/v1/messaging/channels")
    assert ch_id in [c["id"] for c in listing.json()]


@pytest.mark.asyncio
async def test_non_member_cannot_read_or_post(client):
    _, ch_id = await _make_workspace_channel(client)

    with _as_user("outsider-1"):
        read = await client.get(f"/api/v1/messaging/channels/{ch_id}/messages")
        post = await client.post(
            f"/api/v1/messaging/channels/{ch_id}/messages",
            json={"content": "hello"},
        )
        topics = await client.get(f"/api/v1/messaging/channels/{ch_id}/topics")
    assert read.status_code == 403
    assert post.status_code == 403
    assert topics.status_code == 403


@pytest.mark.asyncio
async def test_member_can_read_and_post(client):
    ws_id, ch_id = await _make_workspace_channel(client)

    # Invite a second user and accept
    inv = await client.post(
        f"/api/v1/workspaces/{ws_id}/invites", json={"email": "b@x.io"}
    )
    token = inv.json()["token"]
    with _as_user("member-b"):
        accept = await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        assert accept.status_code == 200
        post = await client.post(
            f"/api/v1/messaging/channels/{ch_id}/messages",
            json={"content": "hi from b"},
        )
        read = await client.get(f"/api/v1/messaging/channels/{ch_id}/messages")
    assert post.status_code == 201
    assert read.status_code == 200
    assert any(m["content"] == "hi from b" for m in read.json())


@pytest.mark.asyncio
async def test_legacy_null_workspace_channel_stays_open(client):
    ch = await client.post("/api/v1/messaging/channels", json={"name": "open"})
    ch_id = ch.json()["id"]

    with _as_user("outsider-1"):
        read = await client.get(f"/api/v1/messaging/channels/{ch_id}/messages")
        post = await client.post(
            f"/api/v1/messaging/channels/{ch_id}/messages",
            json={"content": "legacy ok"},
        )
    assert read.status_code == 200
    assert post.status_code == 201
