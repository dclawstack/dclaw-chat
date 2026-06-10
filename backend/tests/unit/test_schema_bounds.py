"""Schema bound/validation tests (gap T1-08)."""
import pytest
from pydantic import ValidationError

from app.schemas.ai import InlineMessage
from app.schemas.call import CallRoomCreate
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.schemas.huddle import HuddleJoinRequest, HuddleRoomCreate
from app.schemas.meeting import MeetingCreate, MeetingUpdateTitle

OVERSIZED = "x" * 256
MAXED = "x" * 255


# ── CallRoomCreate.max_participants ───────────────────────────────────────────


@pytest.mark.parametrize("value", [0, -1, 501, 10**9])
def test_call_room_max_participants_out_of_range(value):
    with pytest.raises(ValidationError):
        CallRoomCreate(max_participants=value)


@pytest.mark.parametrize("value", [1, 50, 500])
def test_call_room_max_participants_in_range(value):
    assert CallRoomCreate(max_participants=value).max_participants == value


# ── title/name free-text bounds (255) ────────────────────────────────────────


@pytest.mark.parametrize(
    "factory",
    [
        lambda v: CallRoomCreate(title=v),
        lambda v: ConversationCreate(title=v),
        lambda v: ConversationCreate(folder=v),
        lambda v: ConversationUpdate(title=v),
        lambda v: ConversationUpdate(folder=v),
        lambda v: HuddleRoomCreate(name=v),
        lambda v: HuddleJoinRequest(display_name=v),
        lambda v: MeetingCreate(title=v),
        lambda v: MeetingUpdateTitle(title=v),
    ],
    ids=[
        "call.title",
        "conversation.create.title",
        "conversation.create.folder",
        "conversation.update.title",
        "conversation.update.folder",
        "huddle.name",
        "huddle.display_name",
        "meeting.create.title",
        "meeting.update.title",
    ],
)
def test_name_like_fields_bounded_at_255(factory):
    with pytest.raises(ValidationError):
        factory(OVERSIZED)
    factory(MAXED)  # exactly 255 is accepted


# ── InlineMessage.role ───────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["user", "assistant", "system"])
def test_inline_message_allows_chat_roles(role):
    assert InlineMessage(role=role, content="hi").role == role


@pytest.mark.parametrize("role", ["hacker", "root", "USER", "", "assistant "])
def test_inline_message_rejects_other_roles(role):
    with pytest.raises(ValidationError):
        InlineMessage(role=role, content="hi")
