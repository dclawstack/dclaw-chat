import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "dclaw-chat-backend"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_detailed(client):
    response = await client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert data["checks"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_list_models(client):
    response = await client.get("/api/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    assert data[0]["id"] == "gemma-4b"


@pytest.mark.asyncio
async def test_create_conversation(client):
    response = await client.post(
        "/api/v1/conversations",
        json={"title": "Test Conv", "model": "gemma-4b"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Conv"
    assert data["message_count"] == 0


@pytest.mark.asyncio
async def test_list_conversations(client):
    await client.post("/api/v1/conversations", json={"title": "A"})
    await client.post("/api/v1/conversations", json={"title": "B"})
    response = await client.get("/api/v1/conversations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Get Me"})
    cid = created.json()["id"]
    response = await client.get(f"/api/v1/conversations/{cid}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cid
    assert data["title"] == "Get Me"


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    response = await client.get("/api/v1/conversations/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Old"})
    cid = created.json()["id"]
    response = await client.patch(
        f"/api/v1/conversations/{cid}", json={"title": "New"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New"


@pytest.mark.asyncio
async def test_delete_conversation(client):
    created = await client.post("/api/v1/conversations", json={"title": "Delete"})
    cid = created.json()["id"]
    response = await client.delete(f"/api/v1/conversations/{cid}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/v1/conversations/{cid}")
    assert get_resp.status_code == 404
