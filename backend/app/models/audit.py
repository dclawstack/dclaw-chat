"""Append-only audit trail (#26).

Rows are written once and never updated or deleted through the application —
there is deliberately no update path in the repository/service layer and no
mutating API route. Retention/archival is an operator concern, not an API.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Nullable: platform-level admin actions (seed/clear) have no workspace.
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Dotted verb, e.g. "invite.created", "member.role_changed", "admin.clear"
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(32))
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    # JSON-encoded free-form context (never secrets)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
