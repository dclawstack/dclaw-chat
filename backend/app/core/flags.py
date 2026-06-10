"""Minimal feature-flag wrapper around Flagsmith.

Reads FLAGSMITH_KEY from the environment. When unconfigured (or the client
or network is unavailable), ``is_enabled`` returns the supplied default so
callers never break. Import-safe even if flagsmith is not installed.
"""
from __future__ import annotations

import os

try:  # flagsmith is optional at runtime
    from flagsmith import Flagsmith
except Exception:  # pragma: no cover - flagsmith not installed
    Flagsmith = None  # type: ignore[assignment]

_FLAGSMITH_KEY = os.environ.get("FLAGSMITH_KEY")
_client = None
_init_failed = False


def _get_client():
    """Lazily build the Flagsmith client; returns None if unconfigured/unavailable."""
    global _client, _init_failed
    if _client is not None:
        return _client
    if _init_failed or Flagsmith is None or not _FLAGSMITH_KEY:
        return None
    try:
        _client = Flagsmith(environment_key=_FLAGSMITH_KEY)
    except Exception:
        _init_failed = True
        return None
    return _client


def is_enabled(name: str, default: bool = False) -> bool:
    """Return whether feature ``name`` is enabled, falling back to ``default``."""
    client = _get_client()
    if client is None:
        return default
    try:
        flags = client.get_environment_flags()
        return bool(flags.is_feature_enabled(name))
    except Exception:
        return default
