"""Workspace knowledge-graph tables (V2 plan §4.2, Phase 3 groundwork).

Entities (people/topics/decisions/action items/files/meetings) and weighted
edges between them. ``workspace_id`` is nullable: NULL = legacy/global rows,
mirroring the channel/call/huddle scoping convention.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

#: Allowed entity kinds.
ENTITY_KINDS = ("person", "topic", "decision", "action_item", "file", "meeting")

#: Allowed edge relations.
EDGE_RELATIONS = (
    "discussed_in",
    "decided_by",
    "assigned_to",
    "mentioned_with",
    "supersedes",
)


class GraphEntityORM(Base):
    __tablename__ = "graph_entities"
    __table_args__ = (UniqueConstraint("workspace_id", "kind", "name"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    # person | topic | decision | action_item | file | meeting
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # message | meeting — where this entity was last extracted from
    source_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GraphEdgeORM(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        Index("ix_graph_edges_src_id", "src_id"),
        Index("ix_graph_edges_dst_id", "dst_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    src_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("graph_entities.id", ondelete="CASCADE")
    )
    dst_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("graph_entities.id", ondelete="CASCADE")
    )
    # discussed_in | decided_by | assigned_to | mentioned_with | supersedes
    relation: Mapped[str] = mapped_column(String(50))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
