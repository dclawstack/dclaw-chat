from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import WorkspaceBillingORM


class BillingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_workspace(
        self, workspace_id: str
    ) -> Optional[WorkspaceBillingORM]:
        result = await self.db.execute(
            select(WorkspaceBillingORM).where(
                WorkspaceBillingORM.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_subscription_id(
        self, subscription_id: str
    ) -> Optional[WorkspaceBillingORM]:
        result = await self.db.execute(
            select(WorkspaceBillingORM).where(
                WorkspaceBillingORM.stripe_subscription_id == subscription_id
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_for_workspace(
        self, workspace_id: str
    ) -> WorkspaceBillingORM:
        """Lazily create the billing row with free/inactive defaults."""
        existing = await self.get_for_workspace(workspace_id)
        if existing:
            return existing
        billing = WorkspaceBillingORM(workspace_id=workspace_id)
        self.db.add(billing)
        await self.db.commit()
        await self.db.refresh(billing)
        return billing

    async def update_from_subscription(
        self,
        workspace_id: str,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        status: Optional[str] = None,
        seats: Optional[int] = None,
        plan: Optional[str] = None,
    ) -> WorkspaceBillingORM:
        """Apply Stripe-derived state. Idempotent: replaying the same event
        writes the same values, so the row converges to a consistent state.
        ``None`` fields are left untouched.
        """
        billing = await self.get_or_create_for_workspace(workspace_id)
        if customer_id is not None:
            billing.stripe_customer_id = customer_id
        if subscription_id is not None:
            billing.stripe_subscription_id = subscription_id
        if status is not None:
            billing.status = status
        if seats is not None:
            billing.seats = seats
        if plan is not None:
            billing.plan = plan
        await self.db.commit()
        await self.db.refresh(billing)
        return billing
