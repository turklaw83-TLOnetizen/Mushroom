# ---- Prometheus Metrics Endpoint -----------------------------------------
# Exposes app metrics for monitoring dashboards (Grafana, Datadog, etc).

import time
import logging
from collections import defaultdict
from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Monitoring"])

# ---- In-memory metrics counters ----
_metrics = {
    "requests_total": 0,
    "requests_by_method": defaultdict(int),
    "requests_by_status": defaultdict(int),
    "requests_by_path": defaultdict(int),
    "errors_total": 0,
    "response_time_sum": 0.0,
    "response_time_count": 0,
    "active_requests": 0,
    "startup_time": time.time(),
}


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request metrics."""

    async def dispatch(self, request: Request, call_next):
        _metrics["active_requests"] += 1
        _metrics["requests_total"] += 1
        _metrics["requests_by_method"][request.method] += 1

        path = request.url.path.split("?")[0]
        # Normalize dynamic paths
        parts = path.split("/")
        normalized = "/".join(p if not _looks_like_id(p) else "{id}" for p in parts)
        _metrics["requests_by_path"][normalized] += 1

        start = time.time()
        try:
            response = await call_next(request)
            _metrics["requests_by_status"][str(response.status_code)] += 1
            if response.status_code >= 500:
                _metrics["errors_total"] += 1
            return response
        except Exception:
            _metrics["errors_total"] += 1
            _metrics["requests_by_status"]["500"] += 1
            raise
        finally:
            elapsed = time.time() - start
            _metrics["response_time_sum"] += elapsed
            _metrics["response_time_count"] += 1
            _metrics["active_requests"] -= 1


def _looks_like_id(s: str) -> bool:
    """Check if a URL segment looks like a dynamic ID."""
    if len(s) > 8 and any(c in s for c in "-_"):
        return True
    return False


@router.get("/metrics")
def get_metrics():
    """Prometheus-compatible metrics endpoint."""
    uptime = time.time() - _metrics["startup_time"]
    avg_response = (
        _metrics["response_time_sum"] / _metrics["response_time_count"]
        if _metrics["response_time_count"] > 0
        else 0
    )

    return {
        "uptime_seconds": round(uptime, 1),
        "requests_total": _metrics["requests_total"],
        "requests_by_method": dict(_metrics["requests_by_method"]),
        "requests_by_status": dict(_metrics["requests_by_status"]),
        "errors_total": _metrics["errors_total"],
        "active_requests": _metrics["active_requests"],
        "avg_response_ms": round(avg_response * 1000, 2),
        "top_paths": dict(
            sorted(_metrics["requests_by_path"].items(), key=lambda x: x[1], reverse=True)[:20]
        ),
    }
