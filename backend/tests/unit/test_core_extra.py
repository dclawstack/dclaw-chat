import pytest

from app.core import flags as flags_mod
from app.core import cache as cache_mod
from app.core.exceptions import (
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    BadRequestException,
    LLMException,
    DClawException,
)


# ── exceptions ─────────────────────────────────────────────────────────

def test_exception_status_codes_and_defaults():
    assert NotFoundException().status_code == 404
    assert UnauthorizedException().status_code == 401
    assert ForbiddenException().status_code == 403
    assert BadRequestException().status_code == 422
    assert LLMException().status_code == 502


def test_exception_custom_detail():
    exc = NotFoundException("missing widget")
    assert exc.detail == "missing widget"
    assert isinstance(exc, DClawException)


# ── flags ──────────────────────────────────────────────────────────────

def test_flags_is_enabled_returns_default_when_no_client(monkeypatch):
    monkeypatch.setattr(flags_mod, "_client", None)
    monkeypatch.setattr(flags_mod, "_init_failed", False)
    monkeypatch.setattr(flags_mod, "_FLAGSMITH_KEY", None)
    assert flags_mod.is_enabled("anything", default=True) is True
    assert flags_mod.is_enabled("anything", default=False) is False


def test_flags_get_client_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(flags_mod, "_client", None)
    monkeypatch.setattr(flags_mod, "_init_failed", False)
    monkeypatch.setattr(flags_mod, "_FLAGSMITH_KEY", None)
    assert flags_mod._get_client() is None


def test_flags_uses_client_result(monkeypatch):
    class FakeFlags:
        def is_feature_enabled(self, name):
            return name == "on-feature"

    class FakeClient:
        def get_environment_flags(self):
            return FakeFlags()

    monkeypatch.setattr(flags_mod, "_client", FakeClient())
    assert flags_mod.is_enabled("on-feature") is True
    assert flags_mod.is_enabled("off-feature") is False


def test_flags_client_error_falls_back(monkeypatch):
    class BadClient:
        def get_environment_flags(self):
            raise RuntimeError("network")

    monkeypatch.setattr(flags_mod, "_client", BadClient())
    assert flags_mod.is_enabled("x", default=True) is True


# ── cache ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_get_noop_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_mod, "_client", None)
    monkeypatch.setattr(cache_mod, "_init_failed", False)
    monkeypatch.setattr(cache_mod, "_REDIS_URL", None)
    assert await cache_mod.cache_get("key") is None


@pytest.mark.asyncio
async def test_cache_set_noop_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_mod, "_client", None)
    monkeypatch.setattr(cache_mod, "_init_failed", False)
    monkeypatch.setattr(cache_mod, "_REDIS_URL", None)
    assert await cache_mod.cache_set("key", "val") is False


@pytest.mark.asyncio
async def test_cache_get_uses_client(monkeypatch):
    class FakeRedis:
        async def get(self, key):
            return "cached!"

    monkeypatch.setattr(cache_mod, "_client", FakeRedis())
    assert await cache_mod.cache_get("k") == "cached!"


@pytest.mark.asyncio
async def test_cache_set_uses_client(monkeypatch):
    calls = {}

    class FakeRedis:
        async def set(self, key, value, ex=None):
            calls["args"] = (key, value, ex)

    monkeypatch.setattr(cache_mod, "_client", FakeRedis())
    ok = await cache_mod.cache_set("k", "v", ttl=99)
    assert ok is True
    assert calls["args"] == ("k", "v", 99)


@pytest.mark.asyncio
async def test_cache_get_error_returns_none(monkeypatch):
    class BadRedis:
        async def get(self, key):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache_mod, "_client", BadRedis())
    assert await cache_mod.cache_get("k") is None


@pytest.mark.asyncio
async def test_cache_set_error_returns_false(monkeypatch):
    class BadRedis:
        async def set(self, key, value, ex=None):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache_mod, "_client", BadRedis())
    assert await cache_mod.cache_set("k", "v") is False
