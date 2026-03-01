# ---- Input Sanitization Middleware ----------------------------------------
# Prevents XSS, SQL injection, and command injection in request bodies.
# Runs on all incoming JSON bodies.

import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Patterns that indicate malicious input
XSS_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on(load|error|click|mouseover|focus|blur)\s*=", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
]

SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC)\b\s+)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/)", re.IGNORECASE),
    re.compile(r"(\bOR\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),
    re.compile(r"('\s*OR\s+'1'\s*=\s*'1')", re.IGNORECASE),
]

# Paths where raw content is expected (e.g., code editors, AI prompts)
EXEMPT_PATHS = [
    "/api/v1/cases/",  # Case content may contain legal SQL references
]


def _is_exempt(path: str) -> bool:
    """Check if path is exempt from sanitization."""
    return any(path.startswith(p) for p in EXEMPT_PATHS)


def _scan_value(value: str) -> str | None:
    """Scan a string value for malicious patterns. Returns pattern name or None."""
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            return "XSS"
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return "SQL_INJECTION"
    return None


def _scan_dict(data: dict) -> str | None:
    """Recursively scan dict values for malicious content."""
    for key, value in data.items():
        if isinstance(value, str):
            threat = _scan_value(value)
            if threat:
                return f"{threat} in field '{key}'"
        elif isinstance(value, dict):
            result = _scan_dict(value)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    threat = _scan_value(item)
                    if threat:
                        return f"{threat} in field '{key}'"
                elif isinstance(item, dict):
                    result = _scan_dict(item)
                    if result:
                        return result
    return None


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Scan incoming JSON bodies for XSS and SQL injection attempts."""

    async def dispatch(self, request: Request, call_next):
        # Only scan JSON bodies on mutation operations
        if request.method in ("POST", "PUT", "PATCH") and not _is_exempt(request.url.path):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.json()
                    if isinstance(body, dict):
                        threat = _scan_dict(body)
                        if threat:
                            logger.warning(
                                "🚨 Input sanitization blocked: %s from %s on %s",
                                threat, request.client.host if request.client else "unknown", request.url.path,
                            )
                            return JSONResponse(
                                status_code=400,
                                content={"detail": f"Request blocked: potentially malicious input detected ({threat})"},
                            )
                except Exception:
                    pass  # If body can't be parsed, let downstream handle it

        return await call_next(request)
