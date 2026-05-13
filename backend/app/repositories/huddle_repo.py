from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.huddle import HuddleRoomORM, HuddleParticipantORM


class HuddleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(self, name: str, created_by: Optional[str] = None) -> HuddleRoomORM:
        room = HuddleRoomORM(
            id=str(uuid.uuid4()),
            name=name,
            created_by=created_by,
            status="active",
        )
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def get_room(self, room_id: str) -> Optional[HuddleRoomORM]:
        result = await self.db.execute(
            select(HuddleRoomORM).where(HuddleRoomORM.id == room_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self, limit: int = 50) -> List[HuddleRoomORM]:
        result = await self.db.execute(
            select(HuddleRoomORM)
            .where(HuddleRoomORM.status == "active")
            .order_by(HuddleRoomORM.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def close_room(self, room: HuddleRoomORM) -> HuddleRoomORM:
        room.status = "closed"
        room.closed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def delete_room(self, room: HuddleRoomORM) -> None:
        await self.db.delete(room)
        await self.db.commit()

    # ── Participant / presence ──────────────────────────────────────────────────

    async def get_participant(
        self, room_id: str, user_id: str
    ) -> Optional[HuddleParticipantORM]:
        result = await self.db.execute(
            select(HuddleParticipantORM).where(
                HuddleParticipantORM.room_id == room_id,
                HuddleParticipantORM.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def join_room(
        self, room_id: str, user_id: str, display_name: str
    ) -> HuddleParticipantORM:
        existing = await self.get_participant(room_id, user_id)
        if existing:
            existing.last_seen_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        participant = HuddleParticipantORM(
            id=str(uuid.uuid4()),
            room_id=room_id,
            user_id=user_id,
            display_name=display_name,
            is_speaking=False,
            is_muted=False,
        )
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant

    async def leave_room(self, room_id: str, user_id: str) -> bool:
        participant = await self.get_participant(room_id, user_id)
        if not participant:
            return False
        await self.db.delete(participant)
        await self.db.commit()
        return True

    async def update_speaking(
        self,
        room_id: str,
        user_id: str,
        is_speaking: bool,
        is_muted: Optional[bool] = None,
    ) -> Optional[HuddleParticipantORM]:
        participant = await self.get_participant(room_id, user_id)
        if not participant:
            return None
        participant.is_speaking = is_speaking
        if is_muted is not None:
            participant.is_muted = is_muted
        participant.last_seen_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant
