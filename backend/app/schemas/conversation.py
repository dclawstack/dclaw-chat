from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageOut


class ConversationCreate(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = Field("New Conversation", max_length=255)
    folder: Optional[str] = Field(None, max_length=255)
    model: Optional[str] = "gemma-4b"


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    folder: Optional[str] = Field(None, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    folder: Optional[str]
    model: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut] = []
