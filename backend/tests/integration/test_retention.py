"""Per-workspace data retention (#33): admin-only setting, boundary-exact
purge of messages and attachment files, no-policy workspaces untouched."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.channel import ChannelMessageORM, ChannelORM
from app.models.workspace import WorkspaceORM
from app.services import retention

from tests.integration.test_rbac_api import _switch_user, _workspace_with_member


async def _message_at(db, channel_id: str, content: str, at: datetime, attachments=None):
    msg = ChannelMessageORM(
        channel_id=channel_id,
        user_id="u",
        user_name="U",
        content=content,
        created_at=at,
        attachments=json.dumps(attachments) if attachments else None,
    )
    db.add(msg)
    await db.commit()
    return msg


@pytest.mark.asyncio
async def test_retention_setting_is_admin_only_and_audited(client):
    ws = await _workspace_with_member(client, name="Retention Co")
    with _switch_user("member-1"):
        r = await client.put(
            f"/api/v1/workspaces/{ws['id']}/settings/retention",
            json={"retention_days": 30},
        )
        assert r.status_code == 403

    r = await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/retention", json={"retention_days": 30}
    )
    assert r.status_code == 200
    assert r.json()["retention_days"] == 30
    audit_events = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    assert any(e["action"] == "workspace.retention_changed" for e in audit_events)


@pytest.mark.asyncio
async def test_purge_respects_boundary_and_deletes_files(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "UPLOAD_DIR", tmp_path)
    old_dir = tmp_path / "old-file"
    old_dir.mkdir()
    (old_dir / "doc.pdf").write_text("x")

    ws = await _workspace_with_member(client, name="Boundary Co")
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": "purgeable", "type": "public", "workspace_id": ws["id"]},
    )).json()
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/retention", json={"retention_days": 30}
    )

    now = datetime.now(timezone.utc)
    await _message_at(
        db, ch["id"], "just outside", now - timedelta(days=30, hours=1),
        attachments=[{"file_id": "old-file", "filename": "doc.pdf"}],
    )
    await _message_at(db, ch["id"], "just inside", now - timedelta(days=29, hours=23))

    workspace = await db.get(WorkspaceORM, ws["id"])
    counts = await retention.purge_workspace(db, workspace)
    assert counts["messages"] == 1
    assert counts["attachment_dirs"] == 1
    assert not old_dir.exists()

    remaining = (
        await db.execute(
            select(ChannelMessageORM.content).where(
                ChannelMessageORM.channel_id == ch["id"]
            )
        )
    ).scalars().all()
    assert "just inside" in remaining
    assert "just outside" not in remaining


@pytest.mark.asyncio
async def test_sweep_skips_workspaces_without_policy(client, db):
    ws = await _workspace_with_member(client, name="Forever Co")
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": "keep", "type": "public", "workspace_id": ws["id"]},
    )).json()
    ancient = datetime.now(timezone.utc) - timedelta(days=3650)
    await _message_at(db, ch["id"], "ancient but kept", ancient)

    summaries = await retention.run_sweep(db)
    assert all(s["workspace_id"] != ws["id"] for s in summaries)
    remaining = (
        await db.execute(
            select(ChannelMessageORM.id).where(ChannelMessageORM.channel_id == ch["id"])
        )
    ).scalars().all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_sweep_writes_audit_summary(client, db):
    ws = await _workspace_with_member(client, name="Sweep Audit Co")
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": "sweepme", "type": "public", "workspace_id": ws["id"]},
    )).json()
    await client.put(
        f"/api/v1/workspaces/{ws['id']}/settings/retention", json={"retention_days": 7}
    )
    await _message_at(
        db, ch["id"], "stale", datetime.now(timezone.utc) - timedelta(days=8)
    )

    await retention.run_sweep(db)
    audit_events = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    purges = [e for e in audit_events if e["action"] == "retention.purged"]
    assert purges
    detail = json.loads(purges[0]["detail"])
    assert detail["messages"] == 1
    assert purges[0]["actor_id"] == "system:retention"
