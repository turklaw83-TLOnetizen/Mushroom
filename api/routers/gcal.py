# ---- Google Calendar Sync Router -----------------------------------------
# Connect, sync events, and manage Google Calendar integration.
# Wraps core/google_cal_sync.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar/google", tags=["Google Calendar"])


class SyncRequest(BaseModel):
    case_id: str = ""
    direction: str = "both"  # push | pull | both


class CallbackRequest(BaseModel):
    auth_code: str = Field(..., min_length=1, max_length=2000)
    email: str = Field(default="", max_length=320)


class CalendarChoiceRequest(BaseModel):
    calendar_id: str = Field(..., min_length=1, max_length=500)
    calendar_name: str = Field(default="", max_length=500)


# ---- Status & Connection -------------------------------------------------

@router.get("/status")
def sync_status(user: dict = Depends(get_current_user)):
    """Check Google Calendar connection status."""
    try:
        from core.google_cal_sync import get_sync_status
        return get_sync_status()
    except Exception:
        logger.exception("Failed to get sync status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/connect")
def connect_google_cal(user: dict = Depends(require_role("admin"))):
    """Initiate Google Calendar OAuth flow. Returns auth URL."""
    try:
        from core.google_cal_sync import initiate_oauth
        auth_url = initiate_oauth()
        if not auth_url:
            raise HTTPException(
                status_code=400,
                detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
            )
        return {"auth_url": auth_url}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to initiate Google Calendar OAuth")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/callback")
def oauth_callback(
    body: CallbackRequest,
    user: dict = Depends(require_role("admin")),
):
    """Exchange OAuth authorization code for tokens."""
    try:
        from core.google_cal_sync import handle_callback
        success = handle_callback(
            user_id="default",
            auth_code=body.auth_code,
            email=body.email,
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to exchange auth code")
        return {"status": "connected"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to complete Google Calendar OAuth callback")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/disconnect")
def disconnect_google_cal(user: dict = Depends(require_role("admin"))):
    """Disconnect Google Calendar integration."""
    try:
        from core.google_cal_sync import disconnect
        disconnect("default")
        return {"status": "disconnected"}
    except Exception:
        logger.exception("Failed to disconnect Google Calendar")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Calendar List & Selection -------------------------------------------

@router.get("/calendars")
def list_google_calendars(user: dict = Depends(get_current_user)):
    """List available Google Calendars for the connected account."""
    try:
        from core.google_cal_sync import list_calendars, is_connected
        if not is_connected("default"):
            return {"items": [], "connected": False}
        calendars = list_calendars("default")
        return {"items": calendars, "connected": True}
    except Exception:
        logger.exception("Failed to list Google Calendars")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/calendars")
def set_calendar_choice(
    body: CalendarChoiceRequest,
    user: dict = Depends(require_role("admin")),
):
    """Set which Google Calendar to sync events to."""
    try:
        from core.google_cal_sync import set_target_calendar
        success = set_target_calendar("default", body.calendar_id, body.calendar_name)
        if not success:
            raise HTTPException(status_code=400, detail="Not connected to Google Calendar")
        return {"status": "updated", "calendar_id": body.calendar_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to set calendar choice")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Sync & Events -------------------------------------------------------

@router.post("/sync")
def trigger_sync(
    body: SyncRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Sync events between app and Google Calendar."""
    try:
        from core.google_cal_sync import sync_events
        result = sync_events(
            user_id="default",
            case_id=body.case_id or None,
            direction=body.direction,
        )
        return {"status": "synced", "result": result}
    except Exception:
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
        events = list_upcoming_events(user_id="default", days_ahead=days_ahead)
        return {"items": events, "total": len(events)}
    except Exception:
        logger.exception("Failed to list Google Calendar events")
        raise HTTPException(status_code=500, detail="Internal server error")
