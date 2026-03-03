"""Unified error response mapping for custom exceptions."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import (
    AuthorizationError,
    CaseNotFoundError,
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    MushroomCloudError,
    PrepNotFoundError,
    StorageError,
    ValidationError,
)

logger = logging.getLogger(__name__)


async def mushroom_cloud_error_handler(
    request: Request, exc: MushroomCloudError
) -> JSONResponse:
    """Map domain exceptions to proper HTTP status codes."""
    request_id = getattr(request.state, "request_id", "unknown")

    status_map = {
        CaseNotFoundError: 404,
        PrepNotFoundError: 404,
        ValidationError: 422,
        AuthorizationError: 403,
        LLMRateLimitError: 429,
        LLMAuthError: 502,
        LLMProviderError: 502,
        StorageError: 500,
    }

    status_code = status_map.get(type(exc), 500)
    error_type = type(exc).__name__

    if status_code >= 500:
        logger.exception("Server error [%s] %s: %s", request_id, error_type, exc)
    else:
        logger.warning("Client error [%s] %s: %s", request_id, error_type, exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "detail": str(exc),
            "request_id": request_id,
        },
    )
