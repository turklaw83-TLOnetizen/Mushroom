# ---- Activity Feed Router ------------------------------------------------
import logging
from fastapi import APIRouter, Depends
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activity", tags=["Activity"])


@router.get("/recent")
def recent_activity(
    limit: int = 15,
    user: dict = Depends(get_current_user),
):
    """Get recent activity across the system."""
    try:
        from core.activity import get_recent_activity
        return {"items": get_recent_activity(limit=min(limit, 50))}
    except Exception:
        logger.exception("Failed to get recent activity")
        return {"items": []}
