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

        # Group by case
        grouped: dict = {}
        sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        for n in items:
            cid = n.get("case_id") or "ungrouped"
            cname = n.get("case_name") or "General"
            if cid not in grouped:
                grouped[cid] = {
                    "case_name": cname,
                    "case_id": cid,
                    "items": [],
                    "max_severity": "low",
                }
            grouped[cid]["items"].append(n)
            if sev_order.get(n.get("severity", "low"), 0) > sev_order.get(
                grouped[cid]["max_severity"], 0
            ):
                grouped[cid]["max_severity"] = n.get("severity", "low")

        return {
            "items": items,
            "grouped": list(grouped.values()),
            "total": len(items),
        }
    except Exception as e:
        logger.exception("Notification error")
        raise HTTPException(status_code=500, detail="Internal server error")
