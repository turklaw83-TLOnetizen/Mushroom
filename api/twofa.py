# ---- 2FA Enforcement Middleware ------------------------------------------
# Requires Clerk users with the 'attorney' or 'admin' role to have 2FA enabled.

import logging
import os
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

ENFORCE_2FA = os.getenv("ENFORCE_2FA", "false").lower() == "true"
EXEMPT_PATHS = ["/docs", "/redoc", "/openapi.json", "/api/v1/health", "/api/v1/webhooks"]


async def check_2fa(request: Request):
    """
    Dependency: verify that attorney/admin users have 2FA enabled.
    Designed to be used as a FastAPI dependency on sensitive routes.
    """
    if not ENFORCE_2FA:
        return

    # Skip for exempt paths
    if any(request.url.path.startswith(p) for p in EXEMPT_PATHS):
        return

    # Get user claims from Clerk JWT (set by auth middleware)
    user = getattr(request.state, "user", None)
    if not user:
        return

    role = getattr(user, "role", "") or ""
    has_2fa = getattr(user, "two_factor_enabled", False)

    if role in ("attorney", "admin", "partner") and not has_2fa:
        logger.warning("2FA not enabled for %s user %s", role, getattr(user, "id", "unknown"))
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Two-factor authentication required",
                "message": "Your account role requires 2FA. Please enable it in your Clerk account settings.",
                "action": "enable_2fa",
            },
        )
