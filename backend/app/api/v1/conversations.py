from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationOut,
    ConversationDetailOut,
)
from app.repositories.conversation_repo import ConversationRepository
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import NotFoundException, ForbiddenException

router = APIRouter()


def _assert_owner(conversation, user: CurrentUser) -> None:
    """403 on another user's conversation. NULL owner = legacy-shared row
    (same fail-open policy as meetings/calls)."""
    if conversation.created_by and conversation.created_by != user.user_id:
        raise ForbiddenException("Not your conversation")


@router.get("", response_model=List[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    conversations = await repo.list_all(owner_id=user.user_id)
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            folder=c.folder,
            model=c.model,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages),
        )
        for c in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    conversation = await repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundException("Conversation not found")
    _assert_owner(conversation, user)
    return ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        folder=conversation.folder,
        model=conversation.model,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        messages=[
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "created_at": m.created_at,
            }
            for m in conversation.messages
        ],
    )


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    req: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    conversation = await repo.create(req, created_by=user.user_id)
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        folder=conversation.folder,
        model=conversation.model,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    req: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    conversation = await repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundException("Conversation not found")
    _assert_owner(conversation, user)
    updated = await repo.update(conversation, req)
    return ConversationOut(
        id=updated.id,
        title=updated.title,
        folder=updated.folder,
        model=updated.model,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        message_count=len(updated.messages),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    conversation = await repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundException("Conversation not found")
    _assert_owner(conversation, user)
    await repo.delete(conversation)
    return None
