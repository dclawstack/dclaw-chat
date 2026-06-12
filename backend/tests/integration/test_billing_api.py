"""Billing API tests (v2.0 Phase 5 Stripe scaffolding).

Stripe is never called: ``stripe.checkout.Session.create`` and
``stripe.Webhook.construct_event`` are monkeypatched, and the cached
``Settings`` object gets keys patched in per-test. Two-identity pattern
mirrors test_workspaces_api.py.
"""
import contextlib
import json
import types

import pytest
import stripe

from app.core.config import get_settings
from app.core.deps import get_current_user, CurrentUser
from app.main import app


@contextlib.contextmanager
def _as_user(user_id: str, email: str = "b@dclawstack.io"):
    async def _override():
        return CurrentUser(user_id=user_id, email=email, role="User")

    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _override
    try:
        yield
    finally:
        app.dependency_overrides[get_current_user] = original


async def _make_workspace(client, name="Billable") -> str:
    created = await client.post("/api/v1/workspaces", json={"name": name})
    assert created.status_code == 201
    return created.json()["id"]


def _enable_stripe(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro_dummy")


async def _post_webhook(client, monkeypatch, event: dict):
    """Deliver an event with construct_event mocked to verify-and-return it."""
    def fake_construct_event(payload, sig_header, secret):
        assert secret == "whsec_dummy"
        return json.loads(payload)

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)
    return await client.post(
        "/api/v1/billing/webhook",
        content=json.dumps(event),
        headers={"stripe-signature": "t=1,v1=mocked", "content-type": "application/json"},
    )


# ---------------------------------------------------------------- GET billing


@pytest.mark.asyncio
async def test_get_billing_member_sees_free_inactive_defaults(client):
    wid = await _make_workspace(client)
    resp = await client.get(f"/api/v1/billing/workspaces/{wid}")
    assert resp.status_code == 200
    assert resp.json() == {
        "workspace_id": wid,
        "plan": "free",
        "status": "inactive",
        "seats": 1,
    }


@pytest.mark.asyncio
async def test_get_billing_non_member_403(client):
    wid = await _make_workspace(client)
    with _as_user("outsider-1"):
        resp = await client.get(f"/api/v1/billing/workspaces/{wid}")
        assert resp.status_code == 403


# ------------------------------------------------------------------ checkout


@pytest.mark.asyncio
async def test_checkout_503_when_stripe_key_unset(client, monkeypatch):
    wid = await _make_workspace(client)
    # Explicitly clear: a real key may exist in the developer's environment
    monkeypatch.setattr(get_settings(), "STRIPE_SECRET_KEY", "")
    resp = await client.post(
        f"/api/v1/billing/workspaces/{wid}/checkout",
        json={"return_url": "http://localhost:3000"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "billing not configured"


@pytest.mark.asyncio
async def test_checkout_owner_gets_checkout_url(client, monkeypatch):
    wid = await _make_workspace(client)
    _enable_stripe(monkeypatch)

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    resp = await client.post(
        f"/api/v1/billing/workspaces/{wid}/checkout",
        json={"return_url": "http://localhost:3000/settings"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123"
    }
    assert captured["mode"] == "subscription"
    assert captured["client_reference_id"] == wid
    assert captured["metadata"]["workspace_id"] == wid
    assert captured["line_items"] == [{"price": "price_pro_dummy", "quantity": 1}]
    assert captured["success_url"].startswith("http://localhost:3000/settings")


@pytest.mark.asyncio
async def test_checkout_quantity_tracks_member_count(client, monkeypatch):
    wid = await _make_workspace(client)
    invite = await client.post(
        f"/api/v1/workspaces/{wid}/invites", json={"email": "two@dclawstack.io"}
    )
    token = invite.json()["token"]
    with _as_user("member-2"):
        await client.post(f"/api/v1/workspaces/invites/{token}/accept")

    _enable_stripe(monkeypatch)
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(url="https://checkout.stripe.com/c/cs_2")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    resp = await client.post(
        f"/api/v1/billing/workspaces/{wid}/checkout",
        json={"return_url": "http://localhost:3000"},
    )
    assert resp.status_code == 200
    assert captured["line_items"][0]["quantity"] == 2
    assert captured["metadata"]["seats"] == "2"


@pytest.mark.asyncio
async def test_checkout_plain_member_403(client, monkeypatch):
    wid = await _make_workspace(client)
    invite = await client.post(
        f"/api/v1/workspaces/{wid}/invites", json={"email": "m@dclawstack.io"}
    )
    token = invite.json()["token"]

    _enable_stripe(monkeypatch)
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        lambda **kwargs: pytest.fail("stripe must not be called for non-admins"),
    )

    with _as_user("member-3"):
        await client.post(f"/api/v1/workspaces/invites/{token}/accept")
        resp = await client.post(
            f"/api/v1/billing/workspaces/{wid}/checkout",
            json={"return_url": "http://localhost:3000"},
        )
        assert resp.status_code == 403


# ------------------------------------------------------------------- webhook


@pytest.mark.asyncio
async def test_webhook_503_when_secret_unset(client, monkeypatch):
    # Explicitly clear: a real secret may exist in the developer's environment
    monkeypatch.setattr(get_settings(), "STRIPE_WEBHOOK_SECRET", "")
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=x"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "billing not configured"


@pytest.mark.asyncio
async def test_webhook_bad_signature_400(client, monkeypatch):
    _enable_stripe(monkeypatch)

    def raise_bad_sig(payload, sig_header, secret):
        raise stripe.SignatureVerificationError("bad signature", sig_header)

    monkeypatch.setattr(stripe.Webhook, "construct_event", raise_bad_sig)
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=forged"},
    )
    assert resp.status_code == 400


def _checkout_completed_event(wid: str, seats: int = 3) -> dict:
    return {
        "id": "evt_checkout_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "client_reference_id": wid,
                "customer": "cus_test_1",
                "subscription": "sub_test_1",
                "metadata": {"workspace_id": wid, "seats": str(seats)},
            }
        },
    }


@pytest.mark.asyncio
async def test_webhook_checkout_completed_activates_pro(client, monkeypatch):
    wid = await _make_workspace(client)
    _enable_stripe(monkeypatch)

    resp = await _post_webhook(client, monkeypatch, _checkout_completed_event(wid))
    assert resp.status_code == 200

    billing = (await client.get(f"/api/v1/billing/workspaces/{wid}")).json()
    assert billing == {
        "workspace_id": wid,
        "plan": "pro",
        "status": "active",
        "seats": 3,
    }


@pytest.mark.asyncio
async def test_webhook_replayed_event_is_idempotent(client, monkeypatch):
    wid = await _make_workspace(client)
    _enable_stripe(monkeypatch)

    event = _checkout_completed_event(wid)
    first = await _post_webhook(client, monkeypatch, event)
    replay = await _post_webhook(client, monkeypatch, event)
    assert first.status_code == replay.status_code == 200

    billing = (await client.get(f"/api/v1/billing/workspaces/{wid}")).json()
    assert billing["plan"] == "pro"
    assert billing["status"] == "active"
    assert billing["seats"] == 3


@pytest.mark.asyncio
async def test_webhook_subscription_updated_syncs_status_and_seats(
    client, monkeypatch
):
    wid = await _make_workspace(client)
    _enable_stripe(monkeypatch)
    await _post_webhook(client, monkeypatch, _checkout_completed_event(wid))

    updated = {
        "id": "evt_sub_upd_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test_1",
                "status": "past_due",
                "items": {"data": [{"quantity": 5}]},
                "metadata": {"workspace_id": wid},
            }
        },
    }
    resp = await _post_webhook(client, monkeypatch, updated)
    assert resp.status_code == 200

    billing = (await client.get(f"/api/v1/billing/workspaces/{wid}")).json()
    assert billing["status"] == "past_due"
    assert billing["seats"] == 5
    assert billing["plan"] == "pro"  # plan unchanged until deletion


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_downgrades_to_free(client, monkeypatch):
    wid = await _make_workspace(client)
    _enable_stripe(monkeypatch)
    await _post_webhook(client, monkeypatch, _checkout_completed_event(wid))

    deleted = {
        "id": "evt_sub_del_1",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test_1",
                "status": "canceled",
                "metadata": {"workspace_id": wid},
            }
        },
    }
    resp = await _post_webhook(client, monkeypatch, deleted)
    assert resp.status_code == 200

    billing = (await client.get(f"/api/v1/billing/workspaces/{wid}")).json()
    assert billing["plan"] == "free"
    assert billing["status"] == "canceled"

    # Replay of the deletion stays consistent
    replay = await _post_webhook(client, monkeypatch, deleted)
    assert replay.status_code == 200
    billing = (await client.get(f"/api/v1/billing/workspaces/{wid}")).json()
    assert billing["plan"] == "free"
    assert billing["status"] == "canceled"
