"""Per-workspace AI model policy (#30): admin-only settings, server-side
enforcement, filtered model listing."""
import pytest

from app.core.deps import CurrentUser, get_current_user
from app.main import app
from app.services.chat_service import ChatService

from tests.integration.test_rbac_api import _switch_user, _workspace_with_member


@pytest.mark.asyncio
async def test_policy_settings_are_admin_only(client):
    ws = await _workspace_with_member(client, name="Policy Co")
    with _switch_user("member-1"):
        r = await client.put(
            f"/api/v1/workspaces/{ws['id']}/settings/models",
            json={"local_only": True},
        )
        assert r.status_code == 403
        # members can still read the policy
        r = await client.get(f"/api/v1/workspaces/{ws['id']}/settings/models")
        assert r.status_code == 200

    r = await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/models", json={"local_only": True}
    )
    assert r.status_code == 200
    assert r.json()["local_only"] is True
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "workspace.model_policy_changed" for e in audit)


@pytest.mark.asyncio
async def test_local_only_blocks_cloud_model_server_side(client):
    ws = await _workspace_with_member(client, name="Local Co")
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/models", json={"local_only": True}
    )
    r = await client.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": "new",
            "messages": [{"role": "user", "content": "hi"}],
            "model": "gpt-4o",  # explicitly named cloud model
            "workspace_id": ws["id"],
        },
    )
    assert r.status_code == 403
    assert "local-only" in r.json()["detail"]


@pytest.mark.asyncio
async def test_allowlist_blocks_unlisted_model(client):
    ws = await _workspace_with_member(client, name="Allow Co")
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/models",
        json={"allowed_models": ["gemma-4b"]},
    )
    r = await client.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": "new",
            "messages": [{"role": "user", "content": "hi"}],
            "model": "claude-sonnet",
            "workspace_id": ws["id"],
        },
    )
    assert r.status_code == 403
    assert "not allowed" in r.json()["detail"]


@pytest.mark.asyncio
async def test_stream_endpoint_enforces_policy_too(client):
    ws = await _workspace_with_member(client, name="Stream Co")
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/models", json={"local_only": True}
    )
    r = await client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": "new",
            "messages": [{"role": "user", "content": "hi"}],
            "model": "gpt-4o",
            "workspace_id": ws["id"],
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_model_list_filtered_by_workspace_policy(client, monkeypatch):
    async def fake_list_models(self):
        return [
            {"id": "gemma-4b", "name": "Gemma 4B", "provider": "ollama"},
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openrouter"},
        ]

    monkeypatch.setattr(ChatService, "list_models", fake_list_models)

    ws = await _workspace_with_member(client, name="Filter Models Co")
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/models",
        json={"allowed_models": ["gemma-4b"]},
    )
    r = await client.get("/api/v1/models", params={"workspace_id": ws["id"]})
    assert [m["id"] for m in r.json()] == ["gemma-4b"]

    # Unfiltered listing (no workspace context) still shows everything
    r = await client.get("/api/v1/models")
    assert len(r.json()) == 2

    # Non-members cannot use a workspace filter as an oracle
    with _switch_user("stranger-99"):
        r = await client.get("/api/v1/models", params={"workspace_id": ws["id"]})
        assert r.status_code == 403
