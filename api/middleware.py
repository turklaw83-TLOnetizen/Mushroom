# ---- API Middleware -------------------------------------------------------
# Fix #10: Structured error handling
# Fix #11: Request ID + request logging

import logging
import time
import traceback
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mushroom_cloud_api")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Fix #11: Attach a unique request ID to every request.

    - Generates a UUID if the client doesn't send X-Request-ID
    - Adds X-Request-ID to the response headers
    - Stores it on request.state for use in error handlers / logging
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id

        # Log every request (skip health checks to reduce noise)
        if request.url.path != "/api/health":
            logger.info(
                "%s %s → %d (%.0fms) [%s]",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
            )

        return response


async def structured_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Fix #10: Global exception handler for unhandled errors.

    Returns a consistent JSON error response without leaking
    stack traces to the client. Logs the full traceback server-side.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        "Unhandled exception [%s] %s %s: %s\n%s",
        request_id,
        request.method,
        request.url.path,
        str(exc),
        traceback.format_exc(),
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id,
        },
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard security headers on every response:
    - Content-Security-Policy (CSP)
    - X-Content-Type-Options
    - X-Frame-Options
    - Referrer-Policy
    - Permissions-Policy
    """

    CSP = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://clerk.accounts.dev https://*.clerk.accounts.dev https://*.turkclaw.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob: https:",
        "connect-src 'self' https://*.clerk.accounts.dev wss://*.clerk.accounts.dev https://api.clerk.com https://*.turkclaw.net ws://localhost:* http://localhost:*",
        "frame-src 'self' https://clerk.accounts.dev https://*.turkclaw.net",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "worker-src 'self' blob:",
        "manifest-src 'self'",
    ])

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = self.CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), bluetooth=(), serial=(), hid=(), accelerometer=(), gyroscope=(), magnetometer=()"

        # Prevent browsers from caching sensitive API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response
