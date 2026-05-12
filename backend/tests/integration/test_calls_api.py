import pytest


@pytest.mark.asyncio
async def test_create_call_room(client):
    response = await client.post("/api/v1/calls", json={"title": "Team Standup"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Team Standup"
    assert data["status"] == "waiting"
    assert data["max_participants"] == 50
    assert data["recording_enabled"] is False
    assert data["ended_at"] is None


@pytest.mark.asyncio
async def test_create_call_room_caps_participants(client):
    response = await client.post("/api/v1/calls", json={"title": "Big Call", "max_participants": 200})
    assert response.status_code == 201
    assert response.json()["max_participants"] == 50


@pytest.mark.asyncio
async def test_list_call_rooms(client):
    await client.post("/api/v1/calls", json={"title": "Room A"})
    await client.post("/api/v1/calls", json={"title": "Room B"})
    response = await client.get("/api/v1/calls")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_call_room(client):
    created = await client.post("/api/v1/calls", json={"title": "Sync"})
    rid = created.json()["id"]
    response = await client.get(f"/api/v1/calls/{rid}")
    assert response.status_code == 200
    assert response.json()["id"] == rid


@pytest.mark.asyncio
async def test_get_call_room_not_found(client):
    response = await client.get("/api/v1/calls/nonexistent-room")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_end_call_room(client):
    created = await client.post("/api/v1/calls", json={"title": "To End"})
    rid = created.json()["id"]
    response = await client.post(f"/api/v1/calls/{rid}/end")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ended"
    assert data["ended_at"] is not None


@pytest.mark.asyncio
async def test_delete_call_room(client):
    created = await client.post("/api/v1/calls", json={"title": "To Delete"})
    rid = created.json()["id"]
    del_response = await client.delete(f"/api/v1/calls/{rid}")
    assert del_response.status_code == 204
    get_response = await client.get(f"/api/v1/calls/{rid}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_ended_rooms_excluded_from_list(client):
    active = await client.post("/api/v1/calls", json={"title": "Active"})
    ended = await client.post("/api/v1/calls", json={"title": "Ended"})
    await client.post(f"/api/v1/calls/{ended.json()['id']}/end")
    response = await client.get("/api/v1/calls")
    ids = [r["id"] for r in response.json()]
    assert active.json()["id"] in ids
    assert ended.json()["id"] not in ids
