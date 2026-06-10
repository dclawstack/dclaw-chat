"""Two-identity ownership tests for conversations (GAP v2 T2-01/T2-02).

These exercise the cross-user *state* the single-user suite never reaches:
user A creates a conversation, user B (a different verified identity) must
get 403 on read/patch/delete and must not see it in their list, and chat
completions must refuse to write into A's conversation_id.
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
async def test_foreign_user_cannot_read_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Private"})
    cid = created.json()["id"]

    with _as_user("attacker-999"):
        resp = await client.get(f"/api/v1/conversations/{cid}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_foreign_user_cannot_patch_or_delete(client):
    created = await client.post("/api/v1/conversations", json={"title": "Private"})
    cid = created.json()["id"]

    with _as_user("attacker-999"):
        patched = await client.patch(
            f"/api/v1/conversations/{cid}", json={"title": "pwned"}
        )
        deleted = await client.delete(f"/api/v1/conversations/{cid}")
    assert patched.status_code == 403
    assert deleted.status_code == 403

    # Still intact for the owner
    mine = await client.get(f"/api/v1/conversations/{cid}")
    assert mine.status_code == 200
    assert mine.json()["title"] == "Private"


@pytest.mark.asyncio
async def test_list_is_owner_scoped(client):
    await client.post("/api/v1/conversations", json={"title": "Mine"})

    with _as_user("other-user-42"):
        listing = await client.get("/api/v1/conversations")
    assert listing.status_code == 200
    assert listing.json() == []


@pytest.mark.asyncio
async def test_chat_cannot_write_into_foreign_conversation(client, monkeypatch):
    created = await client.post("/api/v1/conversations", json={"title": "Target"})
    cid = created.json()["id"]

    async def _fake_chat(self, model, messages, temperature=0.7):
        return "ok"

    from app.services.ollama_service import OllamaService

    monkeypatch.setattr(OllamaService, "chat", _fake_chat)

    with _as_user("attacker-999"):
        resp = await client.post(
            "/api/v1/chat/completions",
            json={
                "conversation_id": cid,
                "messages": [{"role": "user", "content": "inject"}],
                "model": "gemma-4b",
            },
        )
    assert resp.status_code == 403

    # Stream must also refuse before emitting SSE
    with _as_user("attacker-999"):
        resp = await client.post(
            "/api/v1/chat/stream",
            json={
                "conversation_id": cid,
                "messages": [{"role": "user", "content": "inject"}],
                "model": "gemma-4b",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_binds_new_conversation_to_caller(client, monkeypatch):
    async def _fake_chat(self, model, messages, temperature=0.7):
        return "ok"

    from app.services.ollama_service import OllamaService

    monkeypatch.setattr(OllamaService, "chat", _fake_chat)

    with _as_user("user-b"):
        resp = await client.post(
            "/api/v1/chat/completions",
            json={
                "conversation_id": "conv-owned-by-b",
                "messages": [{"role": "user", "content": "hi"}],
                "model": "gemma-4b",
            },
        )
        assert resp.status_code == 200

    # The default test user (test-user-123) must not be able to touch it
    resp = await client.get("/api/v1/conversations/conv-owned-by-b")
    assert resp.status_code == 403
