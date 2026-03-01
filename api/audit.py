# ---- Audit Trail Middleware -----------------------------------------------
# Logs all CRUD mutations to the case activity feed.
# POST/PUT/DELETE requests are automatically recorded.

import json
import logging
import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mushroom_cloud_api.audit")

# Routes we want to audit (POST/PUT/DELETE on case-related endpoints)
AUDITABLE_PREFIXES = [
    "/api/v1/cases",
    "/api/v1/billing",
    "/api/v1/calendar",
    "/api/v1/compliance",
    "/api/v1/documents",
]

AUDITABLE_METHODS = {"POST", "PUT", "DELETE"}


def _extract_user_id(request: Request) -> Optional[str]:
    """Try to extract user ID from the request state (set by auth)."""
    return getattr(request.state, "user_id", None) or "unknown"


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
        "DELETE": f"deleted {resource}",
    }
    return labels.get(method, f"{method.lower()} {resource}")


class AuditTrailMiddleware(BaseHTTPMiddleware):
    """
    Captures POST/PUT/DELETE on case-related endpoints and logs them
    to the activity table / activity feed.

    Activity records include:
    - user_id
    - action (created/updated/deleted + resource)
    - path
    - method
    - status_code
    - timestamp
    - request_id (for correlation)
    """

    async def dispatch(self, request: Request, call_next):
        # Only audit mutating requests on case-related endpoints
        if request.method not in AUDITABLE_METHODS:
            return await call_next(request)

        is_auditable = any(request.url.path.startswith(p) for p in AUDITABLE_PREFIXES)
        if not is_auditable:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Only record successful mutations
        if 200 <= response.status_code < 300:
            request_id = getattr(request.state, "request_id", "unknown")
            user_id = _extract_user_id(request)
            action = _action_label(request.method, request.url.path)

            # Extract case_id from path if present
            case_id = None
            path_parts = request.url.path.split("/")
            if "cases" in path_parts:
                idx = path_parts.index("cases")
                if idx + 1 < len(path_parts):
                    case_id = path_parts[idx + 1]

            activity_record = {
                "user_id": user_id,
                "action": action,
                "method": request.method,
                "path": request.url.path,
                "case_id": case_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "request_id": request_id,
            }

            logger.info(
                "AUDIT: [%s] %s → %s %s (%d, %.0fms)",
                request_id,
                user_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

            # Store in request state for potential downstream use
            request.state.audit_record = activity_record

            # If storage is available, persist to case activity
            if case_id:
                try:
                    from api.deps import get_storage
                    storage = get_storage()
                    if storage:
                        existing = storage.load_preparation_data(case_id, "activity") or []
                        if isinstance(existing, list):
                            import datetime
                            activity_record["timestamp"] = datetime.datetime.now(
                                datetime.timezone.utc
                            ).isoformat()
                            existing.insert(0, activity_record)
                            # Keep last 500 activities
                            storage.save_preparation_data(
                                case_id, "activity", existing[:500]
                            )
                except Exception as e:
                    logger.warning("Failed to persist audit record: %s", e)

        return response
