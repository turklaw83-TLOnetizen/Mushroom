"""
stripe_pay.py -- Stripe Payment Integration
Create payment links, checkout sessions, and handle webhooks.
Uses Stripe Connect to let each firm manage their own account.

Env vars:
  STRIPE_SECRET_KEY      — sk_test_... or sk_live_...
  STRIPE_WEBHOOK_SECRET  — whsec_...
  STRIPE_PUBLIC_KEY      — pk_test_... or pk_live_... (optional, for frontend)
  APP_BASE_URL           — e.g. https://turkclaw.net (for redirect URLs)
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# -- Paths -----------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_COMMS_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "comms")
_STRIPE_FILE = os.path.join(_COMMS_DIR, "stripe_payments.json")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")


def _ensure_dir():
    os.makedirs(_COMMS_DIR, exist_ok=True)


def _load_stripe_data() -> Dict:
    _ensure_dir()
    if os.path.exists(_STRIPE_FILE):
        with open(_STRIPE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"payment_links": [], "checkout_sessions": [], "webhook_events": []}


def _save_stripe_data(data: Dict):
    _ensure_dir()
    with open(_STRIPE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_stripe():
    """Lazy-import stripe and configure API key. Returns the stripe module."""
    try:
        import stripe
    except ImportError:
        raise RuntimeError(
            "stripe package not installed. Run: pip install stripe"
        )
    if not STRIPE_SECRET_KEY:
        raise RuntimeError(
            "STRIPE_SECRET_KEY not set. Add it to your .env file."
        )
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


# ===================================================================
#  1.  PAYMENT LINKS — reusable payment URLs per client/plan
# ===================================================================

def create_payment_link(
    client_id: str,
    plan_id: str,
    amount_cents: int,
    description: str = "Payment",
    client_name: str = "",
    client_email: str = "",
) -> Dict:
    """
    Create a Stripe Payment Link for a specific client payment.
    Returns {link_id, url, amount, status, created_at, ...}
    """
    stripe = _get_stripe()

    # Create a Stripe Price (one-time)
    price = stripe.Price.create(
        unit_amount=amount_cents,
        currency="usd",
        product_data={
            "name": description,
        },
    )

    # Create Payment Link
    link_params = {
        "line_items": [{"price": price.id, "quantity": 1}],
        "metadata": {
            "client_id": client_id,
            "plan_id": plan_id,
            "client_name": client_name,
            "source": "mushroom_cloud",
        },
        "after_completion": {
            "type": "redirect",
            "redirect": {"url": f"{APP_BASE_URL}/payment-success"},
        },
    }

    # Pre-fill customer email if available
    if client_email:
        link_params["metadata"]["client_email"] = client_email

    payment_link = stripe.PaymentLink.create(**link_params)

    # Save record locally
    record = {
        "id": f"spl_{uuid.uuid4().hex[:8]}",
        "stripe_link_id": payment_link.id,
        "stripe_price_id": price.id,
        "url": payment_link.url,
        "client_id": client_id,
        "plan_id": plan_id,
        "client_name": client_name,
        "amount_cents": amount_cents,
        "amount": round(amount_cents / 100, 2),
        "description": description,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "paid_at": None,
        "payment_intent_id": None,
    }

    data = _load_stripe_data()
    data["payment_links"].append(record)
    _save_stripe_data(data)

    logger.info(
        "Created Stripe payment link: %s for client %s ($%.2f)",
        payment_link.url, client_id, amount_cents / 100,
    )
    return record


# ===================================================================
#  2.  CHECKOUT SESSIONS — one-time checkout pages
# ===================================================================

def create_checkout_session(
    client_id: str,
    plan_id: str,
    amount_cents: int,
    description: str = "Payment",
    client_name: str = "",
    client_email: str = "",
    success_url: str = "",
    cancel_url: str = "",
) -> Dict:
    """
    Create a Stripe Checkout Session for one-time payment.
    Returns {session_id, url, amount, status, ...}
    """
    stripe = _get_stripe()

    params = {
        "payment_method_types": ["card", "us_bank_account"],
        "mode": "payment",
        "line_items": [{
            "price_data": {
                "currency": "usd",
                "unit_amount": amount_cents,
                "product_data": {"name": description},
            },
            "quantity": 1,
        }],
        "success_url": success_url or f"{APP_BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": cancel_url or f"{APP_BASE_URL}/payment-cancelled",
        "metadata": {
            "client_id": client_id,
            "plan_id": plan_id,
            "client_name": client_name,
            "source": "mushroom_cloud",
        },
    }

    if client_email:
        params["customer_email"] = client_email

    session = stripe.checkout.Session.create(**params)

    record = {
        "id": f"scs_{uuid.uuid4().hex[:8]}",
        "stripe_session_id": session.id,
        "url": session.url,
        "client_id": client_id,
        "plan_id": plan_id,
        "client_name": client_name,
        "amount_cents": amount_cents,
        "amount": round(amount_cents / 100, 2),
        "description": description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "paid_at": None,
        "payment_intent_id": None,
    }

    data = _load_stripe_data()
    data["checkout_sessions"].append(record)
    _save_stripe_data(data)

    logger.info(
        "Created Stripe checkout session: %s for client %s ($%.2f)",
        session.id, client_id, amount_cents / 100,
    )
    return record


# ===================================================================
#  3.  WEBHOOK HANDLING — auto-record payments on completion
# ===================================================================

def handle_webhook_event(payload: bytes, sig_header: str) -> Dict:
    """
    Verify and process a Stripe webhook event.
    Handles: checkout.session.completed, payment_intent.succeeded
    Returns {event_type, handled, details}
    """
    stripe = _get_stripe()

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info("Stripe webhook: %s", event_type)

    result = {
        "event_type": event_type,
        "handled": False,
        "details": {},
    }

    # -- Save event for audit --
    data = _load_stripe_data()
    data["webhook_events"].append({
        "id": event.get("id", ""),
        "type": event_type,
        "received_at": datetime.now().isoformat(),
        "metadata": event_data.get("metadata", {}),
    })
    # Keep only last 500 events
    if len(data["webhook_events"]) > 500:
        data["webhook_events"] = data["webhook_events"][-500:]

    if event_type == "checkout.session.completed":
        result = _handle_checkout_completed(event_data, data)
    elif event_type == "payment_intent.succeeded":
        result = _handle_payment_succeeded(event_data, data)

    _save_stripe_data(data)
    return result


def _handle_checkout_completed(session_data: Dict, data: Dict) -> Dict:
    """Process completed checkout session — record payment."""
    metadata = session_data.get("metadata", {})
    client_id = metadata.get("client_id", "")
    plan_id = metadata.get("plan_id", "")
    client_name = metadata.get("client_name", "")

    amount_cents = session_data.get("amount_total", 0)
    payment_intent_id = session_data.get("payment_intent", "")
    session_id = session_data.get("id", "")

    # Update local checkout session record
    for s in data.get("checkout_sessions", []):
        if s.get("stripe_session_id") == session_id:
            s["status"] = "paid"
            s["paid_at"] = datetime.now().isoformat()
            s["payment_intent_id"] = payment_intent_id
            break

    # Auto-record the payment against the client's plan
    payment_id = None
    if client_id and plan_id and amount_cents > 0:
        payment_id = _record_stripe_payment(
            client_id=client_id,
            plan_id=plan_id,
            amount=round(amount_cents / 100, 2),
            payment_intent_id=payment_intent_id,
            client_name=client_name,
        )

    return {
        "event_type": "checkout.session.completed",
        "handled": True,
        "details": {
            "session_id": session_id,
            "client_id": client_id,
            "plan_id": plan_id,
            "amount": round(amount_cents / 100, 2),
            "payment_id": payment_id,
        },
    }


def _handle_payment_succeeded(intent_data: Dict, data: Dict) -> Dict:
    """Process succeeded payment intent — record if from our system."""
    metadata = intent_data.get("metadata", {})
    source = metadata.get("source", "")

    # Only handle payments originating from our system
    if source != "mushroom_cloud":
        return {
            "event_type": "payment_intent.succeeded",
            "handled": False,
            "details": {"reason": "not from mushroom_cloud"},
        }

    client_id = metadata.get("client_id", "")
    plan_id = metadata.get("plan_id", "")
    client_name = metadata.get("client_name", "")
    amount_cents = intent_data.get("amount_received", 0)
    payment_intent_id = intent_data.get("id", "")

    payment_id = None
    if client_id and plan_id and amount_cents > 0:
        payment_id = _record_stripe_payment(
            client_id=client_id,
            plan_id=plan_id,
            amount=round(amount_cents / 100, 2),
            payment_intent_id=payment_intent_id,
            client_name=client_name,
        )

    return {
        "event_type": "payment_intent.succeeded",
        "handled": True,
        "details": {
            "client_id": client_id,
            "plan_id": plan_id,
            "amount": round(amount_cents / 100, 2),
            "payment_id": payment_id,
        },
    }


def _record_stripe_payment(
    client_id: str,
    plan_id: str,
    amount: float,
    payment_intent_id: str = "",
    client_name: str = "",
) -> Optional[str]:
    """Record a Stripe payment against a client's payment plan."""
    try:
        from core.billing import record_plan_payment

        payment_id = record_plan_payment(
            client_id=client_id,
            plan_id=plan_id,
            amount=amount,
            method="stripe",
            payer_name=client_name,
            note=f"[Stripe] Payment Intent: {payment_intent_id}",
            date_str=datetime.now().strftime("%Y-%m-%d"),
            recorded_by="Stripe Webhook",
        )
        if payment_id:
            logger.info(
                "Auto-recorded Stripe payment: $%.2f for client %s (plan %s)",
                amount, client_id, plan_id,
            )
            # Auto-queue a payment receipt communication
            try:
                from core.comms import add_to_queue
                add_to_queue(
                    client_id=client_id,
                    trigger_type="payment_received",
                    subject=f"Payment Received — ${amount:.2f}",
                    body_html=f"<p>Thank you for your payment of <strong>${amount:.2f}</strong>.</p><p>This payment has been recorded to your account.</p>",
                    body_sms=f"Payment of ${amount:.2f} received. Thank you!",
                    trigger_id=payment_intent_id or payment_id,
                    channel="email",
                    priority="low",
                    metadata={
                        "client_name": client_name,
                        "amount": amount,
                        "payment_id": payment_id,
                        "payment_intent_id": payment_intent_id,
                    },
                )
            except Exception:
                logger.warning("Failed to queue payment receipt comm")
        return payment_id
    except Exception:
        logger.exception("Failed to auto-record Stripe payment")
        return None


# ===================================================================
#  4.  QUERIES — list payment links and sessions
# ===================================================================

def get_payment_links(client_id: str = "") -> List[Dict]:
    """List Stripe payment links, optionally filtered by client."""
    data = _load_stripe_data()
    links = data.get("payment_links", [])
    if client_id:
        links = [l for l in links if l.get("client_id") == client_id]
    return sorted(links, key=lambda l: l.get("created_at", ""), reverse=True)


def get_checkout_sessions(client_id: str = "") -> List[Dict]:
    """List checkout sessions, optionally filtered by client."""
    data = _load_stripe_data()
    sessions = data.get("checkout_sessions", [])
    if client_id:
        sessions = [s for s in sessions if s.get("client_id") == client_id]
    return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)


def get_stripe_config() -> Dict:
    """Return public Stripe configuration (no secrets)."""
    return {
        "configured": bool(STRIPE_SECRET_KEY),
        "public_key": STRIPE_PUBLIC_KEY,
        "webhook_configured": bool(STRIPE_WEBHOOK_SECRET),
        "base_url": APP_BASE_URL,
    }


def get_recent_webhook_events(limit: int = 20) -> List[Dict]:
    """Return recent webhook events for debugging."""
    data = _load_stripe_data()
    events = data.get("webhook_events", [])
    return events[-limit:] if events else []
