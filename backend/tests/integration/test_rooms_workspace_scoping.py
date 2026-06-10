"""Call/huddle room workspace-scoping tests (GAP v2 T2-07, REST surface).

States probed: a non-member must not create rooms in, read, or join another
workspace's rooms; legacy NULL-workspace rooms stay open.
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


async def _make_workspace(client) -> str:
    ws = await client.post("/api/v1/workspaces", json={"name": "Acme"})
    assert ws.status_code == 201
    return ws.json()["id"]


@pytest.mark.asyncio
async def test_outsider_cannot_create_room_in_foreign_workspace(client):
    ws_id = await _make_workspace(client)

    with _as_user("outsider-1"):
        call = await client.post(
            "/api/v1/calls", json={"title": "sneak", "workspace_id": ws_id}
        )
        huddle = await client.post(
            "/api/v1/huddles", json={"name": "sneak", "workspace_id": ws_id}
        )
    assert call.status_code == 403
    assert huddle.status_code == 403


@pytest.mark.asyncio
async def test_outsider_cannot_get_or_join_workspace_rooms(client):
    ws_id = await _make_workspace(client)
    call = await client.post(
        "/api/v1/calls", json={"title": "standup", "workspace_id": ws_id}
    )
    assert call.json()["workspace_id"] == ws_id
    huddle = await client.post(
        "/api/v1/huddles", json={"name": "sync", "workspace_id": ws_id}
    )
    call_id, huddle_id = call.json()["id"], huddle.json()["id"]

    with _as_user("outsider-1"):
        get_call = await client.get(f"/api/v1/calls/{call_id}")
        get_huddle = await client.get(f"/api/v1/huddles/{huddle_id}")
        join = await client.post(
            f"/api/v1/huddles/{huddle_id}/join", json={"display_name": "Evil"}
        )
    assert get_call.status_code == 403
    assert get_huddle.status_code == 403
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_member_can_join_workspace_huddle(client):
    ws_id = await _make_workspace(client)
    inv = await client.post(
        f"/api/v1/workspaces/{ws_id}/invites", json={"email": "b@x.io"}
    )
    token = inv.json()["token"]
    huddle = await client.post(
        "/api/v1/huddles", json={"name": "sync", "workspace_id": ws_id}
    )
    huddle_id = huddle.json()["id"]

    with _as_user("member-b"):
        await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        join = await client.post(
            f"/api/v1/huddles/{huddle_id}/join", json={"display_name": "B"}
        )
    assert join.status_code == 200


@pytest.mark.asyncio
async def test_legacy_rooms_stay_open(client):
    call = await client.post("/api/v1/calls", json={"title": "open call"})
    huddle = await client.post("/api/v1/huddles", json={"name": "open huddle"})

    with _as_user("outsider-1"):
        get_call = await client.get(f"/api/v1/calls/{call.json()['id']}")
        join = await client.post(
            f"/api/v1/huddles/{huddle.json()['id']}/join",
            json={"display_name": "Guest"},
        )
    assert get_call.status_code == 200
    assert join.status_code == 200
