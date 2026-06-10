from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.database import Base


class WorkspaceBillingORM(Base):
    """Per-workspace billing state (Stripe per-seat subscriptions, Phase 5).

    One row per workspace, created lazily on first billing read. Webhooks are
    the single writer for Stripe-derived fields, so replayed events converge
    to the same state (idempotent).
    """

    __tablename__ = "workspace_billing"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # free | pro
    plan: Mapped[str] = mapped_column(String(20), default="free")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    seats: Mapped[int] = mapped_column(Integer, default=1)
    # inactive | active | past_due | canceled
    status: Mapped[str] = mapped_column(String(20), default="inactive")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
