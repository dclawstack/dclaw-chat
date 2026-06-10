"""Async Redis cache helper.

No-op when REDIS_URL is unset or Redis is unreachable, so the app keeps
working without a cache. Import-safe even if redis is not installed.
"""
from __future__ import annotations

import os
from typing import Optional

try:  # redis is optional at runtime
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover - redis not installed
    aioredis = None  # type: ignore[assignment]

_REDIS_URL = os.environ.get("REDIS_URL")
_client = None
_init_failed = False


def _get_client():
    """Lazily build the Redis client; returns None if unconfigured/unavailable."""
    global _client, _init_failed
    if _client is not None:
        return _client
    if _init_failed or aioredis is None or not _REDIS_URL:
        return None
    try:
        _client = aioredis.from_url(_REDIS_URL, decode_responses=True)
    except Exception:
        _init_failed = True
        return None
    return _client


async def cache_get(key: str) -> Optional[str]:
    """Return the cached value for ``key`` or None (no-op if cache is down)."""
    client = _get_client()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception:
        return None


async def cache_set(key: str, value: str, ttl: int = 300) -> bool:
    """Set ``key`` to ``value`` with a TTL in seconds. Returns success (no-op safe)."""
    client = _get_client()
    if client is None:
        return False
    try:
        await client.set(key, value, ex=ttl)
        return True
    except Exception:
        return False
