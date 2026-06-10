"""Regression tests for admin-endpoint authorization (T2-09) and the
require_role factory (T3-04).

The seed/clear endpoints wipe the entire database, so we assert the full set of
authorization *states*, not just the happy path:
  - admin disabled  -> 404 (invisible) for everyone, before auth is attempted
  - admin enabled, non-Owner caller -> 403
  - admin enabled, Owner caller      -> allowed
"""
import asyncio

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.deps import require_role, CurrentUser, get_current_user
from app.api.v1.admin import _require_admin_enabled
from app.main import app


# --- T3-04: require_role is a usable sync factory --------------------------

def test_require_role_factory_is_not_a_coroutine():
    checker = require_role("Owner")
    # An async-def factory would return a coroutine here and silently never gate.
    assert not asyncio.iscoroutine(checker)
    assert callable(checker)


@pytest.mark.asyncio
async def test_require_role_allows_owner_and_blocks_others():
    checker = require_role("Admin")
    owner = CurrentUser("1", "o@x.io", role="Owner")  # Owner always allowed
    assert await checker(user=owner) is owner

    member = CurrentUser("2", "m@x.io", role="Member")
    with pytest.raises(HTTPException) as exc:
        await checker(user=member)
    assert exc.value.status_code == 403


# --- T2-09: admin endpoints are gated --------------------------------------

def test_admin_flag_gate_is_404_when_disabled():
    # admin_enabled defaults to False.
    with pytest.raises(HTTPException) as exc:
        _require_admin_enabled()
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_seed_and_clear_are_404_when_admin_disabled(client):
    for path in ("/api/v1/admin/seed", "/api/v1/admin/clear"):
        resp = await client.post(path)
        assert resp.status_code == 404, path


@pytest.mark.asyncio
async def test_clear_forbidden_for_non_owner_when_enabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_enabled", True)

    original = app.dependency_overrides[get_current_user]

    async def _member():
        return CurrentUser(user_id="member-1", email="member@x.io", role="Member")

    app.dependency_overrides[get_current_user] = _member
    try:
        resp = await client.post("/api/v1/admin/clear")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = original


@pytest.mark.asyncio
async def test_clear_allowed_for_owner_when_enabled(client, monkeypatch):
    # conftest's default override is an Owner.
    monkeypatch.setattr(get_settings(), "admin_enabled", True)
    resp = await client.post("/api/v1/admin/clear")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"
