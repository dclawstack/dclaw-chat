from typing import List, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatCompletionRequest(BaseModel):
    conversation_id: str
    messages: List[Message]
    model: str = "gemma-4b"
    # When the chat happens inside a workspace, its model policy applies (#30).
    workspace_id: Optional[str] = None
    stream: bool = False
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class ChatCompletionResponse(BaseModel):
    id: str
    message: Message
    model: str
    usage: dict
