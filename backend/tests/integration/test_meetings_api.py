import pytest


@pytest.mark.asyncio
async def test_create_meeting(client):
    response = await client.post("/api/v1/meetings", json={"title": "Sprint Planning"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Sprint Planning"
    assert data["status"] == "pending"
    assert data["transcript"] is None
    assert data["summary"] is None
    assert data["action_items"] is None


@pytest.mark.asyncio
async def test_list_meetings(client):
    await client.post("/api/v1/meetings", json={"title": "Meeting A"})
    await client.post("/api/v1/meetings", json={"title": "Meeting B"})
    response = await client.get("/api/v1/meetings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_meeting(client):
    created = await client.post("/api/v1/meetings", json={"title": "Standup"})
    mid = created.json()["id"]
    response = await client.get(f"/api/v1/meetings/{mid}")
    assert response.status_code == 200
    assert response.json()["id"] == mid


@pytest.mark.asyncio
async def test_get_meeting_not_found(client):
    response = await client.get("/api/v1/meetings/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_meeting_idor_blocked(client):
    """A user cannot read another user's meeting (consensus #6)."""
    from app.main import app
    from app.core.deps import get_current_user, CurrentUser

    # Created by the default test user (test-user-123).
    created = await client.post("/api/v1/meetings", json={"title": "Private"})
    mid = created.json()["id"]

    # Switch identity to a different user and attempt to read it.
    async def _other_user():
        return CurrentUser(user_id="attacker-999", email="evil@x.io", role="Owner")

    # Capture the live override so we can restore it without re-importing
    # conftest. A fresh `tests.conftest` import re-executes the module, building
    # a second in-memory engine and rebinding get_db to an empty DB, which makes
    # every later test fail with "no such table".
    original_override = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _other_user
    try:
        response = await client.get(f"/api/v1/meetings/{mid}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = original_override


@pytest.mark.asyncio
async def test_update_meeting_title(client):
    created = await client.post("/api/v1/meetings", json={"title": "Old Title"})
    mid = created.json()["id"]
    response = await client.patch(f"/api/v1/meetings/{mid}", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_delete_meeting(client):
    created = await client.post("/api/v1/meetings", json={"title": "To Delete"})
    mid = created.json()["id"]
    del_response = await client.delete(f"/api/v1/meetings/{mid}")
    assert del_response.status_code == 204
    get_response = await client.get(f"/api/v1/meetings/{mid}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_process_meeting_no_file(client):
    created = await client.post("/api/v1/meetings", json={"title": "No File"})
    mid = created.json()["id"]
    response = await client.post(f"/api/v1/meetings/{mid}/process", json={})
    assert response.status_code == 400
    assert "no audio file" in response.json()["detail"].lower()
