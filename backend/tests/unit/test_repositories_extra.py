import json

import pytest

from app.repositories.huddle_repo import HuddleRepository
from app.repositories.meeting_repo import MeetingRepository


# ── HuddleRepository ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_huddle_create_and_get(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Standup", created_by="u1")
    assert room.name == "Standup"
    assert room.status == "active"
    found = await repo.get_room(room.id)
    assert found is not None and found.id == room.id


@pytest.mark.asyncio
async def test_huddle_get_missing(db):
    repo = HuddleRepository(db)
    assert await repo.get_room("nope") is None


@pytest.mark.asyncio
async def test_huddle_list_active_excludes_closed(db):
    repo = HuddleRepository(db)
    active = await repo.create_room("Active")
    closed = await repo.create_room("Closed")
    await repo.close_room(closed)
    rooms = await repo.list_active()
    ids = [r.id for r in rooms]
    assert active.id in ids
    assert closed.id not in ids


@pytest.mark.asyncio
async def test_huddle_close_sets_timestamp(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Close Me")
    closed = await repo.close_room(room)
    assert closed.status == "closed"
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_huddle_delete(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Del")
    await repo.delete_room(room)
    assert await repo.get_room(room.id) is None


@pytest.mark.asyncio
async def test_huddle_join_and_get_participant(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Join")
    p = await repo.join_room(room.id, "u1", "Alice")
    assert p.display_name == "Alice"
    assert p.is_speaking is False
    fetched = await repo.get_participant(room.id, "u1")
    assert fetched is not None and fetched.id == p.id


@pytest.mark.asyncio
async def test_huddle_join_idempotent(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Join2")
    first = await repo.join_room(room.id, "u1", "Alice")
    second = await repo.join_room(room.id, "u1", "Alice")
    assert first.id == second.id  # same participant reused


@pytest.mark.asyncio
async def test_huddle_leave(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Leave")
    await repo.join_room(room.id, "u1", "Alice")
    assert await repo.leave_room(room.id, "u1") is True
    assert await repo.get_participant(room.id, "u1") is None


@pytest.mark.asyncio
async def test_huddle_leave_not_present(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Leave2")
    assert await repo.leave_room(room.id, "ghost") is False


@pytest.mark.asyncio
async def test_huddle_update_speaking(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Speak")
    await repo.join_room(room.id, "u1", "Alice")
    updated = await repo.update_speaking(room.id, "u1", True, is_muted=True)
    assert updated.is_speaking is True
    assert updated.is_muted is True


@pytest.mark.asyncio
async def test_huddle_update_speaking_no_participant(db):
    repo = HuddleRepository(db)
    room = await repo.create_room("Speak2")
    assert await repo.update_speaking(room.id, "ghost", True) is None


# ── MeetingRepository ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_meeting_create_and_get(db):
    repo = MeetingRepository(db)
    m = await repo.create("Planning", created_by="u1")
    assert m.title == "Planning"
    assert m.status == "pending"
    assert (await repo.get_by_id(m.id)).id == m.id


@pytest.mark.asyncio
async def test_meeting_list_all_and_filter(db):
    repo = MeetingRepository(db)
    await repo.create("A", created_by="u1")
    await repo.create("B", created_by="u2")
    assert len(await repo.list_all()) == 2
    mine = await repo.list_all(created_by="u1")
    assert len(mine) == 1
    assert mine[0].created_by == "u1"


@pytest.mark.asyncio
async def test_meeting_update_file(db):
    repo = MeetingRepository(db)
    m = await repo.create("With File")
    updated = await repo.update_file(m, "fid", "a.mp3", "audio/mpeg")
    assert updated.file_id == "fid"
    assert updated.filename == "a.mp3"
    assert updated.mime_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_meeting_status_transcript_summary_flow(db):
    repo = MeetingRepository(db)
    m = await repo.create("Flow")
    m = await repo.update_status(m, "transcribing")
    assert m.status == "transcribing"
    m = await repo.update_transcript(m, "the transcript", duration_seconds=120)
    assert m.transcript == "the transcript"
    assert m.status == "summarizing"
    assert m.duration_seconds == 120
    actions = json.dumps([{"text": "do x", "priority": "high"}])
    m = await repo.update_summary(m, "a summary", actions)
    assert m.summary == "a summary"
    assert m.status == "done"
    assert json.loads(m.action_items)[0]["text"] == "do x"


@pytest.mark.asyncio
async def test_meeting_update_title_and_delete(db):
    repo = MeetingRepository(db)
    m = await repo.create("Title")
    m = await repo.update_title(m, "New Title")
    assert m.title == "New Title"
    await repo.delete(m)
    assert await repo.get_by_id(m.id) is None
