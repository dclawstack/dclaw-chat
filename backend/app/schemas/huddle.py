from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class HuddleParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: str
    user_id: str
    display_name: str
    is_speaking: bool
    is_muted: bool
    joined_at: datetime
    last_seen_at: datetime


class HuddleRoomCreate(BaseModel):
    name: str = "Huddle"


class HuddleRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: Optional[str] = None
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    participants: List[HuddleParticipantOut] = []


class HuddleJoinRequest(BaseModel):
    display_name: str = "Anonymous"


class HuddleSpeakingRequest(BaseModel):
    is_speaking: bool
    is_muted: Optional[bool] = None
