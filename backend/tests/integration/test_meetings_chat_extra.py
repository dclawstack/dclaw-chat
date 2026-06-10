import pytest


@pytest.mark.asyncio
async def test_update_meeting_title_owned(client):
    created = await client.post("/api/v1/meetings", json={"title": "Orig"})
    mid = created.json()["id"]
    resp = await client.patch(f"/api/v1/meetings/{mid}", json={"title": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"


@pytest.mark.asyncio
async def test_update_meeting_title_not_found(client):
    resp = await client.patch("/api/v1/meetings/ghost", json={"title": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_meeting_not_found(client):
    resp = await client.delete("/api/v1/meetings/ghost")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_process_meeting_not_found(client):
    resp = await client.post("/api/v1/meetings/ghost/process", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_meeting_rejects_bad_type(client):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    resp = await client.post("/api/v1/meetings/upload", files=files)
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_chat_stream_success(client, monkeypatch):
    # Stub the Ollama stream so we don't hit the network.
    from app.services.ollama_service import OllamaService

    async def fake_stream(self, model, messages, temperature=0.7):
        for tok in ["Hel", "lo"]:
            yield tok

    monkeypatch.setattr(OllamaService, "chat_stream", fake_stream)

    resp = await client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": "stream-conv",
            "model": "gemma-4b",
            "messages": [{"role": "user", "content": "hello there"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "Hel" in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_chat_stream_handles_llm_error(client, monkeypatch):
    from app.services.ollama_service import OllamaService

    async def boom(self, model, messages, temperature=0.7):
        raise RuntimeError("ollama down")
        yield  # pragma: no cover

    monkeypatch.setattr(OllamaService, "chat_stream", boom)

    resp = await client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": "stream-err-conv",
            "model": "gemma-4b",
            "messages": [{"role": "user", "content": "hello there"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "error" in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_models_endpoint_returns_cloud_fallbacks(client, monkeypatch):
    from app.services.ollama_service import OllamaService

    async def fake_list(self):
        return []

    monkeypatch.setattr(OllamaService, "list_models", fake_list)

    resp = await client.get("/api/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    ids = {m["id"] for m in data}
    # cloud fallback models always listed even when ollama is unreachable
    assert "gpt-4o" in ids
    assert "deepseek-v4" in ids
