from datetime import datetime
from typing import Optional, List
from sqlalchemy import Boolean, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class WorkspaceORM(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), default="Workspace")
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # AI model policy (#30): JSON list of allowed model ids (NULL = all),
    # and a local-only switch that blocks every cloud provider.
    allowed_models: Mapped[Optional[str]] = mapped_column(Text)
    local_only: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Data retention (#33): purge messages older than N days. NULL = keep forever.
    retention_days: Mapped[Optional[int]] = mapped_column(Integer)
    # SCIM (#31): sha256 of the workspace's provisioning bearer token. NULL = SCIM off.
    scim_token_hash: Mapped[Optional[str]] = mapped_column(String(64))
    # Enterprise SSO (#35, ADR 0001): the Logto organization this workspace maps to.
    logto_organization_id: Mapped[Optional[str]] = mapped_column(String(64))

    members: Mapped[List["WorkspaceMemberORM"]] = relationship(
        "WorkspaceMemberORM",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class WorkspaceMemberORM(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Owner | Admin | Member | Guest
    role: Mapped[str] = mapped_column(String(20), default="Member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace: Mapped["WorkspaceORM"] = relationship(
        "WorkspaceORM", back_populates="members"
    )


class WorkspaceInviteORM(Base):
    __tablename__ = "workspace_invites"

    # The id doubles as the invite token shared with the invitee.
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
