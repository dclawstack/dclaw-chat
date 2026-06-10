"""Workspace billing — Stripe per-seat subscriptions (Phase 5 scaffolding).

Works with no Stripe keys configured: checkout and webhook return
503 "billing not configured" until STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET
are set. Enabling billing is config-only — no code changes needed.

Webhook contract (register in Stripe Dashboard → Developers → Webhooks):
    POST <backend-url>/api/v1/billing/webhook
Events handled: checkout.session.completed, customer.subscription.updated,
customer.subscription.deleted. Handlers are idempotent — replaying an event
writes the same state.
"""
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.workspaces import require_member
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException
from app.repositories.billing_repo import BillingRepository
from app.repositories.workspace_repo import WorkspaceRepository, is_workspace_member
from app.schemas.billing import BillingOut, CheckoutRequest, CheckoutOut

router = APIRouter()

_NOT_CONFIGURED = HTTPException(status_code=503, detail="billing not configured")


@router.get("/workspaces/{workspace_id}", response_model=BillingOut)
async def get_workspace_billing(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Current plan/status/seats for a workspace (members only)."""
    if not await is_workspace_member(db, workspace_id, user.user_id):
        raise ForbiddenException("Not a member of this workspace")
    billing = await BillingRepository(db).get_or_create_for_workspace(workspace_id)
    return BillingOut.model_validate(billing)


@router.post("/workspaces/{workspace_id}/checkout", response_model=CheckoutOut)
async def create_checkout_session(
    workspace_id: str,
    req: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Start a Stripe Checkout for the Pro per-seat plan (Owner/Admin only)."""
    workspace, _ = await require_member(
        WorkspaceRepository(db), workspace_id, user, roles=("Owner", "Admin")
    )
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        raise _NOT_CONFIGURED

    stripe.api_key = settings.STRIPE_SECRET_KEY
    seats = max(1, len(workspace.members))
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_PRO, "quantity": seats}],
        success_url=f"{req.return_url}?billing=success",
        cancel_url=f"{req.return_url}?billing=cancel",
        client_reference_id=workspace_id,
        metadata={"workspace_id": workspace_id, "seats": str(seats)},
        # Mirror onto the subscription so subscription.* events carry it too.
        subscription_data={"metadata": {"workspace_id": workspace_id}},
    )
    return CheckoutOut(checkout_url=session.url)


def _normalize_status(stripe_status: Optional[str]) -> str:
    """Collapse Stripe subscription statuses onto our 4-state column."""
    mapping = {
        "active": "active",
        "trialing": "active",
        "past_due": "past_due",
        "unpaid": "past_due",
        "canceled": "canceled",
        "incomplete_expired": "canceled",
    }
    return mapping.get(stripe_status or "", "inactive")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook receiver — NO auth dependency (Stripe calls it).

    Authenticity comes from the signature check against STRIPE_WEBHOOK_SECRET.
    """
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise _NOT_CONFIGURED

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    repo = BillingRepository(db)
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata") or {}
        workspace_id = obj.get("client_reference_id") or metadata.get("workspace_id")
        if workspace_id:
            seats = metadata.get("seats")
            await repo.update_from_subscription(
                workspace_id,
                customer_id=obj.get("customer"),
                subscription_id=obj.get("subscription"),
                status="active",
                seats=int(seats) if seats else None,
                plan="pro",
            )

    elif event_type == "customer.subscription.updated":
        billing = await repo.get_by_subscription_id(obj.get("id"))
        workspace_id = (
            billing.workspace_id
            if billing
            else (obj.get("metadata") or {}).get("workspace_id")
        )
        if workspace_id:
            items = ((obj.get("items") or {}).get("data")) or []
            quantity = items[0].get("quantity") if items else None
            await repo.update_from_subscription(
                workspace_id,
                subscription_id=obj.get("id"),
                status=_normalize_status(obj.get("status")),
                seats=quantity,
            )

    elif event_type == "customer.subscription.deleted":
        billing = await repo.get_by_subscription_id(obj.get("id"))
        workspace_id = (
            billing.workspace_id
            if billing
            else (obj.get("metadata") or {}).get("workspace_id")
        )
        if workspace_id:
            await repo.update_from_subscription(
                workspace_id, status="canceled", plan="free"
            )

    return {"received": True}
