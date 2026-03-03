"""Prometheus metrics middleware — instruments all HTTP requests."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.prometheus_metrics import http_requests_total, http_request_duration


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request count and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start

        path = self._normalize_path(request.url.path)
        method = request.method
        status = str(response.status_code)

        http_requests_total.labels(method=method, path=path, status_code=status).inc()
        http_request_duration.labels(method=method, path=path).observe(duration)

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Collapse dynamic segments to reduce cardinality."""
        parts = path.split("/")
        normalized = []
        for i, part in enumerate(parts):
            # Replace UUIDs and hex IDs with placeholder
            if len(part) >= 8 and all(c in "0123456789abcdef-" for c in part.lower()):
                normalized.append("{id}")
            else:
                normalized.append(part)
        return "/".join(normalized)
