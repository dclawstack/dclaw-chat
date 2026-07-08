"""Enterprise SSO via Logto organizations (#35, ADR 0001).

The backend stores a workspace ↔ Logto organization mapping and enforces two
things: organization tokens never cross workspaces, and IdP-verified members
are JIT-provisioned on first touch. JWT verification itself is untouched.
"""
import pytest

from app.core.deps import CurrentUser, get_current_user
from app.main import app

from tests.integration.test_rbac_api import _switch_user, _workspace_with_member


class _as_sso_user:
    """Authenticated user whose token carries Logto organization claims."""

    def __init__(self, user_id: str, orgs: list[str]):
        self.user_id, self.orgs = user_id, orgs

    def __enter__(self):
        self.original = app.dependency_overrides[get_current_user]

        async def _override():
            return CurrentUser(
                user_id=self.user_id,
                email=f"{self.user_id}@corp.example",
                role="Member",
                organizations=self.orgs,
            )

        app.dependency_overrides[get_current_user] = _override

    def __exit__(self, *exc):
        app.dependency_overrides[get_current_user] = self.original


async def _sso_workspace(client, org_id="org-acme", name="SSO Co"):
    ws = await _workspace_with_member(client, name=name)
    r = await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/sso",
        json={"logto_organization_id": org_id},
    )
    assert r.status_code == 200
    return ws


@pytest.mark.asyncio
async def test_sso_settings_admin_only_and_audited(client):
    ws = await _workspace_with_member(client, name="SSO Settings Co")
    with _switch_user("member-1"):
        r = await client.get(f"/api/v1/workspaces/{ws['id']}/settings/sso")
        assert r.status_code == 403
        r = await client.put(
            f"/api/v1/workspaces/{ws['id']}/settings/sso",
            json={"logto_organization_id": "org-x"},
        )
        assert r.status_code == 403

    r = await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/sso",
        json={"logto_organization_id": "org-x"},
    )
    assert r.status_code == 200
    assert (await client.get(f"/api/v1/workspaces/{ws['id']}/settings/sso")).json() == {
        "logto_organization_id": "org-x"
    }
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "workspace.sso_configured" for e in audit)


@pytest.mark.asyncio
async def test_idp_user_lands_in_mapped_workspace_via_jit(client):
    ws = await _sso_workspace(client, org_id="org-acme", name="JIT Co")

    with _as_sso_user("okta-alice", ["org-acme"]):
        # First touch: not yet a member — the matching org claim provisions them.
        r = await client.get(f"/api/v1/workspaces/{ws['id']}")
        assert r.status_code == 200
        assert r.json()["my_role"] == "Member"

    members = (await client.get(f"/api/v1/workspaces/{ws['id']}/members")).json()
    assert any(m["user_id"] == "okta-alice" for m in members)
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "sso.jit_provisioned" for e in audit)


@pytest.mark.asyncio
async def test_foreign_org_token_cannot_cross_workspaces(client):
    ws_a = await _sso_workspace(client, org_id="org-acme", name="Acme WS")

    # Non-member with a token for a different organization: no access, no JIT
    with _as_sso_user("mallory", ["org-other"]):
        r = await client.get(f"/api/v1/workspaces/{ws_a['id']}")
        assert r.status_code == 403

    # Even an existing member is refused while presenting a foreign org token
    with _as_sso_user("member-1", ["org-other"]):
        r = await client.get(f"/api/v1/workspaces/{ws_a['id']}")
        assert r.status_code == 403

    members = (await client.get(f"/api/v1/workspaces/{ws_a['id']}/members")).json()
    assert all(m["user_id"] != "mallory" for m in members)


@pytest.mark.asyncio
async def test_non_org_tokens_keep_working_unchanged(client):
    """Password/JWT sessions without org claims still use plain membership."""
    ws = await _sso_workspace(client, org_id="org-acme", name="Mixed Auth Co")
    with _switch_user("member-1"):  # no organizations on the token
        r = await client.get(f"/api/v1/workspaces/{ws['id']}")
        assert r.status_code == 200
