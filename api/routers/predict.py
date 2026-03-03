# ---- Predict Router --------------------------------------------------------
# Case outcome prediction and strategy data retrieval.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predict"])


# ---- Schemas ---------------------------------------------------------------

class PredictionResponse(BaseModel):
    win_probability: float = 0.0
    lose_probability: float = 0.0
    settle_probability: float = 0.0
    confidence: float = 0.0
    key_factors: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendation: str = ""

    model_config = {"extra": "allow"}


class StrategyDataResponse(BaseModel):
    strategy_notes: str = ""
    devils_advocate_notes: str = ""
    voir_dire: dict = Field(default_factory=dict)
    mock_jury_feedback: List[dict] = Field(default_factory=list)
    prediction: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ---- Helpers ---------------------------------------------------------------

def _build_evidence_summary(state: dict) -> str:
    """Extract a textual evidence summary from preparation state."""
    parts = []

    # Evidence foundations
    foundations = state.get("evidence_foundations", [])
    if isinstance(foundations, list):
        for item in foundations:
            if isinstance(item, dict):
                parts.append(item.get("summary", item.get("description", "")))
            elif isinstance(item, str):
                parts.append(item)

    # Consistency check results
    consistency = state.get("consistency_check", [])
    if isinstance(consistency, list):
        for item in consistency:
            if isinstance(item, dict):
                parts.append(item.get("finding", item.get("summary", "")))
            elif isinstance(item, str):
                parts.append(item)
    elif isinstance(consistency, str) and consistency:
        parts.append(consistency)

    return "\n".join(p for p in parts if p)


def _build_witness_summary(state: dict) -> str:
    """Extract a textual witness summary from preparation state."""
    parts = []

    witnesses = state.get("witnesses", [])
    if isinstance(witnesses, list):
        for w in witnesses:
            if isinstance(w, dict):
                name = w.get("name", "Unknown")
                wtype = w.get("type", "")
                summary = w.get("summary", w.get("description", ""))
                parts.append(f"{name} ({wtype}): {summary}" if summary else f"{name} ({wtype})")
            elif isinstance(w, str):
                parts.append(w)

    return "\n".join(p for p in parts if p)


# ---- Endpoints -------------------------------------------------------------

@router.post(
    "/cases/{case_id}/preparations/{prep_id}/predict",
    response_model=PredictionResponse,
)
def run_prediction(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run case outcome prediction using AI analysis.

    Loads case summary, evidence, and witness data from the preparation,
    runs the prediction model, saves results back, and returns the prediction.
    """
    cm = get_case_manager()

    # Load preparation state
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preparation {prep_id} not found for case {case_id}",
        )

    # Build inputs from preparation data
    case_summary = state.get("case_summary", "")
    if not case_summary:
        raise HTTPException(
            status_code=400,
            detail="No case summary available. Run analysis first.",
        )

    evidence_summary = _build_evidence_summary(state)
    witness_summary = _build_witness_summary(state)

    # Run prediction
    try:
        from core.case_prediction import predict_outcome

        prediction = predict_outcome(
            case_summary=case_summary,
            evidence_summary=evidence_summary,
            witness_summary=witness_summary,
        )
    except ImportError as e:
        logger.error("case_prediction module not available: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Prediction module not available",
        )
    except Exception as e:
        logger.exception("Prediction failed for case %s prep %s", case_id, prep_id)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {e}",
        )

    # Save prediction results back to preparation state
    try:
        cm.save_prep_state(case_id, prep_id, {**state, "prediction": prediction})
    except Exception as e:
        logger.warning("Failed to save prediction results: %s", e)
        # Still return the prediction even if save fails

    return PredictionResponse(**prediction)


@router.get(
    "/cases/{case_id}/preparations/{prep_id}/strategy",
    response_model=StrategyDataResponse,
)
def get_strategy_data(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Return all strategy data including prediction results.

    Combines strategy notes, devil's advocate analysis, voir dire,
    mock jury feedback, and prediction into a single response.
    """
    cm = get_case_manager()

    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preparation {prep_id} not found for case {case_id}",
        )

    return StrategyDataResponse(
        strategy_notes=state.get("strategy_notes", ""),
        devils_advocate_notes=state.get("devils_advocate_notes", ""),
        voir_dire=state.get("voir_dire", {}),
        mock_jury_feedback=state.get("mock_jury_feedback", []),
        prediction=state.get("prediction", {}),
    )
