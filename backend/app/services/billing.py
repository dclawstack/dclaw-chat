"""Plan gating helpers (Phase 5 scaffolding).

``workspace_plan`` is the single source of truth for a workspace's effective
plan: a workspace is "pro" only while its subscription is active; anything
else (no billing row, inactive, past_due, canceled) is "free".

``check_ai_quota`` is a documented stub: wiring it into the model-router
stats (count AI calls per workspace per month against AI_CALLS_FREE_LIMIT
for free workspaces) is future work. Callers can already depend on its
signature today.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.billing_repo import BillingRepository

# Free-tier cap on AI copilot calls per workspace per month (Phase 5 plan).
AI_CALLS_FREE_LIMIT = 100


async def workspace_plan(db: AsyncSession, workspace_id: str) -> str:
    """Return the workspace's effective plan: "pro" or "free"."""
    billing = await BillingRepository(db).get_for_workspace(workspace_id)
    if billing and billing.plan == "pro" and billing.status == "active":
        return "pro"
    return "free"


async def check_ai_quota(db: AsyncSession, workspace_id: str) -> bool:
    """Stub: always allows the call.

    Future work: for free-plan workspaces, compare this month's AI call count
    (from router stats) against AI_CALLS_FREE_LIMIT and return False when
    exhausted. Pro workspaces are always allowed.
    """
    return True
