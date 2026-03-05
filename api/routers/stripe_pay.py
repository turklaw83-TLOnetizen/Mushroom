# ---- Stripe Payment Router ------------------------------------------------
# Payment links, checkout sessions, webhook handler, configuration.

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stripe",
    tags=["Stripe Payments"],
)


# ---- Request Models ------------------------------------------------------

class CreatePaymentLinkRequest(BaseModel):
    client_id: str = Field(..., max_length=50)
    plan_id: str = Field(..., max_length=50)
    amount: float = Field(..., gt=0, description="Amount in dollars")
    description: str = Field(default="Payment", max_length=500)
    client_name: str = Field(default="", max_length=200)
    client_email: str = Field(default="", max_length=500)


class CreateCheckoutRequest(BaseModel):
    client_id: str = Field(..., max_length=50)
    plan_id: str = Field(..., max_length=50)
    amount: float = Field(..., gt=0, description="Amount in dollars")
    description: str = Field(default="Payment", max_length=500)
    client_name: str = Field(default="", max_length=200)
    client_email: str = Field(default="", max_length=500)


# ---- Payment Link Endpoints ----------------------------------------------

@router.post("/payment-link")
def create_payment_link(
    body: CreatePaymentLinkRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a reusable Stripe Payment Link for a client."""
    try:
        from core.stripe_pay import create_payment_link as _create_link
        amount_cents = int(round(body.amount * 100))
        result = _create_link(
            client_id=body.client_id,
            plan_id=body.plan_id,
            amount_cents=amount_cents,
            description=body.description,
            client_name=body.client_name,
            client_email=body.client_email,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to create payment link")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/payment-links")
def list_payment_links(
    client_id: str = "",
    user: dict = Depends(get_current_user),
):
    """List Stripe payment links, optionally filtered by client."""
    try:
        from core.stripe_pay import get_payment_links
        return {"items": get_payment_links(client_id)}
    except Exception:
        logger.exception("Failed to list payment links")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Checkout Session Endpoints ------------------------------------------

@router.post("/checkout")
def create_checkout(
    body: CreateCheckoutRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a Stripe Checkout Session for one-time payment."""
    try:
        from core.stripe_pay import create_checkout_session
        amount_cents = int(round(body.amount * 100))
        result = create_checkout_session(
            client_id=body.client_id,
            plan_id=body.plan_id,
            amount_cents=amount_cents,
            description=body.description,
            client_name=body.client_name,
            client_email=body.client_email,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to create checkout session")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/checkout-sessions")
def list_checkout_sessions(
    client_id: str = "",
    user: dict = Depends(get_current_user),
):
    """List checkout sessions, optionally filtered by client."""
    try:
        from core.stripe_pay import get_checkout_sessions
        return {"items": get_checkout_sessions(client_id)}
    except Exception:
        logger.exception("Failed to list checkout sessions")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Webhook Endpoint ----------------------------------------------------

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook handler — no auth required (Stripe verifies via signature).
    Handles: checkout.session.completed, payment_intent.succeeded
    Auto-records payments against client payment plans.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")

        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")

        from core.stripe_pay import handle_webhook_event
        result = handle_webhook_event(payload, sig_header)

        return {"status": "ok", **result}

    except ValueError as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        logger.exception("Stripe webhook handler error")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Configuration -------------------------------------------------------

@router.get("/config")
def get_stripe_config(
    user: dict = Depends(get_current_user),
):
    """Get public Stripe configuration (no secrets exposed)."""
    try:
        from core.stripe_pay import get_stripe_config as _get_config
        return _get_config()
    except Exception:
        logger.exception("Failed to get Stripe config")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook-events")
def list_webhook_events(
    limit: int = 20,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """List recent webhook events for debugging."""
    try:
        from core.stripe_pay import get_recent_webhook_events
        return {"items": get_recent_webhook_events(limit)}
    except Exception:
        logger.exception("Failed to list webhook events")
        raise HTTPException(status_code=500, detail="Internal server error")
