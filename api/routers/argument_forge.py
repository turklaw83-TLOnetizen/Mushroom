# ---- Argument Forge Router ------------------------------------------------
# AI-powered legal argument construction and analysis.

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_role, get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/argument-forge",
    tags=["Argument Forge"],
)


# ---- Request Models -------------------------------------------------------

class IdentifyIssuesRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    custom_focus: str = Field(default="", max_length=5000)


class GenerateArgumentsRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    issue: dict
    frameworks: list = Field(
        default_factory=lambda: ["constitutional", "statutory", "common_law", "policy", "equity"]
    )


class SteelmanRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    our_arguments: list


class CounterMatrixRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    our_arguments: list
    opponent_arguments: list


class OralPrepRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    arguments: list
    time_limit: int = Field(default=15, ge=1, le=60)


class ScoreRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    arguments: list


class ExportSkeletonRequest(BaseModel):
    arguments: list
    counter_matrix: list = Field(default_factory=list)


class SaveSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    data: dict


# ---- Helper ---------------------------------------------------------------

def _load_state_or_404(case_id: str, prep_id: str) -> dict:
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=404, detail="Preparation not found")
    return state


# ---- Endpoints ------------------------------------------------------------

@router.post("/identify-issues")
async def identify_issues(
    case_id: str,
    body: IdentifyIssuesRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Identify key legal issues in the case."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import identify_issues as _identify_issues
        result = await asyncio.to_thread(_identify_issues, state, body.custom_focus)
        return result
    except Exception:
        logger.exception("Issue identification failed")
        raise HTTPException(status_code=500, detail="Issue identification failed")


@router.post("/generate-arguments")
async def generate_arguments(
    case_id: str,
    body: GenerateArgumentsRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate arguments across multiple legal frameworks for an issue."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import generate_arguments as _generate_arguments
        result = await asyncio.to_thread(_generate_arguments, state, body.issue, body.frameworks)
        return result
    except Exception:
        logger.exception("Argument generation failed")
        raise HTTPException(status_code=500, detail="Argument generation failed")


@router.post("/steelman")
async def steelman_opposition(
    case_id: str,
    body: SteelmanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate the strongest possible counter-positions to our arguments."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import steelman_opposition as _steelman
        result = await asyncio.to_thread(_steelman, state, body.our_arguments)
        return result
    except Exception:
        logger.exception("Steelman generation failed")
        raise HTTPException(status_code=500, detail="Steelman generation failed")


@router.post("/counter-matrix")
async def build_counter_matrix(
    case_id: str,
    body: CounterMatrixRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Build argument/counter-argument/rebuttal matrix."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import build_counter_matrix as _build_matrix
        result = await asyncio.to_thread(_build_matrix, state, body.our_arguments, body.opponent_arguments)
        return result
    except Exception:
        logger.exception("Counter-matrix build failed")
        raise HTTPException(status_code=500, detail="Counter-matrix build failed")


@router.post("/oral-prep")
async def prepare_oral(
    case_id: str,
    body: OralPrepRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Structure arguments for oral presentation within a time limit."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import prepare_oral_arguments as _prepare_oral
        result = await asyncio.to_thread(_prepare_oral, state, body.arguments, body.time_limit)
        return result
    except Exception:
        logger.exception("Oral prep failed")
        raise HTTPException(status_code=500, detail="Oral prep failed")


@router.post("/score")
async def score_arguments(
    case_id: str,
    body: ScoreRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Score and rank arguments by win probability."""
    state = _load_state_or_404(case_id, body.prep_id)
    try:
        from core.argument_forge import score_arguments as _score
        result = await asyncio.to_thread(_score, state, body.arguments)
        return result
    except Exception:
        logger.exception("Argument scoring failed")
        raise HTTPException(status_code=500, detail="Argument scoring failed")


@router.post("/export-skeleton")
def export_skeleton(
    case_id: str,
    body: ExportSkeletonRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Export arguments as a Major Document Drafter-compatible outline. No LLM call."""
    try:
        from core.argument_forge import export_to_brief_skeleton
        return export_to_brief_skeleton(body.arguments, body.counter_matrix)
    except Exception:
        logger.exception("Export skeleton failed")
        raise HTTPException(status_code=500, detail="Export skeleton failed")


# ---- Session Persistence --------------------------------------------------

@router.get("/sessions")
def list_sessions(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List saved argument forge sessions for this case."""
    try:
        from core.argument_forge import load_argument_sessions
        data_dir = get_data_dir()
        return {"sessions": load_argument_sessions(data_dir, case_id)}
    except Exception:
        logger.exception("Failed to load sessions")
        return {"sessions": []}


@router.post("/sessions")
def save_session(
    case_id: str,
    body: SaveSessionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save an argument forge session."""
    try:
        from core.argument_forge import save_argument_session
        data_dir = get_data_dir()
        session = {"name": body.name, **body.data}
        session_id = save_argument_session(data_dir, case_id, session)
        return {"status": "saved", "id": session_id}
    except Exception:
        logger.exception("Failed to save session")
        raise HTTPException(status_code=500, detail="Failed to save session")


@router.delete("/sessions/{session_id}")
def delete_session(
    case_id: str,
    session_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete an argument forge session."""
    try:
        from core.argument_forge import delete_argument_session
        data_dir = get_data_dir()
        ok = delete_argument_session(data_dir, case_id, session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "id": session_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete session")
        raise HTTPException(status_code=500, detail="Failed to delete session")
