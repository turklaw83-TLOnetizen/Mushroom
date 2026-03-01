# ---- Pagination Utility ---------------------------------------------------
# Standard paginated response wrapper for all list endpoints.

from pydantic import BaseModel
from typing import TypeVar, Generic
from math import ceil


T = TypeVar("T")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def limit(self) -> int:
        return min(self.page_size, MAX_PAGE_SIZE)

    def offset(self) -> int:
        return (max(self.page, 1) - 1) * self.limit()


class PaginatedResponse(BaseModel):
    """Standard paginated response."""
    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


def paginate(items: list, total: int, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> PaginatedResponse:
    """Create a paginated response from a list of items."""
    effective_size = min(page_size, MAX_PAGE_SIZE)
    total_pages = ceil(total / effective_size) if effective_size > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=effective_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
