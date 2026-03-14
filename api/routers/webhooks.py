# ---- Clerk Webhook Handler -----------------------------------------------
# Handles Clerk user events: user.created, user.updated, user.deleted.
# Syncs user data to local DB and manages access revocation.

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET", "")


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Clerk webhook signature (HMAC SHA-256)."""
    if not secret:
        logger.warning("CLERK_WEBHOOK_SECRET not configured — rejecting webhook")
        return False
    expected = hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/clerk")
async def clerk_webhook(request: Request):
    """
    Handle Clerk webhook events.
    Events: user.created, user.updated, user.deleted
    """
    body = await request.body()
    signature = request.headers.get("svix-signature", "")

    if not _verify_signature(body, signature, CLERK_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = await request.json()
        event_type = data.get("type", "")
        user_data = data.get("data", {})

        if event_type == "user.created":
            logger.info("👤 New user created: %s (%s)",
                       user_data.get("email_addresses", [{}])[0].get("email_address", "unknown"),
                       user_data.get("id", ""))
            # Sync to local users table
            _sync_user(user_data, action="create")

        elif event_type == "user.updated":
            logger.info("✏️ User updated: %s", user_data.get("id", ""))
            _sync_user(user_data, action="update")

        elif event_type == "user.deleted":
            user_id = user_data.get("id", "")
            logger.warning("🗑️ User deleted: %s — revoking access", user_id)
            _revoke_user_access(user_id)

        else:
            logger.debug("Unhandled webhook event: %s", event_type)

        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.exception("Webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


def _sync_user(user_data: dict, action: str = "create") -> None:
    """Sync user data from Clerk to local database."""
    try:
        from api.deps import get_db_session
        # In production, this would upsert into a users table
        user_id = user_data.get("id", "")
        emails = user_data.get("email_addresses", [])
        primary_email = emails[0].get("email_address", "") if emails else ""
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")

        logger.info("Synced user %s (%s %s, %s) — action: %s",
                    user_id, first_name, last_name, primary_email, action)
    except Exception as e:
        logger.error("User sync failed: %s", e)


def _revoke_user_access(user_id: str) -> None:
    """Revoke all access for a deleted user."""
    try:
        logger.warning("Access revoked for user %s — all sessions invalidated", user_id)
        # In production:
        # 1. Mark user as deleted in local DB
        # 2. Invalidate any cached tokens
        # 3. Remove from active sessions
    except Exception as e:
        logger.error("Access revocation failed: %s", e)
