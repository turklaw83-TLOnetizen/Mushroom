# ---- Email Integration Router --------------------------------------------
# Gmail API integration: fetch inbox, approval queue, classify to cases.
# Wraps core/email_integration.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["Email"])


# ---- Schemas -------------------------------------------------------------

class ClassifyRequest(BaseModel):
    email_id: str
    case_id: str
    tags: List[str] = []


class DismissRequest(BaseModel):
    email_id: str
    reason: str = ""


# ---- Endpoints -----------------------------------------------------------

@router.get("/queue")
def email_queue(
    status: str = "",
    user: dict = Depends(get_current_user),
):
    """Get email approval queue, optionally filtered by status."""
    try:
        from core.email_integration import get_all_emails
        items = get_all_emails(status_filter=status)
        return {"items": items, "total": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/stats")
def email_stats(
    user: dict = Depends(get_current_user),
):
    """Get email queue statistics (pending/approved/dismissed counts)."""
    try:
        from core.email_integration import get_email_queue_stats
        return get_email_queue_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify")
def classify_email(
    body: ClassifyRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Approve and classify an email into a case."""
    try:
        from core.email_integration import classify_email as _classify
        from api.deps import get_case_manager
        cm = get_case_manager()
        if not _classify(body.email_id, body.case_id, case_mgr=cm, tags=body.tags):
            raise HTTPException(status_code=404, detail="Email not found")
        return {"status": "classified"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dismiss")
def dismiss_email(
    body: DismissRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Dismiss an email from the queue."""
    try:
        from core.email_integration import dismiss_email as _dismiss
        if not _dismiss(body.email_id, reason=body.reason):
            raise HTTPException(status_code=404, detail="Email not found")
        return {"status": "dismissed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
