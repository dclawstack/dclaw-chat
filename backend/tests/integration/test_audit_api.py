"""Append-only audit log (#26): emission, authorization, immutability."""
import pytest

from app.core.deps import CurrentUser, get_current_user
from app.main import app


async def _other_user():
    return CurrentUser(user_id="member-456", email="member@dclawstack.io", role="Member")


@pytest.mark.asyncio
async def test_invite_lifecycle_emits_audit_events(client):
    ws = await client.post("/api/v1/workspaces", json={"name": "Audited Co"})
    ws_id = ws.json()["id"]

    inv = await client.post(f"/api/v1/workspaces/{ws_id}/invites", json={"email": "new@x.io"})
    assert inv.status_code == 201
    token = inv.json()["token"]

    # Another user accepts the invite
    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _other_user
    try:
        acc = await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        assert acc.status_code == 200
    finally:
        app.dependency_overrides[get_current_user] = original

    r = await client.get(f"/api/v1/workspaces/{ws_id}/audit")
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "invite.created" in actions
    assert "invite.accepted" in actions
    created = next(e for e in r.json() if e["action"] == "invite.created")
    assert created["actor_id"] == "test-user-123"
    assert created["target_id"] == token


@pytest.mark.asyncio
async def test_audit_list_filters_by_action(client):
    ws = await client.post("/api/v1/workspaces", json={"name": "Filter Co"})
    ws_id = ws.json()["id"]
    await client.post(f"/api/v1/workspaces/{ws_id}/invites", json={"email": "a@x.io"})

    r = await client.get(f"/api/v1/workspaces/{ws_id}/audit", params={"action": "invite.created"})
    assert r.status_code == 200
    assert r.json() and all(e["action"] == "invite.created" for e in r.json())

    r = await client.get(f"/api/v1/workspaces/{ws_id}/audit", params={"action": "nope.never"})
    assert r.json() == []


@pytest.mark.asyncio
async def test_audit_list_requires_admin_role(client):
    ws = await client.post("/api/v1/workspaces", json={"name": "Locked Co"})
    ws_id = ws.json()["id"]
    inv = await client.post(f"/api/v1/workspaces/{ws_id}/invites", json={"email": "m@x.io"})
    token = inv.json()["token"]

    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _other_user
    try:
        await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        # Plain Member must not read the audit trail
        r = await client.get(f"/api/v1/workspaces/{ws_id}/audit")
        assert r.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = original


@pytest.mark.asyncio
async def test_audit_rows_have_no_mutation_routes(client):
    """Append-only: the API surface offers no way to modify or delete events."""
    ws = await client.post("/api/v1/workspaces", json={"name": "Immutable Co"})
    ws_id = ws.json()["id"]
    for method in ("put", "patch", "delete"):
        r = await getattr(client, method)(f"/api/v1/workspaces/{ws_id}/audit")
        assert r.status_code == 405
        r = await getattr(client, method)(f"/api/v1/workspaces/{ws_id}/audit/some-id")
        assert r.status_code in (404, 405)
