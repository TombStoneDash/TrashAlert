"""Stripe billing endpoints for TrashAlert subscriptions.

Endpoints:
  POST /api/stripe/checkout       — Create a Checkout Session for a plan
  POST /api/stripe/webhook        — Handle Stripe webhook events
  GET  /api/stripe/portal         — Get a billing portal URL for self-service
  GET  /api/stripe/status         — Check subscription status for a customer
  GET  /api/stripe/plans          — List available plans with pricing
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.stripe_config import (
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    STRIPE_PUBLISHABLE_KEY,
    BASE_URL,
    PLANS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SUBS_PATH = DATA_DIR / "stripe_subscriptions.json"

# ---------------------------------------------------------------------------
# Lazy Stripe import — only fail when actually called without key
# ---------------------------------------------------------------------------

_stripe = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            _stripe = stripe
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Stripe SDK not installed. Run: pip install stripe",
            )
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="STRIPE_SECRET_KEY not configured.",
        )
    return _stripe


# ---------------------------------------------------------------------------
# Local subscription store (JSON file — replace with DB in production)
# ---------------------------------------------------------------------------

def _load_subs() -> dict:
    if SUBS_PATH.exists():
        return json.loads(SUBS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_subs(subs: dict):
    SUBS_PATH.write_text(json.dumps(subs, indent=2), encoding="utf-8")


def _record_subscription(customer_id: str, data: dict):
    subs = _load_subs()
    subs[customer_id] = {
        **data,
        "updated_at": datetime.utcnow().isoformat(),
    }
    _save_subs(subs)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Plan slug: 'starter' or 'portfolio'")
    email: Optional[str] = Field(None, description="Customer email (pre-fills Checkout)")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/plans")
async def list_plans():
    """Return available subscription plans with pricing."""
    plans_out = []
    for slug, plan in PLANS.items():
        plans_out.append({
            "slug": slug,
            "name": plan["name"],
            "amount": plan["amount"],
            "currency": plan["currency"],
            "interval": plan["interval"],
            "display_price": f"${plan['amount'] // 100}/mo",
            "properties": "Unlimited" if plan["properties"] == -1 else plan["properties"],
            "features": plan["features"],
        })
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "plans": plans_out,
    }


@router.post("/checkout")
async def create_checkout(req: CheckoutRequest):
    """Create a Stripe Checkout Session and return the URL.

    The frontend redirects the user to this URL to complete payment.
    """
    stripe = _get_stripe()

    if req.plan not in PLANS:
        raise HTTPException(400, detail=f"Invalid plan: {req.plan}. Use 'starter' or 'portfolio'.")

    plan = PLANS[req.plan]
    success = req.success_url or f"{BASE_URL}/pricing?session_id={{CHECKOUT_SESSION_ID}}&status=success"
    cancel = req.cancel_url or f"{BASE_URL}/pricing?status=cancelled"

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": plan["price_id"],
                "quantity": 1,
            }],
            customer_email=req.email,
            success_url=success,
            cancel_url=cancel,
            metadata={
                "plan": req.plan,
                "product": "trashalert",
            },
            subscription_data={
                "metadata": {
                    "plan": req.plan,
                },
            },
        )
    except Exception as e:
        logger.error(f"Stripe Checkout error: {e}")
        raise HTTPException(500, detail=f"Failed to create checkout session: {str(e)}")

    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Processes: checkout.session.completed, customer.subscription.updated,
    customer.subscription.deleted, invoice.payment_failed.
    """
    stripe = _get_stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        event = json.loads(payload)
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig, STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise HTTPException(400, detail="Invalid webhook signature")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer", "")
        subscription_id = data.get("subscription", "")
        email = data.get("customer_email", "")
        plan = data.get("metadata", {}).get("plan", "unknown")

        _record_subscription(customer_id, {
            "subscription_id": subscription_id,
            "email": email,
            "plan": plan,
            "status": "active",
        })
        logger.info(f"New subscription: {email} → {plan}")

    elif event_type == "customer.subscription.updated":
        customer_id = data.get("customer", "")
        status = data.get("status", "")
        plan = data.get("metadata", {}).get("plan", "unknown")

        _record_subscription(customer_id, {
            "subscription_id": data.get("id", ""),
            "plan": plan,
            "status": status,
        })

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer", "")
        _record_subscription(customer_id, {
            "subscription_id": data.get("id", ""),
            "status": "canceled",
        })
        logger.info(f"Subscription canceled: {customer_id}")

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer", "")
        logger.warning(f"Payment failed for customer: {customer_id}")
        subs = _load_subs()
        if customer_id in subs:
            subs[customer_id]["status"] = "past_due"
            _save_subs(subs)

    return JSONResponse({"received": True})


@router.get("/portal")
async def billing_portal(customer_id: str):
    """Generate a Stripe Customer Portal URL for self-service billing management.

    Customers can update payment methods, view invoices, and cancel.
    """
    stripe = _get_stripe()

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{BASE_URL}/pricing",
        )
    except Exception as e:
        logger.error(f"Stripe Portal error: {e}")
        raise HTTPException(500, detail=f"Failed to create portal session: {str(e)}")

    return {"portal_url": session.url}


@router.get("/status")
async def subscription_status(email: Optional[str] = None, customer_id: Optional[str] = None):
    """Check subscription status for a customer by email or customer ID."""
    subs = _load_subs()

    if customer_id and customer_id in subs:
        return subs[customer_id]

    if email:
        for cid, sub in subs.items():
            if sub.get("email", "").lower() == email.lower():
                return {"customer_id": cid, **sub}

    return {"status": "none", "message": "No active subscription found."}
