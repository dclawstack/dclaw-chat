from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


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
    name: str = Field("Huddle", max_length=255)
    workspace_id: Optional[str] = Field(None, max_length=36)


class HuddleRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: Optional[str] = None
    workspace_id: Optional[str] = None
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    participants: List[HuddleParticipantOut] = []


class HuddleJoinRequest(BaseModel):
    display_name: str = Field("Anonymous", max_length=255)


class HuddleSpeakingRequest(BaseModel):
    is_speaking: bool
    is_muted: Optional[bool] = None
