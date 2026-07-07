"""Audit-event emission (#26).

``record`` must never break the action being audited: failures are logged and
swallowed. Events are committed in their own transaction after the action's
own commit has succeeded.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditEventORM

log = get_logger(__name__)


async def record(
    db: AsyncSession,
    *,
    actor_id: str,
    action: str,
    workspace_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    try:
        db.add(AuditEventORM(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail) if detail else None,
        ))
        await db.commit()
    except Exception as exc:
        log.warning("audit_record_failed", action=action, error=repr(exc))
        try:
            await db.rollback()
        except Exception:
            pass
