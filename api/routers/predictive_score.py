# ---- Predictive Case Scoring Router ----------------------------------------
# Endpoints for computing multi-dimensional case quality scores and
# tracking score trends over time.

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_role, get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/predictive-score",
    tags=["Predictive Scoring"],
)


# ---- Helpers --------------------------------------------------------------

def _load_state_or_404(case_id: str, prep_id: str) -> dict:
    """Load preparation state or raise 404."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=404, detail="Preparation not found")
    return state


# ---- GET /  — Compute and return predictive score --------------------------

@router.get("")
async def get_predictive_score(
    case_id: str,
    prep_id: str,
    save: bool = True,
    user: dict = Depends(get_current_user),
):
    """Compute the multi-dimensional predictive case score.

    Analyzes evidence quality, witness strength, element coverage,
    legal authority, narrative coherence, and adversarial resilience.

    This is a pure data analysis operation (no LLM calls) and completes
    quickly. The score is automatically saved for trend tracking unless
    ``save=false`` is passed as a query parameter.

    Returns the full score with dimensional breakdowns, top strengths,
    top vulnerabilities with suggested actions, and trend data.
    """
    state = _load_state_or_404(case_id, prep_id)
    data_dir = get_data_dir()

    try:
        from core.predictive_scoring import (
            compute_predictive_score,
            save_score_snapshot,
        )

        # compute_predictive_score is CPU-bound (no I/O), but we use
        # to_thread for consistency and to not block the event loop
        # if the state dict is very large.
        score = await asyncio.to_thread(
            compute_predictive_score,
            state=state,
            data_dir=data_dir,
            case_id=case_id,
            prep_id=prep_id,
        )

        # Auto-save snapshot for trend tracking
        if save:
            try:
                save_score_snapshot(data_dir, case_id, prep_id, score)
            except Exception:
                logger.warning(
                    "Failed to save score snapshot for case %s prep %s",
                    case_id, prep_id,
                )

        return {
            "status": "success",
            "score": score,
        }

    except Exception:
        logger.exception(
            "Predictive score computation failed for case %s prep %s",
            case_id, prep_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Predictive score computation failed",
        )


# ---- GET /history  — Score trend history -----------------------------------

@router.get("/history")
def get_score_history(
    case_id: str,
    prep_id: str,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Return score history for trend analysis (newest first).

    Each entry includes the overall score, grade, label, per-dimension
    scores, and the timestamp. Use this to visualize score trends
    over time as the case develops.

    Args:
        limit: Maximum number of history entries to return (default 20).
    """
    # Verify case + prep exist
    _load_state_or_404(case_id, prep_id)

    try:
        from core.predictive_scoring import load_score_history

        data_dir = get_data_dir()
        history = load_score_history(data_dir, case_id, prep_id)

        # Apply limit
        if limit > 0:
            history = history[:limit]

        return {
            "status": "success",
            "history": history,
            "total_snapshots": len(history),
        }

    except Exception:
        logger.exception(
            "Failed to load score history for case %s prep %s",
            case_id, prep_id,
        )
        return {"status": "success", "history": [], "total_snapshots": 0}


# ---- GET /compare  — Compare current vs previous score --------------------

@router.get("/compare")
async def compare_scores(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Compute current score and compare with the most recent saved snapshot.

    Returns both the current score and the previous score side by side,
    with per-dimension change analysis. Useful for showing whether
    recent work (new analysis, additional evidence, etc.) improved
    the case position.
    """
    state = _load_state_or_404(case_id, prep_id)
    data_dir = get_data_dir()

    try:
        from core.predictive_scoring import (
            compute_predictive_score,
            load_score_history,
        )

        # Compute current score (do NOT save — comparison is read-only)
        current = await asyncio.to_thread(
            compute_predictive_score,
            state=state,
            data_dir=data_dir,
            case_id=case_id,
            prep_id=prep_id,
        )

        # Load previous
        history = load_score_history(data_dir, case_id, prep_id)
        previous = history[0] if history else None

        # Build dimension-level comparison
        changes: dict = {}
        if previous and previous.get("dimension_scores"):
            for dim, curr_data in current.get("dimensions", {}).items():
                prev_score = previous["dimension_scores"].get(dim)
                curr_score = curr_data.get("score")
                if prev_score is not None and curr_score is not None:
                    diff = curr_score - prev_score
                    direction = "improved" if diff > 0 else "declined" if diff < 0 else "unchanged"
                    changes[dim] = {
                        "current": curr_score,
                        "previous": prev_score,
                        "change": diff,
                        "direction": direction,
                    }

        return {
            "status": "success",
            "current": current,
            "previous": previous,
            "dimension_changes": changes,
        }

    except Exception:
        logger.exception(
            "Score comparison failed for case %s prep %s",
            case_id, prep_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Score comparison failed",
        )
