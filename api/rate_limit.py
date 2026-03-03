# ---- Rate Limiting Middleware ---------------------------------------------
# Per-IP sliding window rate limiter with per-endpoint tiered limits.
# Configurable via RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW_SECONDS env vars.

import os
import re
import time
import logging
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configuration — global defaults
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))  # per window
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Paths exempt from rate limiting
EXEMPT_PATHS = {"/health", "/api/v1/ws/workers", "/api/v1/health"}

# ---------------------------------------------------------------------------
# Per-endpoint rate limits for expensive AI calls.
# Maps a path pattern (with {} as wildcard for path segments like case IDs)
# to a tuple of (max_requests, window_seconds).
# ---------------------------------------------------------------------------
ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/cases/{}/chat/stream": (10, 60),       # 10 per minute for chat streaming
    "/api/v1/cases/{}/analysis/start": (5, 60),      # 5 per minute for analysis starts
    "/api/v1/cases/{}/analysis/ingestion": (5, 60),  # 5 per minute for ingestion
    "/api/v1/documents/outline": (10, 60),            # 10 per minute for doc outline gen
    "/api/v1/documents/draft-section": (10, 60),      # 10 per minute for section drafting
    "/api/v1/documents/review": (5, 60),              # 5 per minute for AI review
}

# Pre-compile patterns: convert "/api/v1/cases/{}/chat/stream" into a regex
# that matches "/api/v1/cases/<any-segment>/chat/stream" (and optional trailing slash).
_COMPILED_ENDPOINT_PATTERNS: list[tuple[re.Pattern, str, int, int]] = []


def _compile_endpoint_patterns():
    """Build regex patterns from ENDPOINT_LIMITS on first use."""
    if _COMPILED_ENDPOINT_PATTERNS:
        return
    for pattern_str, (max_req, window) in ENDPOINT_LIMITS.items():
        # Escape literal regex chars, then replace escaped \{\} with [^/]+
        escaped = re.escape(pattern_str)
        regex_str = escaped.replace(r"\{\}", r"[^/]+")
        # Match with optional trailing slash
        compiled = re.compile(f"^{regex_str}/?$")
        _COMPILED_ENDPOINT_PATTERNS.append((compiled, pattern_str, max_req, window))


def match_endpoint(path: str) -> tuple[str, int, int] | None:
    """
    Check if a request path matches any endpoint-specific rate limit pattern.

    Returns (pattern_name, max_requests, window_seconds) or None.
    """
    _compile_endpoint_patterns()
    for compiled, pattern_str, max_req, window in _COMPILED_ENDPOINT_PATTERNS:
        if compiled.match(path):
            return pattern_str, max_req, window
    return None


class _SlidingWindow:
    """Thread-safe sliding window counter per key."""

    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(
        self, key: str, now: float, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Check if a request is allowed. Returns (allowed, remaining)."""
        with self._lock:
            timestamps = self._buckets[key]
            cutoff = now - window_seconds
            # Prune expired timestamps
            timestamps[:] = [t for t in timestamps if t > cutoff]
            remaining = max_requests - len(timestamps)
            if remaining <= 0:
                return False, 0
            timestamps.append(now)
            return True, remaining - 1

    def cleanup(self, now: float, window_seconds: int = WINDOW_SECONDS):
        """Remove stale entries to prevent memory leaks."""
        with self._lock:
            cutoff = now - window_seconds * 2
            stale = [k for k, v in self._buckets.items() if not v or v[-1] < cutoff]
            for k in stale:
                del self._buckets[k]


# Global sliding window for general rate limiting
_global_window = _SlidingWindow()
# Separate sliding window for per-endpoint rate limiting
_endpoint_window = _SlidingWindow()
_last_cleanup = time.time()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter with per-endpoint tiered limits.

    Expensive AI endpoints (chat streaming, analysis, document drafting) have
    stricter per-endpoint limits. All other endpoints use the global limit.
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

        now = time.time()

        # Periodic cleanup (every 5 minutes)
        if now - _last_cleanup > 300:
            _global_window.cleanup(now, WINDOW_SECONDS)
            _endpoint_window.cleanup(now)
            _last_cleanup = now

        # --- Per-endpoint rate limit check ---
        endpoint_match = match_endpoint(path)
        if endpoint_match:
            ep_pattern, ep_max, ep_window = endpoint_match
            ep_key = f"{client_ip}:{ep_pattern}"
            ep_allowed, ep_remaining = _endpoint_window.is_allowed(
                ep_key, now, ep_max, ep_window
            )
            if not ep_allowed:
                logger.warning(
                    "Endpoint rate limit exceeded for %s on %s (pattern: %s)",
                    client_ip,
                    path,
                    ep_pattern,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Rate limit exceeded for endpoint {ep_pattern}. "
                            f"Max {ep_max} requests per {ep_window}s. "
                            "Please try again later."
                        )
                    },
                    headers={
                        "Retry-After": str(ep_window),
                        "X-RateLimit-Limit": str(ep_max),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(now + ep_window)),
                        "X-RateLimit-Scope": "endpoint",
                    },
                )

        # --- Global rate limit check (applies to all endpoints) ---
        allowed, remaining = _global_window.is_allowed(
            client_ip, now, MAX_REQUESTS, WINDOW_SECONDS
        )

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
                    "X-RateLimit-Scope": "global",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if endpoint_match:
            _, ep_max, _ = endpoint_match
            response.headers["X-RateLimit-Endpoint-Limit"] = str(ep_max)
            response.headers["X-RateLimit-Endpoint-Remaining"] = str(ep_remaining)
        return response
