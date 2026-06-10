from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class GraphEntityOut(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    kind: str
    name: str
    summary: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GraphEdgeOut(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    src_id: str
    dst_id: str
    relation: str
    weight: int
    source_id: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GraphNeighborsOut(BaseModel):
    entity: GraphEntityOut
    entities: List[GraphEntityOut]
    edges: List[GraphEdgeOut]


class GraphCitation(BaseModel):
    """An entity reference with a pointer back to its source."""

    name: str
    kind: str
    summary: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    updated_at: Optional[datetime] = None


class CatchMeUpOut(BaseModel):
    workspace_id: str
    since: Optional[datetime] = None
    entities: List[GraphCitation]
    decisions: List[GraphCitation]
    action_items: List[GraphCitation]
    edges: List[GraphEdgeOut] = []
