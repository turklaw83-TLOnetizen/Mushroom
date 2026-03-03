# ---- Calendar Router -----------------------------------------------------
# Events, deadlines, and calendar management.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar", tags=["Calendar"])


class EventResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    title: str = ""
    date: str = ""
    time: str = ""
    type: str = ""
    description: str = ""
    location: str = ""

    model_config = {"extra": "allow"}


class CreateEventRequest(BaseModel):
    case_id: str = Field(default="", max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    date: str = Field(..., max_length=20)
    time: str = Field(default="", max_length=10)
    type: str = Field(default="event", max_length=50)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=500)


@router.get("/events", response_model=List[EventResponse])
def list_events(
    case_id: str = Query(default="", description="Filter by case"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List calendar events, optionally filtered by case (with limit/offset)."""
    try:
        from core.calendar_events import load_events
        cm = get_case_manager()
        events = load_events(cm.storage, case_id=case_id or None)
        return events[offset:offset + limit]
    except ImportError:
        return []


@router.post("/events")
def create_event(
    body: CreateEventRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Create a calendar event."""
    try:
        from core.calendar_events import add_event
        cm = get_case_manager()
        event_id = add_event(cm.storage, **body.model_dump())
        return {"status": "created", "id": event_id}
    except ImportError:
        return {"status": "calendar_module_not_available"}


@router.delete("/events/{event_id}")
def delete_event(
    event_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete an event."""
    try:
        from core.calendar_events import delete_event as core_delete
        cm = get_case_manager()
        core_delete(cm.storage, event_id)
        return {"status": "deleted", "id": event_id}
    except ImportError:
        return {"status": "calendar_module_not_available"}


@router.put("/events/{event_id}")
def update_event(
    event_id: str,
    body: CreateEventRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a calendar event."""
    try:
        from core.calendar_events import delete_event as core_delete, add_event
        cm = get_case_manager()
        core_delete(cm.storage, event_id)
        new_id = add_event(cm.storage, **{**body.model_dump(), "id": event_id})
        return {"status": "updated", "id": new_id}
    except ImportError:
        return {"status": "calendar_module_not_available"}


@router.get("/upcoming")
def upcoming_events(
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Get upcoming events within N days."""
    try:
        from core.calendar_events import get_upcoming_events
        cm = get_case_manager()
        return get_upcoming_events(cm.storage, days=days)
    except ImportError:
        return []
