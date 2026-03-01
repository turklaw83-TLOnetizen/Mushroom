# ---- Response Envelope ---------------------------------------------------
# Standardized response wrapper for all API endpoints.
# Usage:
#   return envelope(data=items, meta={"page": 1, "total": 50})
#   return envelope(data={"id": "abc"}, message="Created")
#   return envelope(error="Not found", status=404)

from typing import Any, Optional
from fastapi.responses import JSONResponse


def envelope(
    data: Any = None,
    meta: Optional[dict] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    status: int = 200,
) -> JSONResponse:
    """
    Standard API response envelope.

    Success: {"data": ..., "meta": ..., "message": ...}
    Error:   {"error": "...", "data": null}

    Existing endpoints can adopt this incrementally.
    """
    body: dict[str, Any] = {"data": data}

    if meta:
        body["meta"] = meta
    if message:
        body["message"] = message
    if error:
        body["error"] = error
        body["data"] = None

    return JSONResponse(content=body, status_code=status)
