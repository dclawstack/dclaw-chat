from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    model: Optional[str]
    created_at: datetime
