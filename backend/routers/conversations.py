from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import uuid

from models import (
    ConversationORM,
    MessageORM,
    ConversationCreate,
    ConversationUpdate,
    ConversationOut,
    ConversationDetailOut,
    MessageOut,
)

router = APIRouter()


async def get_db():
    from main import async_session
    async with async_session() as session:
        yield session


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationORM)
        .options(selectinload(ConversationORM.messages))
        .order_by(ConversationORM.updated_at.desc())
    )
    conversations = result.scalars().all()

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


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationORM)
        .options(selectinload(ConversationORM.messages))
        .where(ConversationORM.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        folder=conversation.folder,
        model=conversation.model,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                model=m.model,
                created_at=m.created_at,
            )
            for m in conversation.messages
        ],
    )


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(req: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conversation = ConversationORM(
        id=str(uuid.uuid4()),
        title=req.title or "New Conversation",
        folder=req.folder,
        model=req.model,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        folder=conversation.folder,
        model=conversation.model,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    req: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConversationORM).where(ConversationORM.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        conversation.title = req.title
    if req.folder is not None:
        conversation.folder = req.folder

    await db.commit()
    await db.refresh(conversation)

    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        folder=conversation.folder,
        model=conversation.model,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationORM).where(ConversationORM.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.commit()

    return {"deleted": True}
