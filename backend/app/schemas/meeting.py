import json
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MeetingActionItem(BaseModel):
    text: str
    priority: Literal["low", "medium", "high"] = "medium"
    assignee: Optional[str] = None
    status: Literal["open", "done"] = "open"


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_id: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    action_items: Optional[List[MeetingActionItem]] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("action_items", mode="before")
    @classmethod
    def parse_action_items(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return v


class MeetingCreate(BaseModel):
    title: str = Field("Untitled Meeting", max_length=255)


class MeetingUpdateTitle(BaseModel):
    title: str = Field(..., max_length=255)


class ProcessMeetingRequest(BaseModel):
    model: Optional[str] = "gemma-4b"


class MeetingSummaryOut(BaseModel):
    meeting_id: str
    transcript: str
    summary: str
    action_items: List[MeetingActionItem]
