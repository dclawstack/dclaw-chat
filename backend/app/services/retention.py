"""Per-workspace data retention (#33).

Workspaces with ``retention_days`` set get messages (and their stored
attachment files) older than the window really deleted. Deletion runs in
small batches so a large workspace never holds a long transaction, and each
sweep writes one audit summary per workspace touched. Workspaces with no
policy (NULL) are never purged.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.channel import ChannelMessageORM, ChannelORM
from app.models.workspace import WorkspaceORM
from app.services import audit
from app.services.files import UPLOAD_DIR

log = get_logger(__name__)

PURGE_BATCH_SIZE = 500
SWEEP_INTERVAL_SECONDS = 3600


def _cutoff(retention_days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=retention_days)


def _delete_attachment_files(attachment_json: str | None) -> int:
    """Remove stored upload dirs referenced by a purged message."""
    if not attachment_json:
        return 0
    removed = 0
    try:
        attachments = json.loads(attachment_json)
    except ValueError:
        return 0
    for att in attachments if isinstance(attachments, list) else []:
        file_id = (att or {}).get("file_id")
        if not file_id:
            continue
        target = (UPLOAD_DIR / str(file_id)).resolve()
        # Containment check mirrors the file-serving guard.
        if target.parent != UPLOAD_DIR.resolve():
            continue
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed += 1
    return removed


async def purge_workspace(db: AsyncSession, workspace: WorkspaceORM) -> dict:
    """Delete messages older than the workspace's retention window."""
    assert workspace.retention_days is not None
    cutoff = _cutoff(workspace.retention_days)
    total_messages = 0
    total_files = 0

    while True:
        batch = (
            await db.execute(
                select(ChannelMessageORM.id, ChannelMessageORM.attachments)
                .join(ChannelORM, ChannelORM.id == ChannelMessageORM.channel_id)
                .where(
                    ChannelORM.workspace_id == workspace.id,
                    ChannelMessageORM.created_at < cutoff,
                )
                .limit(PURGE_BATCH_SIZE)
            )
        ).all()
        if not batch:
            break
        ids = [row[0] for row in batch]
        for _, attachments in batch:
            total_files += _delete_attachment_files(attachments)
        await db.execute(
            delete(ChannelMessageORM).where(ChannelMessageORM.id.in_(ids))
        )
        await db.commit()
        total_messages += len(ids)

    return {"messages": total_messages, "attachment_dirs": total_files}


async def run_sweep(db: AsyncSession) -> list[dict]:
    """Purge every workspace that opted into retention. Returns summaries."""
    workspaces = (
        await db.execute(
            select(WorkspaceORM).where(WorkspaceORM.retention_days.is_not(None))
        )
    ).scalars().all()
    summaries = []
    for ws in workspaces:
        counts = await purge_workspace(db, ws)
        if counts["messages"]:
            await audit.record(
                db, actor_id="system:retention", action="retention.purged",
                workspace_id=ws.id, target_type="workspace", target_id=ws.id,
                detail={
                    "retention_days": ws.retention_days,
                    "cutoff": _cutoff(ws.retention_days).isoformat(),
                    **counts,
                },
            )
        summaries.append({"workspace_id": ws.id, **counts})
    return summaries


async def sweep_loop() -> None:
    """Background task: periodic retention sweeps for the app's lifetime."""
    from app.core.database import async_session

    while True:
        try:
            async with async_session() as db:
                await run_sweep(db)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never kill the loop on one bad sweep
            log.warning("retention_sweep_failed", error=repr(exc))
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
