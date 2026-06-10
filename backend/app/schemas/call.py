from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CallRoomCreate(BaseModel):
    title: str = Field("New Call", max_length=255)
    channel_id: Optional[str] = Field(None, max_length=255)
    workspace_id: Optional[str] = Field(None, max_length=36)
    max_participants: int = Field(50, ge=1, le=500)
    recording_enabled: bool = False


class CallRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    host_id: Optional[str] = None
    channel_id: Optional[str] = None
    workspace_id: Optional[str] = None
    status: str
    max_participants: int
    recording_enabled: bool
    created_at: datetime
    ended_at: Optional[datetime] = None
