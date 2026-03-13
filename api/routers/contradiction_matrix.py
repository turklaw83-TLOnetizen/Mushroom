# ---- Cross-Document Contradiction Matrix Router ----------------------------
# Endpoints for running contradiction matrix analysis, loading saved results,
# and deleting matrices.  Follows the war_game.py router pattern.

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.auth import require_role, get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}",
    tags=["Contradiction Matrix"],
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


# ---- POST /contradiction-matrix  — Run analysis --------------------------

@router.post("/contradiction-matrix", status_code=201)
async def run_contradiction_matrix(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run the full cross-document contradiction matrix analysis.

    This is a long-running operation (1 LLM call per document + 1 per pair
    + 1 synthesis call).  The result is saved to disk and returned.
    """
    state = _load_state_or_404(case_id, prep_id)

    if not state.get("raw_documents"):
        raise HTTPException(
            status_code=400,
            detail="No documents loaded. Run ingestion first.",
        )

    try:
        from core.contradiction_matrix import (
            run_contradiction_matrix as _run_matrix,
            save_contradiction_matrix,
        )

        data_dir = get_data_dir()

        result = await asyncio.to_thread(_run_matrix, state)

        # Persist to disk
        await asyncio.to_thread(
            save_contradiction_matrix, data_dir, case_id, prep_id, result
        )

        return result

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Contradiction matrix analysis failed for case %s prep %s",
            case_id, prep_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Contradiction matrix analysis failed",
        )


# ---- GET /contradiction-matrix  — Load saved matrix ----------------------

@router.get("/contradiction-matrix")
def get_contradiction_matrix(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Load a previously saved contradiction matrix for this preparation."""
    from core.contradiction_matrix import load_contradiction_matrix

    data_dir = get_data_dir()
    matrix = load_contradiction_matrix(data_dir, case_id, prep_id)

    if matrix is None:
        raise HTTPException(
            status_code=404,
            detail="No contradiction matrix found for this preparation",
        )

    return matrix


# ---- DELETE /contradiction-matrix  — Delete saved matrix -----------------

@router.delete("/contradiction-matrix", status_code=204)
def delete_contradiction_matrix(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a saved contradiction matrix."""
    from core.contradiction_matrix import delete_contradiction_matrix as _delete

    data_dir = get_data_dir()
    ok = _delete(data_dir, case_id, prep_id)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="No contradiction matrix found for this preparation",
        )

    return JSONResponse(status_code=204, content=None)
