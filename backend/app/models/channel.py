from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class ChannelORM(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[List["ChannelMessageORM"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
        order_by="ChannelMessageORM.created_at",
    )


class ChannelMessageORM(Base):
    __tablename__ = "channel_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_name: Mapped[str] = mapped_column(String(100), default="Anonymous")
    content: Mapped[str] = mapped_column(Text)
    thread_parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("channel_messages.id", ondelete="SET NULL"), nullable=True
    )
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    topic: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel: Mapped["ChannelORM"] = relationship(back_populates="messages")
    replies: Mapped[List["ChannelMessageORM"]] = relationship(
        "ChannelMessageORM",
        foreign_keys=[thread_parent_id],
        back_populates="parent",
    )
    parent: Mapped[Optional["ChannelMessageORM"]] = relationship(
        "ChannelMessageORM",
        foreign_keys="ChannelMessageORM.thread_parent_id",
        remote_side="ChannelMessageORM.id",
        back_populates="replies",
    )
