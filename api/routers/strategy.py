# ---- Strategy Router -----------------------------------------------------
# Strategy, voir dire, and mock jury for a case preparation.

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/preparations/{prep_id}/strategy", tags=["Strategy"])


class StrategyResponse(BaseModel):
    strategy_notes: str = ""
    devils_advocate_notes: str = ""
    voir_dire: dict = Field(default_factory=dict)
    mock_jury_feedback: List[dict] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class UpdateStrategyRequest(BaseModel):
    strategy_notes: str | None = None
    devils_advocate_notes: str | None = None


@router.get("", response_model=StrategyResponse)
def get_strategy(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get strategy, voir dire, and mock jury data."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return StrategyResponse(
        strategy_notes=state.get("strategy_notes", ""),
        devils_advocate_notes=state.get("devils_advocate_notes", ""),
        voir_dire=state.get("voir_dire", {}),
        mock_jury_feedback=state.get("mock_jury_feedback", []),
    )


@router.put("")
def update_strategy(
    case_id: str,
    prep_id: str,
    body: UpdateStrategyRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update strategy notes."""
    cm = get_case_manager()
    updates = {}
    if body.strategy_notes is not None:
        updates["strategy_notes"] = body.strategy_notes
    if body.devils_advocate_notes is not None:
        updates["devils_advocate_notes"] = body.devils_advocate_notes
    if updates:
        cm.save_prep_state(case_id, prep_id, updates)
    return {"status": "updated"}


@router.get("/voir-dire")
def get_voir_dire(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get voir dire data."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("voir_dire", {})


@router.get("/mock-jury")
def get_mock_jury(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get mock jury feedback."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("mock_jury_feedback", [])
