from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    workspace_id: Optional[str] = None  # enables knowledge-graph citations
    model: Optional[str] = "gemma-4b"
    include_context: bool = False


class Citation(BaseModel):
    """Knowledge-graph citation: an entity + a pointer to its source."""

    name: str
    kind: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None


class AIChatResponse(BaseModel):
    answer: str
    model: str
    rag_chunks_used: int
    context_snippets: List[str] = []
    citations: List[Citation] = []


class InlineMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class SummarizeRequest(BaseModel):
    conversation_id: str
    model: Optional[str] = "gemma-4b"
    messages: Optional[List[InlineMessage]] = None  # client-side messages fallback


class SummarizeResponse(BaseModel):
    conversation_id: str
    summary: str
    message_count: int


class ExtractedAction(BaseModel):
    text: str
    priority: Literal["low", "medium", "high"] = "medium"
    assignee: Optional[str] = None
    status: Literal["open", "done"] = "open"


class ActionsRequest(BaseModel):
    conversation_id: str
    model: Optional[str] = "gemma-4b"
    messages: Optional[List[InlineMessage]] = None  # client-side messages fallback


class ActionsResponse(BaseModel):
    conversation_id: str
    actions: List[ExtractedAction]
