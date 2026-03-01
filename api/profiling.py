"""Performance profiling middleware — log slow requests."""

import logging
import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

SLOW_THRESHOLD = float(os.getenv("SLOW_REQUEST_THRESHOLD_SECONDS", "2.0"))
ENABLED = os.getenv("ENABLE_PROFILING", "").lower() in ("true", "1", "yes")

# In-memory performance data
_perf_data: dict[str, list[float]] = defaultdict(list)
MAX_SAMPLES = 500


class ProfilingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not ENABLED:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        path = request.url.path
        method = request.method
        key = f"{method} {path}"

        # Store sample
        samples = _perf_data[key]
        samples.append(duration)
        if len(samples) > MAX_SAMPLES:
            _perf_data[key] = samples[-MAX_SAMPLES:]

        # Log slow requests
        if duration > SLOW_THRESHOLD:
            logger.warning(
                "SLOW REQUEST: %s %s took %.2fs (threshold: %.1fs)",
                method, path, duration, SLOW_THRESHOLD,
            )

        return response


def get_performance_summary() -> dict:
    """Return performance summary for all endpoints."""
    summary = {}
    for key, samples in _perf_data.items():
        if not samples:
            continue
        sorted_s = sorted(samples)
        n = len(sorted_s)
        summary[key] = {
            "count": n,
            "avg_ms": round(sum(sorted_s) / n * 1000, 1),
            "p50_ms": round(sorted_s[n // 2] * 1000, 1),
            "p95_ms": round(sorted_s[int(n * 0.95)] * 1000, 1),
            "p99_ms": round(sorted_s[int(n * 0.99)] * 1000, 1) if n > 10 else None,
            "max_ms": round(sorted_s[-1] * 1000, 1),
        }
    return summary
