# ---- Access Control Configuration ----------------------------------------
# Founder/admin account lockdown.
# Only the initial admin can approve new accounts.

import logging
import os
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

# The founding admin account — the ONLY account that can approve new users.
INITIAL_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "daniel@turklaylaw.com")

# Approved emails — loaded from DB in production, hardcoded for bootstrap.
# New users must be approved by the admin before gaining access.
APPROVED_EMAILS: set[str] = {
    INITIAL_ADMIN_EMAIL,
}


def is_approved(email: str) -> bool:
    """Check if an email is in the approved list."""
    return email.lower() in {e.lower() for e in APPROVED_EMAILS}


def is_admin(email: str) -> bool:
    """Check if an email is the initial admin."""
    return email.lower() == INITIAL_ADMIN_EMAIL.lower()


def approve_user(email: str, approved_by: str):
    """Approve a new user (must be done by admin)."""
    if not is_admin(approved_by):
        raise PermissionError("Only the initial admin can approve new users.")
    APPROVED_EMAILS.add(email.lower())
    logger.info("User %s approved by %s", email, approved_by)


def revoke_user(email: str, revoked_by: str):
    """Revoke a user's access (must be done by admin)."""
    if not is_admin(revoked_by):
        raise PermissionError("Only the initial admin can revoke users.")
    if email.lower() == INITIAL_ADMIN_EMAIL.lower():
        raise PermissionError("Cannot revoke the initial admin account.")
    APPROVED_EMAILS.discard(email.lower())
    logger.info("User %s revoked by %s", email, revoked_by)


async def require_approved_user(request: Request):
    """
    FastAPI dependency: ensure the current user is in the approved list.
    Must run AFTER Clerk auth so request.state.user is populated.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    email = getattr(user, "email", "") or ""
    if not email:
        raise HTTPException(status_code=403, detail="No email associated with account")

    if not is_approved(email):
        logger.warning("Unauthorized access attempt: %s", email)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Account not approved",
                "message": "Your account has not been approved. Contact daniel@turklaylaw.com for access.",
                "admin_contact": INITIAL_ADMIN_EMAIL,
            },
        )
