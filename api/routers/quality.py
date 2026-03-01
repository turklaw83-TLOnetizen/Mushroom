# ---- Quality & Cost Router -----------------------------------------------
# Exposes analysis quality scores, draft quality, and LLM cost tracking.
# Wraps core/analysis_quality.py, core/draft_quality.py, core/cost_tracker.py

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/quality", tags=["Quality & Costs"])


@router.get("/analysis")
def analysis_quality(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get quality scores for case analysis modules."""
    try:
        from core.analysis_quality import score_analysis
        return score_analysis(case_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts")
def draft_quality(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get quality scores for generated drafts (motions, briefs)."""
    try:
        from core.draft_quality import score_drafts
        return score_drafts(case_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs")
def llm_costs(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get LLM API cost breakdown for a case."""
    try:
        from core.cost_tracker import get_case_costs
        return get_case_costs(case_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/summary")
def cost_summary(
    user: dict = Depends(require_role("admin")),
):
    """Get global LLM cost summary across all cases."""
    try:
        from core.cost_tracker import get_global_costs
        return get_global_costs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
