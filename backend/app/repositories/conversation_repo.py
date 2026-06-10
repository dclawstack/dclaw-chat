from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
import uuid

from app.models.conversation import ConversationORM
from app.schemas.conversation import ConversationCreate, ConversationUpdate


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conversation_id: str) -> Optional[ConversationORM]:
        result = await self.db.execute(
            select(ConversationORM)
            .options(selectinload(ConversationORM.messages))
            .where(ConversationORM.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, limit: int = 100, offset: int = 0, owner_id: Optional[str] = None
    ) -> List[ConversationORM]:
        query = (
            select(ConversationORM)
            .options(selectinload(ConversationORM.messages))
            .order_by(ConversationORM.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if owner_id is not None:
            # NULL created_by = legacy rows from before ownership existed
            query = query.where(
                or_(
                    ConversationORM.created_by == owner_id,
                    ConversationORM.created_by.is_(None),
                )
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(
        self, data: ConversationCreate, created_by: Optional[str] = None
    ) -> ConversationORM:
        conversation = ConversationORM(
            id=data.id or str(uuid.uuid4()),
            title=data.title or "New Conversation",
            created_by=created_by,
            folder=data.folder,
            model=data.model,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def update(
        self, conversation: ConversationORM, data: ConversationUpdate
    ) -> ConversationORM:
        if data.title is not None:
            conversation.title = data.title
        if data.folder is not None:
            conversation.folder = data.folder
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def delete(self, conversation: ConversationORM) -> None:
        await self.db.delete(conversation)
        await self.db.commit()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(ConversationORM))
        return result.scalar() or 0
