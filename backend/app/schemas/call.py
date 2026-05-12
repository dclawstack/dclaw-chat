from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CallRoomCreate(BaseModel):
    title: str = "New Call"
    channel_id: Optional[str] = None
    max_participants: int = 50
    recording_enabled: bool = False


class CallRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    host_id: Optional[str] = None
    channel_id: Optional[str] = None
    status: str
    max_participants: int
    recording_enabled: bool
    created_at: datetime
    ended_at: Optional[datetime] = None
