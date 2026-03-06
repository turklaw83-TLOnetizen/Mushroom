# ---- AI War Game Router ---------------------------------------------------
# Adversarial case simulation endpoints.  Creates sessions, generates AI
# attacks, evaluates attorney responses, and produces battle reports.

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import require_role, get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/war-game",
    tags=["War Game"],
)


# ---- Request Models -------------------------------------------------------

class CreateSessionRequest(BaseModel):
    difficulty: Literal["standard", "aggressive", "ruthless"] = "standard"


class RespondRequest(BaseModel):
    response: str = Field(..., min_length=1, max_length=50000)


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


def _load_session_or_404(
    data_dir: str, case_id: str, prep_id: str, session_id: str
) -> dict:
    """Load a war-game session from disk or raise 404."""
    from core.war_game import load_war_game_session

    session = load_war_game_session(data_dir, case_id, prep_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="War-game session not found")
    return session


def _validate_round_type(round_type: str) -> int:
    """Validate round_type against known types.  Returns the round index."""
    from core.war_game import ROUND_TYPES

    if round_type not in ROUND_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid round type '{round_type}'. Must be one of: {', '.join(ROUND_TYPES)}",
        )
    return ROUND_TYPES.index(round_type)


# ---- POST /sessions  — Create new session --------------------------------

@router.post("/sessions", status_code=201)
async def create_session(
    case_id: str,
    prep_id: str,
    body: CreateSessionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new war-game session for this preparation."""
    # Verify case + prep exist
    _load_state_or_404(case_id, prep_id)

    try:
        from core.war_game import create_session as _create, save_war_game_session

        session = _create(difficulty=body.difficulty)
        data_dir = get_data_dir()
        session_id = save_war_game_session(data_dir, case_id, prep_id, session)
        return {"status": "created", "session": session}
    except Exception:
        logger.exception("Failed to create war-game session")
        raise HTTPException(status_code=500, detail="Failed to create war-game session")


# ---- GET /sessions  — List sessions (metadata only) ----------------------

@router.get("/sessions")
def list_sessions(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """List all war-game sessions for this preparation (metadata only)."""
    try:
        from core.war_game import load_war_game_sessions

        data_dir = get_data_dir()
        sessions = load_war_game_sessions(data_dir, case_id, prep_id)
        return {"sessions": sessions}
    except Exception:
        logger.exception("Failed to list war-game sessions")
        return {"sessions": []}


# ---- GET /sessions/{session_id}  — Get full session ----------------------

@router.get("/sessions/{session_id}")
def get_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the full war-game session including all rounds and report."""
    data_dir = get_data_dir()
    session = _load_session_or_404(data_dir, case_id, prep_id, session_id)
    return session


# ---- DELETE /sessions/{session_id}  — Delete session ---------------------

@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a war-game session."""
    from core.war_game import delete_war_game_session

    data_dir = get_data_dir()
    ok = delete_war_game_session(data_dir, case_id, prep_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="War-game session not found")
    return JSONResponse(status_code=204, content=None)


# ---- POST /sessions/{session_id}/rounds/{round_type}/attack  — AI attack -

@router.post("/sessions/{session_id}/rounds/{round_type}/attack")
async def generate_attack(
    case_id: str,
    prep_id: str,
    session_id: str,
    round_type: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate an AI attack for the specified round.

    The round must be in 'pending' status (not already attacked or completed).
    Rounds must be played in order — earlier rounds must be completed first.
    """
    from core.war_game import (
        ROUND_TYPES,
        generate_round_attack,
        save_war_game_session,
    )

    round_idx = _validate_round_type(round_type)
    state = _load_state_or_404(case_id, prep_id)
    data_dir = get_data_dir()
    session = _load_session_or_404(data_dir, case_id, prep_id, session_id)

    # Session must be active
    if session.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Session is '{session.get('status')}', not 'active'. Cannot generate attack.",
        )

    rnd = session["rounds"][round_idx]

    # Check round is pending
    if rnd["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Round '{round_type}' is '{rnd['status']}', expected 'pending'.",
        )

    # Enforce sequential order — all prior rounds must be completed
    for i in range(round_idx):
        prior = session["rounds"][i]
        if prior["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Round '{ROUND_TYPES[i]}' must be completed before "
                    f"starting '{round_type}'."
                ),
            )

    try:
        attack_text = await asyncio.to_thread(
            generate_round_attack, state, session, round_type
        )
        save_war_game_session(data_dir, case_id, prep_id, session)

        return {
            "status": "success",
            "round_type": round_type,
            "attack": attack_text,
            "round_status": session["rounds"][round_idx]["status"],
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Attack generation failed for round %s", round_type)
        raise HTTPException(status_code=500, detail="Attack generation failed")


# ---- POST /sessions/{session_id}/rounds/{round_type}/respond  — Response -

@router.post("/sessions/{session_id}/rounds/{round_type}/respond")
async def submit_response(
    case_id: str,
    prep_id: str,
    session_id: str,
    round_type: str,
    body: RespondRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Submit the attorney's response to a round attack and get an evaluation.

    The round must be in 'awaiting_response' status (attack already generated).
    The jury round does not accept responses — it auto-completes after attack.
    """
    from core.war_game import (
        evaluate_round_response,
        save_war_game_session,
        simulate_jury_verdict,
    )

    round_idx = _validate_round_type(round_type)
    state = _load_state_or_404(case_id, prep_id)
    data_dir = get_data_dir()
    session = _load_session_or_404(data_dir, case_id, prep_id, session_id)

    # Session must be active
    if session.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Session is '{session.get('status')}', not 'active'. Cannot submit response.",
        )

    rnd = session["rounds"][round_idx]

    # Jury round auto-completes — no manual response
    if round_type == "jury":
        raise HTTPException(
            status_code=400,
            detail="The jury round does not accept manual responses. It auto-completes after attack generation.",
        )

    # Check round is awaiting response
    if rnd["status"] != "awaiting_response":
        raise HTTPException(
            status_code=400,
            detail=f"Round '{round_type}' is '{rnd['status']}', expected 'awaiting_response'.",
        )

    try:
        evaluation = await asyncio.to_thread(
            evaluate_round_response, state, session, round_type, body.response
        )

        # If this was the last pre-jury round (elements, index 3) and the jury
        # round is still pending, we auto-generate the jury attack + verdict.
        jury_result = None
        if round_idx == 3 and session["rounds"][4]["status"] == "pending":
            from core.war_game import generate_round_attack

            await asyncio.to_thread(generate_round_attack, state, session, "jury")
            jury_result = await asyncio.to_thread(
                simulate_jury_verdict, state, session
            )

        save_war_game_session(data_dir, case_id, prep_id, session)

        result = {
            "status": "success",
            "round_type": round_type,
            "evaluation": evaluation,
            "round_status": rnd["status"],
        }
        if jury_result is not None:
            result["jury_verdict"] = jury_result
            result["session_status"] = session["status"]

        return result
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Response evaluation failed for round %s", round_type)
        raise HTTPException(status_code=500, detail="Response evaluation failed")


# ---- POST /sessions/{session_id}/finalize  — Battle report ---------------

@router.post("/sessions/{session_id}/finalize")
async def finalize_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate the final battle report for a completed war-game session.

    All five rounds must be completed before the report can be generated.
    If a report already exists, it is regenerated.
    """
    from core.war_game import (
        ROUND_TYPES,
        generate_battle_report,
        save_war_game_session,
    )

    state = _load_state_or_404(case_id, prep_id)
    data_dir = get_data_dir()
    session = _load_session_or_404(data_dir, case_id, prep_id, session_id)

    # All rounds must be completed
    incomplete = []
    for i, rnd in enumerate(session.get("rounds", [])):
        if rnd.get("status") != "completed":
            incomplete.append(ROUND_TYPES[i] if i < len(ROUND_TYPES) else f"round_{i}")
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize: rounds not completed: {', '.join(incomplete)}",
        )

    try:
        report = await asyncio.to_thread(
            generate_battle_report, state, session
        )
        save_war_game_session(data_dir, case_id, prep_id, session)

        return {
            "status": "success",
            "report": report,
            "session_status": session["status"],
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Battle report generation failed")
        raise HTTPException(status_code=500, detail="Battle report generation failed")
