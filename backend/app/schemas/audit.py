from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: str
    workspace_id: Optional[str]
    actor_id: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    detail: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
