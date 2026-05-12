from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.meeting import MeetingORM


class MeetingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, title: str, created_by: Optional[str] = None) -> MeetingORM:
        meeting = MeetingORM(
            id=str(uuid.uuid4()),
            title=title,
            created_by=created_by,
            status="pending",
        )
        self.db.add(meeting)
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def get_by_id(self, meeting_id: str) -> Optional[MeetingORM]:
        result = await self.db.execute(
            select(MeetingORM).where(MeetingORM.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, created_by: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[MeetingORM]:
        q = select(MeetingORM).order_by(MeetingORM.created_at.desc()).limit(limit).offset(offset)
        if created_by:
            q = q.where(MeetingORM.created_by == created_by)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update_file(
        self,
        meeting: MeetingORM,
        file_id: str,
        filename: str,
        mime_type: str,
        status: str = "pending",
    ) -> MeetingORM:
        meeting.file_id = file_id
        meeting.filename = filename
        meeting.mime_type = mime_type
        meeting.status = status
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_status(self, meeting: MeetingORM, status: str) -> MeetingORM:
        meeting.status = status
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_transcript(
        self, meeting: MeetingORM, transcript: str, duration_seconds: Optional[int] = None
    ) -> MeetingORM:
        meeting.transcript = transcript
        meeting.status = "summarizing"
        if duration_seconds is not None:
            meeting.duration_seconds = duration_seconds
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_summary(
        self, meeting: MeetingORM, summary: str, action_items_json: str
    ) -> MeetingORM:
        meeting.summary = summary
        meeting.action_items = action_items_json
        meeting.status = "done"
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_title(self, meeting: MeetingORM, title: str) -> MeetingORM:
        meeting.title = title
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def delete(self, meeting: MeetingORM) -> None:
        await self.db.delete(meeting)
        await self.db.commit()
