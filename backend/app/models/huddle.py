from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class HuddleRoomORM(Base):
    __tablename__ = "huddle_rooms"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), default="Huddle")
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # NULL = legacy/open huddle; set = only that workspace's members may join
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    # active | closed
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    participants: Mapped[List["HuddleParticipantORM"]] = relationship(
        "HuddleParticipantORM",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class HuddleParticipantORM(Base):
    __tablename__ = "huddle_participants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("huddle_rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="Anonymous")
    is_speaking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    room: Mapped["HuddleRoomORM"] = relationship(
        "HuddleRoomORM", back_populates="participants"
    )
