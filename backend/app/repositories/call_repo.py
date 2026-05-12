from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.call import CallRoomORM


class CallRoomRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        title: str,
        host_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        max_participants: int = 50,
        recording_enabled: bool = False,
    ) -> CallRoomORM:
        room = CallRoomORM(
            id=str(uuid.uuid4()),
            title=title,
            host_id=host_id,
            channel_id=channel_id,
            status="waiting",
            max_participants=max_participants,
            recording_enabled=recording_enabled,
        )
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def get_by_id(self, room_id: str) -> Optional[CallRoomORM]:
        result = await self.db.execute(
            select(CallRoomORM).where(CallRoomORM.id == room_id)
        )
        return result.scalar_one_or_none()

    async def list_active(
        self, channel_id: Optional[str] = None, limit: int = 50
    ) -> List[CallRoomORM]:
        q = (
            select(CallRoomORM)
            .where(CallRoomORM.status != "ended")
            .order_by(CallRoomORM.created_at.desc())
            .limit(limit)
        )
        if channel_id:
            q = q.where(CallRoomORM.channel_id == channel_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update_status(self, room: CallRoomORM, status: str) -> CallRoomORM:
        room.status = status
        if status == "ended":
            room.ended_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def delete(self, room: CallRoomORM) -> None:
        await self.db.delete(room)
        await self.db.commit()
