"""Two-identity ownership and identity-spoof tests for bots (GAP v2 T2-04/T2-05).

These exercise the cross-user *state* the single-user suite never reaches:
user A creates a bot, user B (a different verified identity) must get 403 on
PUT/DELETE; and /commands/execute must derive identity from the verified
token, ignoring any client-supplied ``user_id``/``user_name`` in the body.
"""
import contextlib

import pytest
from sqlalchemy import select

import conftest
import app.api.v1.bots as bots_module
from app.core.deps import get_current_user, CurrentUser
from app.main import app
from app.models.channel import ChannelMessageORM


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


# ── T2-05 · owner-gated mutation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_foreign_user_cannot_update_or_delete_bot(client):
    created = await client.post(
        "/api/v1/bots", json={"name": "Mine", "slug": "owned-bot"}
    )
    assert created.status_code == 201
    bid = created.json()["id"]

    with _as_user("attacker-999"):
        updated = await client.put(
            f"/api/v1/bots/{bid}", json={"webhook_url": "https://evil.example/hook"}
        )
        deleted = await client.delete(f"/api/v1/bots/{bid}")
    assert updated.status_code == 403
    assert deleted.status_code == 403

    # Still intact (and un-repointed) for the owner
    mine = await client.get(f"/api/v1/bots/{bid}")
    assert mine.status_code == 200
    assert mine.json()["webhook_url"] is None


@pytest.mark.asyncio
async def test_foreign_user_cannot_disable_bot(client):
    created = await client.post(
        "/api/v1/bots", json={"name": "Enabled", "slug": "enabled-bot"}
    )
    bid = created.json()["id"]

    with _as_user("attacker-999"):
        resp = await client.put(f"/api/v1/bots/{bid}", json={"enabled": False})
    assert resp.status_code == 403
    assert (await client.get(f"/api/v1/bots/{bid}")).json()["enabled"] is True


@pytest.mark.asyncio
async def test_owner_can_still_mutate_own_bot(client):
    created = await client.post(
        "/api/v1/bots", json={"name": "Self", "slug": "self-bot"}
    )
    bid = created.json()["id"]

    updated = await client.put(f"/api/v1/bots/{bid}", json={"name": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    assert (await client.delete(f"/api/v1/bots/{bid}")).status_code == 204


@pytest.mark.asyncio
async def test_legacy_null_owner_bot_stays_fail_open(client):
    # Seed bots have created_by NULL → legacy-shared, any member may mutate
    listing = await client.get("/api/v1/bots")
    seed = next(b for b in listing.json() if b["slug"] == "github")

    with _as_user("some-other-user"):
        resp = await client.put(
            f"/api/v1/bots/{seed['id']}", json={"description": "shared edit"}
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_install_uninstall_stay_member_open(client):
    created = await client.post(
        "/api/v1/bots", json={"name": "Inst", "slug": "inst-bot"}
    )
    bid = created.json()["id"]

    with _as_user("not-the-owner"):
        uninstall = await client.post(f"/api/v1/bots/{bid}/uninstall")
        install = await client.post(f"/api/v1/bots/{bid}/install")
    assert uninstall.status_code == 200
    assert install.status_code == 200


# ── T2-04 · execute identity from token, not body ─────────────────────────────

@pytest.mark.asyncio
async def test_execute_command_ignores_forged_body_identity(
    client, db, monkeypatch
):
    await client.post(
        "/api/v1/bots",
        json={
            "name": "Echo Bot",
            "slug": "echo-bot",
            "commands": [{"name": "echo", "description": "echo back"}],
        },
    )

    captured: dict = {}

    async def _fake_execute(
        command, bot_commands_json, webhook_url, channel_id, user_id, user_name
    ):
        captured["user_id"] = user_id
        captured["user_name"] = user_name
        return "echoed"

    monkeypatch.setattr(bots_module, "execute_command", _fake_execute)
    # Route persists the bot reply via its own session factory; point it at
    # the test database.
    monkeypatch.setattr(bots_module, "async_session", conftest.TestingSessionLocal)

    resp = await client.post(
        "/api/v1/bots/commands/execute",
        json={
            "content": "/echo hi",
            "channel_id": "c1",
            "user_id": "victim-user",
            "user_name": "Victim",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "echoed"

    # Forwarded identity (webhook payload path) is the token identity
    assert captured["user_id"] == "test-user-123"
    assert captured["user_name"] == "test@dclawstack.io"

    # Persisted reply is authored by the bot, never the forged body identity
    rows = (
        (await db.execute(select(ChannelMessageORM))).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == "bot-echo-bot"
    assert "victim-user" not in {rows[0].user_id, rows[0].user_name}
