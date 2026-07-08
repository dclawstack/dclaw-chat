from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

WORKSPACE_ROLES = ("Owner", "Admin", "Member", "Guest")


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: str
    created_at: datetime
    member_count: int = 0
    # The caller's own role in this workspace — lets the UI hide admin controls.
    my_role: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    role: Literal["Owner", "Admin", "Member", "Guest"]


class ModelPolicyOut(BaseModel):
    allowed_models: Optional[list[str]] = None
    local_only: bool = False


class ModelPolicyUpdate(BaseModel):
    allowed_models: Optional[list[str]] = None
    local_only: bool = False


class RetentionPolicyOut(BaseModel):
    retention_days: Optional[int] = None


class RetentionPolicyUpdate(BaseModel):
    # None = keep forever; otherwise purge messages older than N days.
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


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
