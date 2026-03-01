# ---- Shared API Schemas --------------------------------------------------
# Reusable Pydantic models across routers.
# Fix #13: Pagination pattern
# Fix #14: Input length validation

from typing import List, Optional
from pydantic import BaseModel, Field


# ---- Pagination ----------------------------------------------------------

class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=25, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""
    items: List = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 25
    pages: int = 1

    model_config = {"extra": "allow"}


def paginate(items: list, page: int = 1, per_page: int = 25) -> PaginatedResponse:
    """Apply pagination to a list of items."""
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    start = (page - 1) * per_page
    end = start + per_page

    return PaginatedResponse(
        items=items[start:end],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# ---- Reusable Validation Constraints (Fix #14) --------------------------

# Use these with Field() in request models for consistent limits

CASE_NAME_MAX = 200
DESCRIPTION_MAX = 5000
SHORT_TEXT_MAX = 500
DIRECTIVE_MAX = 10000
NOTE_MAX = 50000
FILENAME_MAX = 255
TAG_MAX = 100
