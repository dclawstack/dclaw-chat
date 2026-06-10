import pytest


@pytest.mark.asyncio
async def test_list_bots_seeds_marketplace(client):
    resp = await client.get("/api/v1/bots")
    assert resp.status_code == 200
    bots = resp.json()
    slugs = {b["slug"] for b in bots}
    assert {"github", "remind", "standup", "poll"}.issubset(slugs)


@pytest.mark.asyncio
async def test_list_bots_filter_by_category(client):
    resp = await client.get("/api/v1/bots", params={"category": "developer"})
    assert resp.status_code == 200
    bots = resp.json()
    assert len(bots) >= 1
    assert all(b["category"] == "developer" for b in bots)


@pytest.mark.asyncio
async def test_create_bot(client):
    resp = await client.post(
        "/api/v1/bots",
        json={
            "name": "My Bot",
            "slug": "my-bot",
            "description": "does things",
            "commands": [{"name": "hi", "description": "say hi"}],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "my-bot"
    assert data["installed"] is True
    assert data["commands"][0]["name"] == "hi"


@pytest.mark.asyncio
async def test_create_bot_duplicate_slug(client):
    await client.post("/api/v1/bots", json={"name": "A", "slug": "dup"})
    resp = await client.post("/api/v1/bots", json={"name": "B", "slug": "dup"})
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_bot(client):
    created = await client.post("/api/v1/bots", json={"name": "G", "slug": "g-bot"})
    bid = created.json()["id"]
    resp = await client.get(f"/api/v1/bots/{bid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == bid


@pytest.mark.asyncio
async def test_get_bot_not_found(client):
    resp = await client.get("/api/v1/bots/no-such-bot")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_bot(client):
    created = await client.post("/api/v1/bots", json={"name": "Old", "slug": "u-bot"})
    bid = created.json()["id"]
    resp = await client.put(
        f"/api/v1/bots/{bid}",
        json={"name": "New", "description": "updated", "enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New"
    assert data["description"] == "updated"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_bot_not_found(client):
    resp = await client.put("/api/v1/bots/ghost", json={"name": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_bot(client):
    created = await client.post("/api/v1/bots", json={"name": "D", "slug": "d-bot"})
    bid = created.json()["id"]
    resp = await client.delete(f"/api/v1/bots/{bid}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/bots/{bid}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_bot_not_found(client):
    resp = await client.delete("/api/v1/bots/ghost")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_install_and_uninstall_bot(client):
    created = await client.post("/api/v1/bots", json={"name": "I", "slug": "i-bot"})
    bid = created.json()["id"]
    uninstall = await client.post(f"/api/v1/bots/{bid}/uninstall")
    assert uninstall.status_code == 200
    assert uninstall.json()["installed"] is False
    install = await client.post(f"/api/v1/bots/{bid}/install")
    assert install.status_code == 200
    assert install.json()["installed"] is True


@pytest.mark.asyncio
async def test_install_not_found(client):
    assert (await client.post("/api/v1/bots/ghost/install")).status_code == 404
    assert (await client.post("/api/v1/bots/ghost/uninstall")).status_code == 404


@pytest.mark.asyncio
async def test_list_all_commands(client):
    await client.post(
        "/api/v1/bots",
        json={
            "name": "Cmd Bot",
            "slug": "cmd-bot",
            "commands": [{"name": "ping", "description": "pong"}],
        },
    )
    resp = await client.get("/api/v1/bots/commands/all")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()}
    assert "ping" in names


@pytest.mark.asyncio
async def test_run_command_not_a_slash(client):
    resp = await client.post(
        "/api/v1/bots/commands/execute",
        json={"content": "hello", "channel_id": "c1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_run_command_unknown(client):
    resp = await client.post(
        "/api/v1/bots/commands/execute",
        json={"content": "/definitelynotacommand", "channel_id": "c1"},
    )
    assert resp.status_code == 200
    assert "Unknown command" in resp.json()["reply"]
