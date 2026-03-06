# ---- Calendar Router -----------------------------------------------------
# Events, deadlines, and calendar management.

import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar", tags=["Calendar"])


class EventResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    title: str = ""
    date: str = ""
    time: str = ""
    type: str = ""
    event_type: str = ""
    description: str = ""
    location: str = ""
    status: str = "scheduled"
    end_time: str = ""
    days_until: int | None = None

    model_config = {"extra": "allow"}


class RecurrenceSpec(BaseModel):
    frequency: str = Field(..., pattern="^(daily|weekly|biweekly|monthly)$")
    end_date: str = Field(..., max_length=20, description="End date in YYYY-MM-DD format")


class CreateEventRequest(BaseModel):
    case_id: str = Field(default="", max_length=200)
    client_id: str = Field(default="", max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    date: str = Field(..., max_length=20)
    time: str = Field(default="", max_length=10)
    type: str = Field(default="event", max_length=50)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=500)
    recurrence: RecurrenceSpec | None = Field(default=None, description="Optional recurrence rule")


class StatusChangeRequest(BaseModel):
    status: str = Field(..., pattern="^(scheduled|completed|cancelled|rescheduled)$")


# ---- Event CRUD ----------------------------------------------------------

@router.get("/events", response_model=List[EventResponse])
def list_events(
    case_id: str = Query(default="", description="Filter by case"),
    user: dict = Depends(get_current_user),
):
    """List calendar events, optionally filtered by case."""
    try:
        from core.calendar_events import load_events
        events = load_events()
        if case_id:
            events = [e for e in events if e.get("case_id") == case_id]
        # Normalize type field for frontend compatibility
        for e in events:
            if not e.get("type"):
                e["type"] = e.get("event_type", "event")
        return events
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
        recurrence_dict = body.recurrence.model_dump() if body.recurrence else None
        event_id = add_event(
            title=body.title,
            event_type=body.type,
            event_date=body.date,
            time=body.time,
            description=body.description,
            location=body.location,
            case_id=body.case_id,
            client_id=body.client_id,
            recurrence=recurrence_dict,
        )
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
        core_delete(event_id)
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
        from core.calendar_events import update_event as core_update
        updates = {
            "title": body.title,
            "event_type": body.type,
            "event_date": body.date,
            "time": body.time,
            "description": body.description,
            "location": body.location,
            "case_id": body.case_id,
        }
        core_update(event_id, updates)
        return {"status": "updated", "id": event_id}
    except ImportError:
        return {"status": "calendar_module_not_available"}


@router.patch("/events/{event_id}/status")
def change_event_status(
    event_id: str,
    body: StatusChangeRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Change an event's status (scheduled/completed/cancelled/rescheduled)."""
    try:
        from core.calendar_events import update_event as core_update
        if not core_update(event_id, {"status": body.status}):
            raise HTTPException(status_code=404, detail="Event not found")
        return {"status": "updated", "id": event_id, "new_status": body.status}
    except ImportError:
        raise HTTPException(status_code=500, detail="Calendar module not available")


# ---- Calendar Views ------------------------------------------------------

@router.get("/upcoming")
def upcoming_events(
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Get upcoming events within N days."""
    try:
        from core.calendar_events import get_upcoming_events
        return get_upcoming_events(days=days)
    except ImportError:
        return []


@router.get("/month")
def month_calendar(
    year: int = Query(default=None, ge=2020, le=2099),
    month: int = Query(default=None, ge=1, le=12),
    user: dict = Depends(get_current_user),
):
    """Get month calendar grid with events per day cell."""
    try:
        from core.calendar_events import get_month_calendar
        if year is None:
            year = date.today().year
        if month is None:
            month = date.today().month
        return get_month_calendar(year, month)
    except ImportError:
        return {"year": year, "month": month, "month_name": "", "weeks": [], "total_events": 0}


@router.get("/stats")
def calendar_stats(
    user: dict = Depends(get_current_user),
):
    """Get calendar statistics for dashboard display."""
    try:
        from core.calendar_events import get_calendar_stats
        return get_calendar_stats()
    except ImportError:
        return {
            "total_events": 0, "active_events": 0, "upcoming": 0,
            "this_week": 0, "past_due": 0, "completed": 0,
            "cancelled": 0, "type_breakdown": {},
        }
