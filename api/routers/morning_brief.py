# ---- Morning Brief Router -------------------------------------------------
# Daily brief generation, triage actions, deadline chains, and email digest.

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brief", tags=["Morning Brief"])


# ---- Request Models ------------------------------------------------------

class SnoozeRequest(BaseModel):
    days: int = 3


class DigestRequest(BaseModel):
    target_date: Optional[str] = None
    recipient_email: Optional[str] = None


# ---- Brief Endpoints -----------------------------------------------------

@router.get("")
def get_morning_brief(
    target_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format"),
    user: dict = Depends(get_current_user),
):
    """Generate the complete morning brief for today (or a specified date)."""
    try:
        from core.morning_brief import generate_morning_brief
        case_mgr = get_case_manager()
        data_dir = get_data_dir()
        user_id = user.get("id", user.get("sub", ""))
        brief = generate_morning_brief(case_mgr, data_dir, user_id, target_date)
        return brief
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to generate morning brief")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Triage Actions ------------------------------------------------------

@router.post("/items/{item_id}/dismiss")
def dismiss_item(
    item_id: str,
    user: dict = Depends(get_current_user),
):
    """Dismiss a triage item for 24 hours."""
    try:
        from core.morning_brief import dismiss_brief_item
        data_dir = get_data_dir()
        if not dismiss_brief_item(data_dir, item_id):
            raise HTTPException(status_code=404, detail="Brief item not found")
        return {"success": True, "item_id": item_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to dismiss brief item")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/items/{item_id}/snooze")
def snooze_item(
    item_id: str,
    body: SnoozeRequest,
    user: dict = Depends(get_current_user),
):
    """Snooze a triage item for N days."""
    try:
        from core.morning_brief import snooze_brief_item
        from datetime import date, timedelta
        data_dir = get_data_dir()
        result = snooze_brief_item(data_dir, item_id, body.days)
        if not result:
            raise HTTPException(status_code=404, detail="Brief item not found")
        snoozed_until = str(date.today() + timedelta(days=body.days))
        return {"success": True, "item_id": item_id, "snoozed_until": snoozed_until}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to snooze brief item")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Email Digest --------------------------------------------------------

@router.post("/send-digest")
def send_email_digest(
    body: DigestRequest,
    user: dict = Depends(get_current_user),
):
    """Send the morning brief as an email digest to the attorney."""
    try:
        from core.morning_brief import generate_morning_brief
        from core.comms import add_to_queue

        case_mgr = get_case_manager()
        data_dir = get_data_dir()
        user_id = user.get("id", user.get("sub", ""))

        brief = generate_morning_brief(case_mgr, data_dir, user_id, body.target_date)
        email_html = brief.get("email_html", "")
        if not email_html:
            raise HTTPException(status_code=400, detail="Brief generated but no email content available")

        recipient = body.recipient_email or user.get("email", "")
        if not recipient:
            raise HTTPException(status_code=400, detail="No recipient email provided")

        comm_id = add_to_queue(
            client_id="",
            trigger_type="morning_brief",
            subject=f"Morning Brief - {brief.get('date', 'Today')}",
            body_html=email_html,
            channel="email",
        )
        return {"success": True, "comm_id": comm_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to send morning brief digest")
        raise HTTPException(status_code=500, detail="Internal server error")
