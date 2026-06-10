"""Shared slowapi rate limiter.

Defined in its own module so route handlers (e.g. auth/admin endpoints) can
import the same ``limiter`` instance that ``app.main`` registers on the app
state, avoiding circular imports.

Storage: when ``REDIS_URL`` is set the counters live in Redis, so the limit is
shared across all uvicorn workers and pods (and survives restarts). Without it,
slowapi falls back to per-process in-memory storage — fine for single-worker
dev, but the effective limit is then ``limit × workers`` and resets on restart.

Client IP: ``X-Forwarded-For`` is trusted **only** when ``TRUST_PROXY_HEADERS``
is enabled (i.e. the app sits behind a reverse proxy/ingress that sets it).
Trusting it otherwise would let any client spoof their source IP and evade the
limit; not trusting it behind a proxy would bucket every client under the proxy
IP. Set it to match the deployment.
"""
from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

logger = logging.getLogger(__name__)

_TRUST_PROXY = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")
_REDIS_URL = os.environ.get("REDIS_URL")


def _client_ip(request: Request) -> str:
    """Resolve the client IP, honouring X-Forwarded-For only behind a trusted proxy."""
    if _TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Left-most entry is the original client (proxies append on the right).
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    if _REDIS_URL:
        try:
            return Limiter(
                key_func=_client_ip,
                default_limits=["200/minute"],
                storage_uri=_REDIS_URL,
            )
        except Exception:  # pragma: no cover - redis backend unavailable
            logger.warning(
                "Rate limiter: REDIS_URL set but Redis storage unavailable; "
                "falling back to in-memory (per-process) limits."
            )
    return Limiter(key_func=_client_ip, default_limits=["200/minute"])


limiter = _build_limiter()
