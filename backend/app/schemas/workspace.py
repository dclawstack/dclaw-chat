from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: str
    created_at: datetime
    member_count: int = 0


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    role: str
    created_at: datetime


class InviteCreate(BaseModel):
    email: str = Field(min_length=1, max_length=255)


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str
    workspace_id: str
    email: str


class InviteAccepted(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    role: str
