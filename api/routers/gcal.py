# ---- Google Calendar Sync Router -----------------------------------------
# Connect, sync events, and manage Google Calendar integration.
# Wraps core/google_cal_sync.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar/google", tags=["Google Calendar"])


class SyncRequest(BaseModel):
    case_id: str = ""
    direction: str = "both"  # push | pull | both


@router.get("/status")
def sync_status(user: dict = Depends(get_current_user)):
    """Check Google Calendar connection status."""
    try:
        from core.google_cal_sync import get_sync_status
        return get_sync_status()
    except Exception as e:
        logger.exception("Failed to get sync status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/connect")
def connect_google_cal(user: dict = Depends(require_role("admin"))):
    """Initiate Google Calendar OAuth flow."""
    try:
        from core.google_cal_sync import initiate_oauth
        return {"auth_url": initiate_oauth()}
    except Exception as e:
        logger.exception("Failed to initiate Google Calendar OAuth")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync")
def trigger_sync(
    body: SyncRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Sync events between app and Google Calendar."""
    try:
        from core.google_cal_sync import sync_events
        result = sync_events(case_id=body.case_id or None, direction=body.direction)
        return {"status": "synced", "result": result}
    except Exception as e:
        logger.exception("Failed to sync events")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events")
def list_google_events(
    days_ahead: int = 30,
    user: dict = Depends(get_current_user),
):
    """List upcoming events from Google Calendar."""
    try:
        from core.google_cal_sync import list_upcoming_events
        events = list_upcoming_events(days_ahead=days_ahead)
        return {"items": events, "total": len(events)}
    except Exception as e:
        logger.exception("Failed to list Google Calendar events")
        raise HTTPException(status_code=500, detail="Internal server error")
