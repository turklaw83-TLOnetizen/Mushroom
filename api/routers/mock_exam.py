# ---- Mock Examination Router -----------------------------------------------
# Session CRUD + scorecard generation for the Mock Exam Simulator.

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/mock-exam",
    tags=["Mock Exam"],
)


# ---- Request / Response Models ---------------------------------------------

class CreateSessionRequest(BaseModel):
    witness_name: str = Field(..., min_length=1, max_length=200)
    exam_type: str = Field(..., pattern=r"^(cross|direct)$")
    opposing_counsel_mode: bool = False


class SessionSummary(BaseModel):
    id: str
    witness_name: str
    witness_type: str = ""
    exam_type: str
    opposing_counsel_mode: bool = False
    created_at: str
    ended_at: Optional[str] = None
    message_count: int = 0
    status: str = "active"
    scorecard_summary: Optional[dict] = None

    model_config = {"extra": "allow"}


class SessionDetail(BaseModel):
    session_id: str
    witness_name: str
    witness_type: str = ""
    exam_type: str
    opposing_counsel_mode: bool = False
    messages: list = []
    coaching_notes: list = []
    scorecard: Optional[dict] = None

    model_config = {"extra": "allow"}


# ---- Endpoints -------------------------------------------------------------

@router.post("/sessions", response_model=dict, status_code=201)
def create_session(
    case_id: str,
    prep_id: str,
    body: CreateSessionRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new mock examination session."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation not found or no analysis state.")

    # Find the witness
    witnesses = state.get("witnesses", [])
    witness = None
    for w in witnesses:
        if isinstance(w, dict):
            name = w.get("name", w.get("witness", ""))
            if name.lower() == body.witness_name.lower():
                witness = w
                break

    if not witness:
        raise HTTPException(
            status_code=404,
            detail=f"Witness '{body.witness_name}' not found in this preparation.",
        )

    w_type = witness.get("type", witness.get("role", "Unknown"))

    from core.nodes.mock_exam import (
        create_initial_session_data,
        create_session_id,
        create_session_index_entry,
    )

    session_id = create_session_id()

    # Create session data file
    session_data = create_initial_session_data(
        session_id, body.witness_name, w_type, body.exam_type, body.opposing_counsel_mode,
    )
    cm.save_mock_exam_data(case_id, prep_id, session_id, session_data)

    # Add to sessions index
    sessions = cm.load_mock_exam_sessions(case_id, prep_id)
    entry = create_session_index_entry(
        session_id, body.witness_name, w_type, body.exam_type, body.opposing_counsel_mode,
    )
    sessions.insert(0, entry)
    cm.save_mock_exam_sessions(case_id, prep_id, sessions)

    logger.info("Created mock exam session %s for witness %s", session_id, body.witness_name)
    return {"session_id": session_id, "witness_type": w_type}


@router.get("/sessions", response_model=List[SessionSummary])
def list_sessions(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """List all mock exam sessions for this preparation."""
    cm = get_case_manager()
    sessions = cm.load_mock_exam_sessions(case_id, prep_id)
    return sessions


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a session with full message history."""
    cm = get_case_manager()
    data = cm.load_mock_exam_data(case_id, prep_id, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return data


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a mock exam session."""
    cm = get_case_manager()
    sessions = cm.load_mock_exam_sessions(case_id, prep_id)
    sessions = [s for s in sessions if s.get("id") != session_id]
    cm.save_mock_exam_sessions(case_id, prep_id, sessions)
    # Delete session data file (best effort)
    try:
        cm.save_mock_exam_data(case_id, prep_id, session_id, {})
    except Exception:
        pass
    logger.info("Deleted mock exam session %s", session_id)


@router.post("/sessions/{session_id}/end", response_model=dict)
async def end_session(
    case_id: str,
    prep_id: str,
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """End a session and generate the scorecard."""
    cm = get_case_manager()
    session_data = cm.load_mock_exam_data(case_id, prep_id, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    state = cm.load_prep_state(case_id, prep_id) or {}
    witnesses = state.get("witnesses", [])
    witness_name = session_data.get("witness_name", "")
    witness = {}
    for w in witnesses:
        if isinstance(w, dict):
            name = w.get("name", w.get("witness", ""))
            if name.lower() == witness_name.lower():
                witness = w
                break

    from core.nodes.mock_exam import generate_scorecard

    scorecard = await asyncio.to_thread(
        generate_scorecard,
        state,
        session_data.get("messages", []),
        session_data.get("coaching_notes", []),
        session_data.get("exam_type", "cross"),
        witness,
    )

    # Save scorecard to session
    session_data["scorecard"] = scorecard
    cm.save_mock_exam_data(case_id, prep_id, session_id, session_data)

    # Update index
    sessions = cm.load_mock_exam_sessions(case_id, prep_id)
    for s in sessions:
        if s.get("id") == session_id:
            s["status"] = "completed"
            s["ended_at"] = datetime.now().isoformat()
            s["message_count"] = sum(
                1 for m in session_data.get("messages", []) if m.get("role") == "attorney"
            )
            s["scorecard_summary"] = {
                "overall_score": scorecard.get("overall_score", 0),
                "summary": scorecard.get("summary", ""),
            }
            break
    cm.save_mock_exam_sessions(case_id, prep_id, sessions)

    logger.info("Ended mock exam session %s with score %s", session_id, scorecard.get("overall_score"))
    return scorecard
