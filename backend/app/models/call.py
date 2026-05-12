from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.database import Base


class CallRoomORM(Base):
    __tablename__ = "call_rooms"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), default="New Call")
    host_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # waiting | active | ended
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    max_participants: Mapped[int] = mapped_column(Integer, default=50)
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
