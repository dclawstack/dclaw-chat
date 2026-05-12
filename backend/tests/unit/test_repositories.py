import pytest
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.call_repo import CallRoomRepository
from app.schemas.conversation import ConversationCreate, ConversationUpdate


@pytest.mark.asyncio
async def test_conversation_repo_create(db):
    repo = ConversationRepository(db)
    conv = await repo.create(ConversationCreate(title="Test Chat", model="gemma-4b"))
    assert conv.title == "Test Chat"
    assert conv.model == "gemma-4b"
    assert conv.id is not None


@pytest.mark.asyncio
async def test_conversation_repo_get_by_id(db):
    repo = ConversationRepository(db)
    created = await repo.create(ConversationCreate(title="Find Me"))
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_conversation_repo_get_by_id_not_found(db):
    repo = ConversationRepository(db)
    found = await repo.get_by_id("non-existent-id")
    assert found is None


@pytest.mark.asyncio
async def test_conversation_repo_list_all(db):
    repo = ConversationRepository(db)
    await repo.create(ConversationCreate(title="A"))
    await repo.create(ConversationCreate(title="B"))
    items = await repo.list_all()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_conversation_repo_update(db):
    repo = ConversationRepository(db)
    created = await repo.create(ConversationCreate(title="Old"))
    updated = await repo.update(created, ConversationUpdate(title="New"))
    assert updated.title == "New"


@pytest.mark.asyncio
async def test_conversation_repo_delete(db):
    repo = ConversationRepository(db)
    created = await repo.create(ConversationCreate(title="Delete Me"))
    await repo.delete(created)
    found = await repo.get_by_id(created.id)
    assert found is None


@pytest.mark.asyncio
async def test_message_repo_create(db):
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)
    conv = await conv_repo.create(ConversationCreate())
    msg = await msg_repo.create(
        conversation_id=conv.id, role="user", content="Hello"
    )
    assert msg.role == "user"
    assert msg.content == "Hello"


@pytest.mark.asyncio
async def test_message_repo_list_by_conversation(db):
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)
    conv = await conv_repo.create(ConversationCreate())
    await msg_repo.create(conv.id, "user", "Hi")
    await msg_repo.create(conv.id, "assistant", "Hello")
    msgs = await msg_repo.list_by_conversation(conv.id)
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_call_room_repo_create(db):
    repo = CallRoomRepository(db)
    room = await repo.create(title="Sprint Call", host_id="user-1")
    assert room.title == "Sprint Call"
    assert room.host_id == "user-1"
    assert room.status == "waiting"
    assert room.max_participants == 50


@pytest.mark.asyncio
async def test_call_room_repo_get_by_id(db):
    repo = CallRoomRepository(db)
    created = await repo.create(title="Find Me")
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_call_room_repo_update_status(db):
    repo = CallRoomRepository(db)
    room = await repo.create(title="Status Test")
    updated = await repo.update_status(room, "active")
    assert updated.status == "active"
    ended = await repo.update_status(updated, "ended")
    assert ended.status == "ended"
    assert ended.ended_at is not None


@pytest.mark.asyncio
async def test_call_room_repo_list_active_excludes_ended(db):
    repo = CallRoomRepository(db)
    active = await repo.create(title="Active")
    ended = await repo.create(title="Ended")
    await repo.update_status(ended, "ended")
    rooms = await repo.list_active()
    ids = [r.id for r in rooms]
    assert active.id in ids
    assert ended.id not in ids
