# ---- Audit Trail Middleware -----------------------------------------------
# Logs ALL authenticated mutations + security events to structured audit log.
#
# Covers: every POST/PUT/PATCH/DELETE on /api/v1, plus failed auth attempts.
# Persists to case activity feed (for case-related ops) and a global audit log file.

import datetime
import json
import logging
import os
import time
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mushroom_cloud_api.audit")

# All API mutations are auditable (not just 5 prefixes)
AUDITABLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to skip (health checks, metrics, websocket upgrades)
SKIP_PATHS = {"/health", "/api/v1/health", "/api/v1/metrics", "/api/v1/ws/workers"}

# Global audit log file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_LOG_DIR = _PROJECT_ROOT / "data" / "audit_logs"
_audit_lock = Lock()


def _ensure_audit_dir():
    """Create audit log directory if missing."""
    _AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_audit_log(record: dict):
    """Append a JSON record to the daily audit log file."""
    try:
        _ensure_audit_dir()
        today = datetime.date.today().isoformat()
        log_file = _AUDIT_LOG_DIR / f"audit-{today}.jsonl"
        line = json.dumps(record, default=str) + "\n"
        with _audit_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        logger.warning("Failed to write audit log: %s", e)


def _extract_user_id(request: Request) -> Optional[str]:
    """Try to extract user ID from the request state (set by auth)."""
    return getattr(request.state, "user_id", None) or "unknown"


def _extract_client_ip(request: Request) -> str:
    """Extract real client IP, respecting proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _action_label(method: str, path: str) -> str:
    """Generate a human-readable action label from the HTTP method + path."""
    parts = path.strip("/").split("/")
    resource = parts[-1] if parts else "unknown"

    # Handle index-based resources like /witnesses/0
    try:
        int(resource)
        resource = parts[-2] if len(parts) >= 2 else resource
    except ValueError:
        pass

    labels = {
        "POST": f"created {resource}",
        "PUT": f"updated {resource}",
        "PATCH": f"updated {resource}",
        "DELETE": f"deleted {resource}",
    }
    return labels.get(method, f"{method.lower()} {resource}")


def log_security_event(event_type: str, details: dict, request: Request = None):
    """
    Log a security-relevant event (failed auth, rate limit, suspicious input).

    Call this from auth handlers, rate limiters, etc.
    """
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": event_type,
        "severity": "warning",
        **details,
    }
    if request:
        record["client_ip"] = _extract_client_ip(request)
        record["path"] = str(request.url.path)
        record["method"] = request.method
        record["user_agent"] = request.headers.get("User-Agent", "")[:200]

    logger.warning("SECURITY: [%s] %s", event_type, json.dumps(details, default=str))
    _write_audit_log(record)


class AuditTrailMiddleware(BaseHTTPMiddleware):
    """
    Captures ALL API mutations and logs them to:
    1. Structured log (stdout for container aggregation)
    2. Daily JSONL audit file (data/audit_logs/audit-YYYY-MM-DD.jsonl)
    3. Case activity feed (for case-related operations)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-mutation requests and noise paths
        if request.method not in AUDITABLE_METHODS or path in SKIP_PATHS:
            return await call_next(request)

        # Only audit /api/ paths
        if not path.startswith("/api/"):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        request_id = getattr(request.state, "request_id", "unknown")
        user_id = _extract_user_id(request)
        client_ip = _extract_client_ip(request)
        action = _action_label(request.method, path)

        # Extract case_id from path if present
        case_id = None
        path_parts = path.split("/")
        if "cases" in path_parts:
            idx = path_parts.index("cases")
            if idx + 1 < len(path_parts):
                case_id = path_parts[idx + 1]

        record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event_type": "api_mutation",
            "request_id": request_id,
            "user_id": user_id,
            "client_ip": client_ip,
            "action": action,
            "method": request.method,
            "path": path,
            "case_id": case_id,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 1),
            "user_agent": request.headers.get("User-Agent", "")[:200],
        }

        # Log failed mutations at warning level (potential attack indicators)
        if response.status_code >= 400:
            record["severity"] = "warning"
            logger.warning(
                "AUDIT: [%s] %s → %s %s (%d, %.0fms) [FAILED] from %s",
                request_id, user_id, request.method, path,
                response.status_code, duration_ms, client_ip,
            )
        else:
            record["severity"] = "info"
            logger.info(
                "AUDIT: [%s] %s → %s %s (%d, %.0fms)",
                request_id, user_id, request.method, path,
                response.status_code, duration_ms,
            )

        # Write to daily audit log file
        _write_audit_log(record)

        # Store in request state for downstream use
        request.state.audit_record = record

        # Persist to case activity feed (successful mutations only)
        if case_id and 200 <= response.status_code < 300:
            try:
                from api.deps import get_storage
                storage = get_storage()
                if storage:
                    existing = storage.load_preparation_data(case_id, "activity") or []
                    if isinstance(existing, list):
                        existing.insert(0, record)
                        storage.save_preparation_data(
                            case_id, "activity", existing[:500]
                        )
            except Exception as e:
                logger.warning("Failed to persist audit record: %s", e)

        return response
