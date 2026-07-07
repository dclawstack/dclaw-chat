"""Per-workspace AI model policy (#30).

Two knobs on the workspace: an ``allowed_models`` allowlist (NULL = all
models permitted) and ``local_only`` (True = only on-box Ollama models may
run, regardless of what the client asks for). Enforcement is server-side —
a disallowed model is rejected before any provider call.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import WorkspaceORM
from app.services.model_router import ModelRouter


async def get_policy(
    db: AsyncSession, workspace_id: str
) -> tuple[Optional[list[str]], bool]:
    """Return (allowed_models or None, local_only) for the workspace."""
    ws = await db.get(WorkspaceORM, workspace_id)
    if ws is None:
        return None, False
    allowed = json.loads(ws.allowed_models) if ws.allowed_models else None
    return allowed, bool(ws.local_only)


async def enforce(db: AsyncSession, workspace_id: str, model: str) -> None:
    """403 unless *model* is permitted by the workspace policy."""
    allowed, local_only = await get_policy(db, workspace_id)
    if local_only and not ModelRouter._is_local(model):
        raise HTTPException(
            403,
            f"Workspace policy is local-only AI: model '{model}' would leave the box",
        )
    if allowed is not None and model not in allowed:
        raise HTTPException(403, f"Model '{model}' is not allowed in this workspace")


def filter_models(
    models: list[dict], allowed: Optional[list[str]], local_only: bool
) -> list[dict]:
    out = []
    for m in models:
        mid = m.get("id", "")
        if local_only and not ModelRouter._is_local(mid):
            continue
        if allowed is not None and mid not in allowed:
            continue
        out.append(m)
    return out
