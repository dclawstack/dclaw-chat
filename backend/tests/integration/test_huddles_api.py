import pytest


@pytest.mark.asyncio
async def test_create_huddle(client):
    response = await client.post("/api/v1/huddles", json={"name": "Design Sync"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Design Sync"
    assert data["status"] == "active"
    assert data["participants"] == []
    assert data["closed_at"] is None


@pytest.mark.asyncio
async def test_create_huddle_default_name(client):
    response = await client.post("/api/v1/huddles", json={})
    assert response.status_code == 201
    assert response.json()["name"] == "Huddle"


@pytest.mark.asyncio
async def test_list_huddles(client):
    await client.post("/api/v1/huddles", json={"name": "Room A"})
    await client.post("/api/v1/huddles", json={"name": "Room B"})
    response = await client.get("/api/v1/huddles")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_huddle(client):
    created = await client.post("/api/v1/huddles", json={"name": "Quick Chat"})
    rid = created.json()["id"]
    response = await client.get(f"/api/v1/huddles/{rid}")
    assert response.status_code == 200
    assert response.json()["id"] == rid


@pytest.mark.asyncio
async def test_get_huddle_not_found(client):
    response = await client.get("/api/v1/huddles/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_join_huddle(client):
    created = await client.post("/api/v1/huddles", json={"name": "Sprint Review"})
    rid = created.json()["id"]
    response = await client.post(
        f"/api/v1/huddles/{rid}/join", json={"display_name": "Alice"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Alice"
    assert data["room_id"] == rid
    assert data["is_speaking"] is False
    assert data["is_muted"] is False


@pytest.mark.asyncio
async def test_join_updates_participants_in_room(client):
    created = await client.post("/api/v1/huddles", json={"name": "Standup"})
    rid = created.json()["id"]
    await client.post(f"/api/v1/huddles/{rid}/join", json={"display_name": "Bob"})
    room = await client.get(f"/api/v1/huddles/{rid}")
    assert len(room.json()["participants"]) == 1


@pytest.mark.asyncio
async def test_leave_huddle(client):
    created = await client.post("/api/v1/huddles", json={"name": "Brainstorm"})
    rid = created.json()["id"]
    await client.post(f"/api/v1/huddles/{rid}/join", json={"display_name": "Carol"})
    leave_response = await client.post(f"/api/v1/huddles/{rid}/leave")
    assert leave_response.status_code == 204
    room = await client.get(f"/api/v1/huddles/{rid}")
    assert room.json()["participants"] == []


@pytest.mark.asyncio
async def test_update_speaking(client):
    created = await client.post("/api/v1/huddles", json={"name": "Collab"})
    rid = created.json()["id"]
    await client.post(f"/api/v1/huddles/{rid}/join", json={"display_name": "Dave"})
    response = await client.post(
        f"/api/v1/huddles/{rid}/speaking", json={"is_speaking": True}
    )
    assert response.status_code == 200
    assert response.json()["is_speaking"] is True


@pytest.mark.asyncio
async def test_update_speaking_not_participant(client):
    created = await client.post("/api/v1/huddles", json={"name": "Orphan"})
    rid = created.json()["id"]
    response = await client.post(
        f"/api/v1/huddles/{rid}/speaking", json={"is_speaking": True}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_close_huddle(client):
    created = await client.post("/api/v1/huddles", json={"name": "Closing Soon"})
    rid = created.json()["id"]
    response = await client.post(f"/api/v1/huddles/{rid}/close")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    assert data["closed_at"] is not None


@pytest.mark.asyncio
async def test_closed_huddles_excluded_from_list(client):
    active = await client.post("/api/v1/huddles", json={"name": "Active"})
    closed = await client.post("/api/v1/huddles", json={"name": "Closed"})
    await client.post(f"/api/v1/huddles/{closed.json()['id']}/close")
    response = await client.get("/api/v1/huddles")
    ids = [r["id"] for r in response.json()]
    assert active.json()["id"] in ids
    assert closed.json()["id"] not in ids


@pytest.mark.asyncio
async def test_delete_huddle(client):
    created = await client.post("/api/v1/huddles", json={"name": "To Delete"})
    rid = created.json()["id"]
    del_response = await client.delete(f"/api/v1/huddles/{rid}")
    assert del_response.status_code == 204
    get_response = await client.get(f"/api/v1/huddles/{rid}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_join_closed_huddle_returns_404(client):
    created = await client.post("/api/v1/huddles", json={"name": "Stale"})
    rid = created.json()["id"]
    await client.post(f"/api/v1/huddles/{rid}/close")
    response = await client.post(
        f"/api/v1/huddles/{rid}/join", json={"display_name": "Eve"}
    )
    assert response.status_code == 404
