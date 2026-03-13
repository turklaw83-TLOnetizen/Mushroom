# ---- CSRF Protection (Double-Submit Cookie) ---------------------------------
# Prevents cross-site request forgery on mutation endpoints.
#
# How it works:
# 1. Server sets a random CSRF token in a cookie (mc-csrf) on every response
# 2. Frontend JS reads the cookie and includes it as X-CSRF-Token header
# 3. Server verifies the header matches the cookie
#
# This works because:
# - An attacker's page can trigger requests WITH cookies (automatic)
# - But an attacker CANNOT read our cookie (same-origin policy)
# - So they can't send the matching header
#
# Exempt: GET/HEAD/OPTIONS (safe methods) and webhook endpoints (use HMAC auth)

import logging
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "mc-csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 32  # 256 bits of entropy

# Safe methods that don't need CSRF protection
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths exempt from CSRF (webhooks use HMAC, health checks are safe)
EXEMPT_PATHS = {
    "/health",
    "/api/v1/health",
    "/api/v1/webhooks",
    "/api/v1/ws/workers",
    "/api/v1/ws/mock-exam",
}

# Exempt path prefixes (webhooks can have subpaths)
EXEMPT_PREFIXES = [
    "/api/v1/webhooks/",
    "/api/v1/ws/",
]


def _is_exempt(path: str) -> bool:
    """Check if a path is exempt from CSRF verification."""
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def _generate_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_hex(CSRF_TOKEN_LENGTH)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection.

    Sets a CSRF cookie on every response. Verifies the X-CSRF-Token header
    matches the cookie on mutation requests (POST/PUT/PATCH/DELETE).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Safe methods don't need CSRF verification
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            self._set_csrf_cookie(request, response)
            return response

        # Exempt paths (webhooks, websockets, health)
        if _is_exempt(request.url.path):
            return await call_next(request)

        # Only enforce CSRF on /api/ paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Verify CSRF token
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            logger.warning(
                "CSRF: missing token — cookie=%s header=%s path=%s",
                bool(cookie_token), bool(header_token), request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing. Refresh the page and try again."},
            )

        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning(
                "CSRF: token mismatch on %s from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            # Log security event
            try:
                from api.audit import log_security_event
                log_security_event("csrf_violation", {
                    "path": request.url.path,
                    "method": request.method,
                }, request)
            except Exception:
                pass

            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid. Refresh the page and try again."},
            )

        # Token valid — proceed
        response = await call_next(request)
        self._set_csrf_cookie(request, response)
        return response

    def _set_csrf_cookie(self, request: Request, response: Response):
        """Set or refresh the CSRF cookie on every response."""
        existing = request.cookies.get(CSRF_COOKIE_NAME)
        token = existing or _generate_token()

        is_production = os.getenv("ENVIRONMENT", "development") == "production"

        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,  # JS must be able to read this
            secure=is_production,  # HTTPS only in production
            samesite="strict",
            max_age=86400,  # 24 hours
            path="/",
        )
