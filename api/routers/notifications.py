# ---- Notifications Router ------------------------------------------------
# Aggregates notifications from overdue tasks, deadlines, retainer balances.
# Wraps core/notifications.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def get_notifications(
    case_ids: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """
    Get aggregated notifications sorted by severity.

    Query params:
        case_ids: Comma-separated case IDs to filter (optional)

    Returns:
        {items: [{type, title, detail, case_id, severity, timestamp}, ...]}
    """
    try:
        from core.notifications import get_notifications as _get
        cm = get_case_manager()
        user_id = user.get("id", "")

        _case_ids = case_ids.split(",") if case_ids else None
        items = _get(cm, user_id=user_id, case_ids=_case_ids)
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception("Notification error")
        raise HTTPException(status_code=500, detail=str(e))
