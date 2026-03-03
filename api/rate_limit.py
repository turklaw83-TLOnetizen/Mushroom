# ---- Rate Limiting Middleware ---------------------------------------------
# Per-IP sliding window rate limiter.
# Configurable via RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW_SECONDS env vars.

import os
import time
import logging
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configuration
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "600"))  # per window (generous for dev)
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Paths exempt from rate limiting
EXEMPT_PATHS = {"/health", "/api/v1/ws/workers", "/api/v1/health", "/docs", "/redoc", "/openapi.json", "/"}

# IPs exempt from rate limiting (localhost in dev)
EXEMPT_IPS = {"127.0.0.1", "::1", "localhost"}


class _SlidingWindow:
    """Thread-safe sliding window counter per key."""

    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, now: float) -> tuple[bool, int]:
        """Check if a request is allowed. Returns (allowed, remaining)."""
        with self._lock:
            timestamps = self._buckets[key]
            cutoff = now - WINDOW_SECONDS
            # Prune expired timestamps
            timestamps[:] = [t for t in timestamps if t > cutoff]
            remaining = MAX_REQUESTS - len(timestamps)
            if remaining <= 0:
                return False, 0
            timestamps.append(now)
            return True, remaining - 1

    def cleanup(self, now: float):
        """Remove stale entries to prevent memory leaks."""
        with self._lock:
            cutoff = now - WINDOW_SECONDS * 2
            stale = [k for k, v in self._buckets.items() if not v or v[-1] < cutoff]
            for k in stale:
                del self._buckets[k]


_window = _SlidingWindow()
_last_cleanup = time.time()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter.

    Returns 429 with Retry-After header when limit is exceeded.
    """

    async def dispatch(self, request: Request, call_next):
        global _last_cleanup

        path = request.url.path
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Use forwarded IP if behind proxy, else client IP
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host
            if request.client
            else "unknown"
        )

        # Skip rate limiting for exempt IPs (localhost in dev)
        if client_ip in EXEMPT_IPS:
            return await call_next(request)

        now = time.time()

        # Periodic cleanup (every 5 minutes)
        if now - _last_cleanup > 300:
            _window.cleanup(now)
            _last_cleanup = now

        allowed, remaining = _window.is_allowed(client_ip, now)

        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "Retry-After": str(WINDOW_SECONDS),
                    "X-RateLimit-Limit": str(MAX_REQUESTS),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + WINDOW_SECONDS)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
