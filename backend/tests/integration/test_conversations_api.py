import pytest


@pytest.mark.asyncio
async def test_create_and_list_conversations(client):
    resp = await client.post(
        "/api/v1/conversations", json={"title": "First", "model": "gemma-4b"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "First"
    assert data["message_count"] == 0

    listing = await client.get("/api/v1/conversations")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


@pytest.mark.asyncio
async def test_get_conversation_detail(client):
    created = await client.post("/api/v1/conversations", json={"title": "Detail"})
    cid = created.json()["id"]
    resp = await client.get(f"/api/v1/conversations/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cid
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    resp = await client.get("/api/v1/conversations/missing")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Old Title"})
    cid = created.json()["id"]
    resp = await client.patch(
        f"/api/v1/conversations/{cid}", json={"title": "Renamed"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"


@pytest.mark.asyncio
async def test_update_conversation_not_found(client):
    resp = await client.patch("/api/v1/conversations/missing", json={"title": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Bye"})
    cid = created.json()["id"]
    resp = await client.delete(f"/api/v1/conversations/{cid}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/conversations/{cid}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client):
    resp = await client.delete("/api/v1/conversations/missing")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["service"] == "dclaw-chat-backend"


@pytest.mark.asyncio
async def test_health_detailed(client):
    resp = await client.get("/api/v1/health/detailed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_list_models_endpoint(client, monkeypatch):
    from app.services.ollama_service import OllamaService

    async def fake_list(self):
        return [{"name": "gemma4:e2b", "size": 5_000_000_000}]

    monkeypatch.setattr(OllamaService, "list_models", fake_list)
    resp = await client.get("/api/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(m["provider"] == "local" for m in data)
