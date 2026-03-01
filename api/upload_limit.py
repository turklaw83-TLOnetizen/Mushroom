# ---- Upload Size Middleware -----------------------------------------------
# Enforces 20GB max upload size at the application layer.
# Works alongside Nginx client_max_body_size.

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Default 20GB
DEFAULT_MAX_SIZE = 20 * 1024 * 1024 * 1024


class UploadSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding the configured limit."""

    def __init__(self, app, max_size: int = DEFAULT_MAX_SIZE):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            gb = self.max_size / (1024 ** 3)
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"File too large. Maximum upload size is {gb:.0f}GB.",
                    "max_bytes": self.max_size,
                },
            )
        return await call_next(request)
