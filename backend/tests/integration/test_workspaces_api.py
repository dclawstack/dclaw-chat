"""Workspace membership + invite tests (v2.0 Phase 2 multi-tenant foundation).

Two-identity pattern: the conftest client is test-user-123; other identities
are swapped in via app.dependency_overrides (same pattern as
test_conversations_ownership.py).
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


@pytest.mark.asyncio
async def test_create_and_list_workspaces(client):
    created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Acme"
    assert body["created_by"] == "test-user-123"
    assert body["member_count"] == 1  # creator auto-added as Owner

    listing = await client.get("/api/v1/workspaces")
    assert listing.status_code == 200
    names = [w["name"] for w in listing.json()]
    assert "Acme" in names

    # Creator is an Owner member
    members = await client.get(f"/api/v1/workspaces/{body['id']}/members")
    assert members.status_code == 200
    assert members.json() == [
        {
            "user_id": "test-user-123",
            "role": "Owner",
            "created_at": members.json()[0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_non_member_gets_403_and_unknown_404(client):
    created = await client.post("/api/v1/workspaces", json={"name": "Private"})
    wid = created.json()["id"]

    with _as_user("outsider-1"):
        resp = await client.get(f"/api/v1/workspaces/{wid}")
        assert resp.status_code == 403
        resp = await client.get(f"/api/v1/workspaces/{wid}/members")
        assert resp.status_code == 403
        # Outsider's list must not contain the workspace
        listing = await client.get("/api/v1/workspaces")
        assert listing.json() == []

    missing = await client.get("/api/v1/workspaces/does-not-exist")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_invite_requires_owner_or_admin(client):
    created = await client.post("/api/v1/workspaces", json={"name": "Team"})
    wid = created.json()["id"]

    # Owner can invite
    invite = await client.post(
        f"/api/v1/workspaces/{wid}/invites", json={"email": "new@dclawstack.io"}
    )
    assert invite.status_code == 201
    token = invite.json()["token"]

    # Second identity joins as a plain Member...
    with _as_user("member-2"):
        accepted = await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        assert accepted.status_code == 200
        assert accepted.json() == {"workspace_id": wid, "role": "Member"}

        # ...and a plain Member cannot invite
        denied = await client.post(
            f"/api/v1/workspaces/{wid}/invites", json={"email": "x@dclawstack.io"}
        )
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_accept_flow_grants_membership(client):
    created = await client.post("/api/v1/workspaces", json={"name": "Onboard"})
    wid = created.json()["id"]

    invite = await client.post(
        f"/api/v1/workspaces/{wid}/invites", json={"email": "joiner@dclawstack.io"}
    )
    token = invite.json()["token"]

    with _as_user("joiner-7"):
        # Before accepting: 403
        before = await client.get(f"/api/v1/workspaces/{wid}")
        assert before.status_code == 403

        accepted = await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        assert accepted.status_code == 200

        # After accepting: member can read the workspace and appears in members
        after = await client.get(f"/api/v1/workspaces/{wid}")
        assert after.status_code == 200
        assert after.json()["member_count"] == 2

        # Accept is idempotent — no duplicate member row
        again = await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        assert again.status_code == 200
        assert again.json()["role"] == "Member"

    members = await client.get(f"/api/v1/workspaces/{wid}/members")
    user_ids = [m["user_id"] for m in members.json()]
    assert user_ids.count("joiner-7") == 1


@pytest.mark.asyncio
async def test_unknown_invite_token_404(client):
    resp = await client.post("/api/v1/workspaces/invites/no-such-token/accept")
    assert resp.status_code == 404
