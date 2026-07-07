"""Workspace RBAC (#27): role × operation boundaries.

Roles: Owner (creator), Admin, Member (invite default), Guest.
Admin-only ops: invites, role changes, member removal, channel deletion.
Guests cannot see, join, or create workspace channels.
"""
import pytest

from app.core.deps import CurrentUser, get_current_user
from app.main import app


def _as(user_id: str):
    async def _override():
        return CurrentUser(user_id=user_id, email=f"{user_id}@x.io", role="Member")
    return _override


class _switch_user:
    """Temporarily swap the authenticated user."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def __enter__(self):
        self.original = app.dependency_overrides[get_current_user]
        app.dependency_overrides[get_current_user] = _as(self.user_id)

    def __exit__(self, *exc):
        app.dependency_overrides[get_current_user] = self.original


async def _workspace_with_member(client, name="RBAC Co", member_id="member-1"):
    """Owner (test-user-123) workspace with one accepted Member."""
    ws = (await client.post("/api/v1/workspaces", json={"name": name})).json()
    inv = (await client.post(
        f"/api/v1/workspaces/{ws['id']}/invites", json={"email": f"{member_id}@x.io"}
    )).json()
    with _switch_user(member_id):
        await client.post(f"/api/v1/workspaces/invites/{inv['token']}/accept")
    return ws


@pytest.mark.asyncio
async def test_my_role_reported_on_workspace(client):
    ws = await _workspace_with_member(client)
    r = await client.get(f"/api/v1/workspaces/{ws['id']}")
    assert r.json()["my_role"] == "Owner"
    with _switch_user("member-1"):
        r = await client.get(f"/api/v1/workspaces/{ws['id']}")
        assert r.json()["my_role"] == "Member"


@pytest.mark.asyncio
async def test_member_cannot_invite_change_roles_or_remove(client):
    ws = await _workspace_with_member(client)
    with _switch_user("member-1"):
        r = await client.post(f"/api/v1/workspaces/{ws['id']}/invites", json={"email": "x@x.io"})
        assert r.status_code == 403
        r = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/test-user-123", json={"role": "Member"}
        )
        assert r.status_code == 403
        r = await client.delete(f"/api/v1/workspaces/{ws['id']}/members/test-user-123")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_owner_changes_role_and_audit_records_it(client):
    ws = await _workspace_with_member(client)
    r = await client.patch(
        f"/api/v1/workspaces/{ws['id']}/members/member-1", json={"role": "Admin"}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "Admin"
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "member.role_changed" for e in audit)


@pytest.mark.asyncio
async def test_admin_cannot_touch_owner_role(client):
    ws = await _workspace_with_member(client)
    await client.patch(f"/api/v1/workspaces/{ws['id']}/members/member-1", json={"role": "Admin"})
    with _switch_user("member-1"):  # now Admin
        # Cannot demote the Owner
        r = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/test-user-123", json={"role": "Member"}
        )
        assert r.status_code == 403
        # Cannot grant Owner
        r = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/member-1", json={"role": "Owner"}
        )
        assert r.status_code == 403
        # Cannot remove the Owner
        r = await client.delete(f"/api/v1/workspaces/{ws['id']}/members/test-user-123")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_last_owner_cannot_demote_self(client):
    ws = await _workspace_with_member(client)
    r = await client.patch(
        f"/api/v1/workspaces/{ws['id']}/members/test-user-123", json={"role": "Member"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_removes_member_with_audit(client):
    ws = await _workspace_with_member(client, member_id="removable")
    r = await client.delete(f"/api/v1/workspaces/{ws['id']}/members/removable")
    assert r.status_code == 204
    members = (await client.get(f"/api/v1/workspaces/{ws['id']}/members")).json()
    assert all(m["user_id"] != "removable" for m in members)
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "member.removed" for e in audit)


@pytest.mark.asyncio
async def test_channel_delete_is_admin_only_and_audited(client):
    ws = await _workspace_with_member(client)
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": "doomed", "type": "public", "workspace_id": ws["id"]},
    )).json()

    with _switch_user("member-1"):
        r = await client.delete(f"/api/v1/messaging/channels/{ch['id']}")
        assert r.status_code == 403

    r = await client.delete(f"/api/v1/messaging/channels/{ch['id']}")
    assert r.status_code == 204
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "channel.deleted" for e in audit)


@pytest.mark.asyncio
async def test_legacy_channel_not_deletable(client):
    ch = (await client.post(
        "/api/v1/messaging/channels", json={"name": "legacy", "type": "public"}
    )).json()
    r = await client.delete(f"/api/v1/messaging/channels/{ch['id']}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_guest_cannot_see_join_or_post_in_workspace_channels(client):
    ws = await _workspace_with_member(client, member_id="guesty")
    await client.patch(f"/api/v1/workspaces/{ws['id']}/members/guesty", json={"role": "Guest"})
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": "private-ws", "type": "public", "workspace_id": ws["id"]},
    )).json()

    with _switch_user("guesty"):
        listing = (await client.get("/api/v1/messaging/channels")).json()
        assert all(c["id"] != ch["id"] for c in listing)
        r = await client.post(
            f"/api/v1/messaging/channels/{ch['id']}/messages", json={"content": "hi"}
        )
        assert r.status_code == 403
        r = await client.post(
            "/api/v1/messaging/channels",
            json={"name": "guest-made", "type": "public", "workspace_id": ws["id"]},
        )
        assert r.status_code == 403
