"""Workspace message export / e-discovery (#32)."""
import pytest

from tests.integration.test_rbac_api import _switch_user, _workspace_with_member


async def _seed_channel(client, ws_id, name="exports"):
    ch = (await client.post(
        "/api/v1/messaging/channels",
        json={"name": name, "type": "public", "workspace_id": ws_id},
    )).json()
    parent = (await client.post(
        f"/api/v1/messaging/channels/{ch['id']}/messages",
        json={"content": "root message", "attachments": [
            {"file_id": "f1", "filename": "spec.pdf", "url": "/files/f1/spec.pdf"}
        ]},
    )).json()
    await client.post(
        f"/api/v1/messaging/channels/{ch['id']}/messages",
        json={"content": "threaded reply", "thread_parent_id": parent["id"]},
    )
    return ch, parent


@pytest.mark.asyncio
async def test_export_includes_threads_and_attachments(client):
    ws = await _workspace_with_member(client, name="Export Co")
    ch, parent = await _seed_channel(client, ws["id"])

    r = await client.get(f"/api/v1/workspaces/{ws['id']}/export")
    assert r.status_code == 200
    data = r.json()
    assert data["workspace_id"] == ws["id"]
    exported = next(c for c in data["channels"] if c["id"] == ch["id"])
    contents = {m["content"]: m for m in exported["messages"]}
    assert contents["threaded reply"]["thread_parent_id"] == parent["id"]
    assert contents["root message"]["attachments"][0]["filename"] == "spec.pdf"


@pytest.mark.asyncio
async def test_export_is_admin_only_and_audited(client):
    ws = await _workspace_with_member(client, name="Export Locked Co")
    await _seed_channel(client, ws["id"])

    with _switch_user("member-1"):
        r = await client.get(f"/api/v1/workspaces/{ws['id']}/export")
        assert r.status_code == 403

    r = await client.get(f"/api/v1/workspaces/{ws['id']}/export")
    assert r.status_code == 200
    audit = (await client.get(f"/api/v1/workspaces/{ws['id']}/audit")).json()
    exports = [e for e in audit if e["action"] == "workspace.exported"]
    assert exports and exports[0]["actor_id"] == "test-user-123"


@pytest.mark.asyncio
async def test_export_date_range_filters_messages(client):
    ws = await _workspace_with_member(client, name="Export Range Co")
    ch, _ = await _seed_channel(client, ws["id"])

    # Everything was created "now" — a window ending in the past is empty,
    # a wide window contains both messages.
    r = await client.get(
        f"/api/v1/workspaces/{ws['id']}/export",
        params={"end": "2000-01-01T00:00:00"},
    )
    exported = next(c for c in r.json()["channels"] if c["id"] == ch["id"])
    assert exported["messages"] == []

    r = await client.get(
        f"/api/v1/workspaces/{ws['id']}/export",
        params={"start": "2000-01-01T00:00:00", "end": "2100-01-01T00:00:00"},
    )
    exported = next(c for c in r.json()["channels"] if c["id"] == ch["id"])
    assert len(exported["messages"]) == 2


@pytest.mark.asyncio
async def test_export_single_channel_scope(client):
    ws = await _workspace_with_member(client, name="Export Scope Co")
    ch1, _ = await _seed_channel(client, ws["id"], name="one")
    ch2, _ = await _seed_channel(client, ws["id"], name="two")

    r = await client.get(
        f"/api/v1/workspaces/{ws['id']}/export", params={"channel_id": ch1["id"]}
    )
    ids = [c["id"] for c in r.json()["channels"]]
    assert ids == [ch1["id"]]

    r = await client.get(
        f"/api/v1/workspaces/{ws['id']}/export", params={"channel_id": "ghost"}
    )
    assert r.status_code == 404
