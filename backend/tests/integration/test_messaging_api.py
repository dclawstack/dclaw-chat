import pytest


@pytest.mark.asyncio
async def test_reply_count_increments_atomically(client):
    """Threaded replies bump the parent's reply_count (consensus #7).

    Uses the atomic SQL ``reply_count = reply_count + 1`` path; this asserts
    the counter is correct, which the previous read-modify-write also passed
    serially — the value of the fix is under concurrency, but this guards the
    happy path and the dropped existence-check.
    """
    ch = await client.post("/api/v1/messaging/channels", json={"name": "general", "type": "public"})
    channel_id = ch.json()["id"]

    parent = await client.post(
        f"/api/v1/messaging/channels/{channel_id}/messages",
        json={"content": "parent message"},
    )
    parent_id = parent.json()["id"]
    assert parent.json()["reply_count"] == 0

    for _ in range(3):
        r = await client.post(
            f"/api/v1/messaging/channels/{channel_id}/messages",
            json={"content": "reply", "thread_parent_id": parent_id},
        )
        assert r.status_code == 201

    listing = await client.get(f"/api/v1/messaging/channels/{channel_id}/messages")
    parent_row = next(m for m in listing.json() if m["id"] == parent_id)
    assert parent_row["reply_count"] == 3


@pytest.mark.asyncio
async def test_reply_to_missing_parent_is_noop(client):
    """An atomic update against a non-existent parent affects 0 rows, no error."""
    ch = await client.post("/api/v1/messaging/channels", json={"name": "g2", "type": "public"})
    channel_id = ch.json()["id"]
    r = await client.post(
        f"/api/v1/messaging/channels/{channel_id}/messages",
        json={"content": "orphan reply", "thread_parent_id": "does-not-exist"},
    )
    assert r.status_code == 201
