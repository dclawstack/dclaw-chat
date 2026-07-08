"""SCIM 2.0 provisioning (#31): token boundary, user lifecycle, revocation."""
import pytest

from app.services.messaging import manager as ws_manager

from tests.integration.test_rbac_api import _switch_user, _workspace_with_member
from tests.unit.test_messaging_manager import FakeWS


async def _scim_setup(client, name="SCIM Co"):
    ws = await _workspace_with_member(client, name=name)
    token = (await client.post(f"/api/v1/workspaces/{ws['id']}/scim/token")).json()["token"]
    return ws, token, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_token_issue_is_admin_only_and_audited(client):
    ws = await _workspace_with_member(client, name="SCIM Token Co")
    with _switch_user("member-1"):
        r = await client.post(f"/api/v1/workspaces/{ws['id']}/scim/token")
        assert r.status_code == 403
    r = await client.post(f"/api/v1/workspaces/{ws['id']}/scim/token")
    assert r.status_code == 200
    assert r.json()["token"]
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "scim.token_issued" for e in audit)


@pytest.mark.asyncio
async def test_scim_rejects_bad_or_missing_token(client):
    ws, token, headers = await _scim_setup(client, name="SCIM Auth Co")
    r = await client.get(f"/scim/v2/{ws['id']}/Users")
    assert r.status_code == 401
    r = await client.get(
        f"/scim/v2/{ws['id']}/Users", headers={"Authorization": "Bearer wrong"}
    )
    assert r.status_code == 401
    # Rotation invalidates the old token
    new_token = (await client.post(f"/api/v1/workspaces/{ws['id']}/scim/token")).json()["token"]
    r = await client.get(f"/scim/v2/{ws['id']}/Users", headers=headers)
    assert r.status_code == 401
    r = await client.get(
        f"/scim/v2/{ws['id']}/Users", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_scim_provision_creates_member(client):
    ws, _, headers = await _scim_setup(client, name="SCIM Provision Co")
    r = await client.post(
        f"/scim/v2/{ws['id']}/Users",
        json={"schemas": [], "userName": "okta-user-1", "active": True},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["id"] == "okta-user-1"

    members = (await client.get(f"/api/v1/workspaces/{ws['id']}/members")).json()
    assert any(m["user_id"] == "okta-user-1" and m["role"] == "Member" for m in members)

    # Filter probe (Okta-style) finds them
    r = await client.get(
        f"/scim/v2/{ws['id']}/Users",
        params={"filter": 'userName eq "okta-user-1"'},
        headers=headers,
    )
    assert r.json()["totalResults"] == 1
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "scim.provisioned" for e in audit)


@pytest.mark.asyncio
async def test_scim_deactivate_revokes_access_and_closes_ws(client):
    ws, _, headers = await _scim_setup(client, name="SCIM Revoke Co")
    await client.post(
        f"/scim/v2/{ws['id']}/Users",
        json={"userName": "leaver", "active": True},
        headers=headers,
    )

    # 'leaver' can read the workspace while provisioned…
    with _switch_user("leaver"):
        r = await client.get(f"/api/v1/workspaces/{ws['id']}")
        assert r.status_code == 200

    # …and has a live WS connection
    fake_ws = FakeWS()
    fake_ws.closed = False

    async def fake_close(code=1000):
        fake_ws.closed = True

    fake_ws.close = fake_close
    await ws_manager.connect(fake_ws, "leaver")

    # IdP deactivates (Entra-style PATCH)
    r = await client.patch(
        f"/scim/v2/{ws['id']}/Users/leaver",
        json={"Operations": [{"op": "replace", "value": {"active": False}}]},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["active"] is False

    assert fake_ws.closed is True
    assert "leaver" not in ws_manager._connections

    with _switch_user("leaver"):
        r = await client.get(f"/api/v1/workspaces/{ws['id']}")
        assert r.status_code == 403

    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "scim.deprovisioned" for e in audit)


@pytest.mark.asyncio
async def test_scim_delete_removes_member(client):
    ws, _, headers = await _scim_setup(client, name="SCIM Delete Co")
    await client.post(
        f"/scim/v2/{ws['id']}/Users", json={"userName": "temp"}, headers=headers
    )
    r = await client.delete(f"/scim/v2/{ws['id']}/Users/temp", headers=headers)
    assert r.status_code == 204
    members = (await client.get(f"/api/v1/workspaces/{ws['id']}/members")).json()
    assert all(m["user_id"] != "temp" for m in members)


@pytest.mark.asyncio
async def test_scim_disabled_workspace_is_404(client):
    ws = await _workspace_with_member(client, name="No SCIM Co")
    r = await client.get(
        f"/scim/v2/{ws['id']}/Users", headers={"Authorization": "Bearer whatever"}
    )
    assert r.status_code == 404
