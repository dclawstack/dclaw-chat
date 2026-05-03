from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pydantic import BaseModel, Field
import uuid


class Base(DeclarativeBase):
    pass


# ─── SQLAlchemy ORM Models ───

class ConversationORM(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="New Conversation")
    folder: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[List["MessageORM"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="MessageORM.created_at")


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["ConversationORM"] = relationship(back_populates="messages")


# ─── Pydantic API Models ───

class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatCompletionRequest(BaseModel):
    conversation_id: str
    messages: List[Message]
    model: str = "gemma-4b"
    stream: bool = False
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class ChatCompletionResponse(BaseModel):
    id: str
    message: Message
    model: str
    usage: dict


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    folder: Optional[str] = None
    model: Optional[str] = "gemma-4b"


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    folder: Optional[str] = None


class ConversationOut(BaseModel):
    id: str
    title: str
    folder: Optional[str]
    model: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    model: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut] = []


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str  # local | cloud
    description: str
    available: bool
