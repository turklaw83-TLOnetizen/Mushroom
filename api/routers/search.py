# ---- Global Search Router ------------------------------------------------
# Cross-entity search across cases, clients, and tasks.
# Wraps core/search.py

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
def global_search(
    q: str = "",
    user: dict = Depends(get_current_user),
):
    """
    Search across cases, clients, and tasks.

    Returns:
        {cases: [...], clients: [...], tasks: [...]}
    """
    if not q or len(q) < 2:
        return {"cases": [], "clients": [], "tasks": []}
    try:
        from core.search import global_search as _search
        cm = get_case_manager()
        return _search(q, cm)
    except Exception as e:
        logger.exception("Search error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/case/{case_id}")
def search_in_case(
    case_id: str,
    q: str = "",
    user: dict = Depends(get_current_user),
):
    """Search within a specific case (tasks, activity)."""
    if not q or len(q) < 2:
        return {"tasks": [], "activity": []}
    try:
        from core.search import search_in_case as _search
        cm = get_case_manager()
        return _search(q, case_id, cm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
