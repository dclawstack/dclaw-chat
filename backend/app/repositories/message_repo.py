from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.message import MessageORM


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, message_id: str) -> Optional[MessageORM]:
        result = await self.db.execute(
            select(MessageORM).where(MessageORM.id == message_id)
        )
        return result.scalar_one_or_none()

    async def list_by_conversation(
        self, conversation_id: str, limit: int = 500, offset: int = 0
    ) -> List[MessageORM]:
        result = await self.db.execute(
            select(MessageORM)
            .where(MessageORM.conversation_id == conversation_id)
            .order_by(MessageORM.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
    ) -> MessageORM:
        message = MessageORM(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def delete(self, message: MessageORM) -> None:
        await self.db.delete(message)
        await self.db.commit()
