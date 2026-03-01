# ---- Witnesses Router ----------------------------------------------------
# Witness management for a case preparation.
# Reads/writes from the prep state's `witnesses` key.

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/preparations/{prep_id}/witnesses", tags=["Witnesses"])


# ---- Models --------------------------------------------------------------

class WitnessResponse(BaseModel):
    name: str = ""
    type: str = "State"
    role: str = ""
    goal: str = ""
    credibility_notes: str = ""
    key_testimony: str = ""

    model_config = {"extra": "allow"}


class CreateWitnessRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(default="State", max_length=50)
    role: str = Field(default="", max_length=200)
    goal: str = Field(default="", max_length=2000)


class CrossExamPoint(BaseModel):
    topic: str = ""
    question: str = ""
    impeachment_source: str = ""
    priority: str = "medium"

    model_config = {"extra": "allow"}


# ---- Endpoints -----------------------------------------------------------

@router.get("", response_model=List[WitnessResponse])
def list_witnesses(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """List all witnesses for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("witnesses", [])


@router.post("")
def add_witness(
    case_id: str,
    prep_id: str,
    body: CreateWitnessRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a witness to the preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    witnesses = state.get("witnesses", [])
    witnesses.append(body.model_dump())
    cm.save_prep_state(case_id, prep_id, {"witnesses": witnesses})
    return {"status": "added", "count": len(witnesses)}


@router.delete("/{index}")
def remove_witness(
    case_id: str,
    prep_id: str,
    index: int,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Remove a witness by index."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    witnesses = state.get("witnesses", [])
    if index < 0 or index >= len(witnesses):
        raise HTTPException(status_code=404, detail="Witness not found")
    removed = witnesses.pop(index)
    cm.save_prep_state(case_id, prep_id, {"witnesses": witnesses})
    return {"status": "removed", "name": removed.get("name", "")}


@router.put("/{index}")
def update_witness(
    case_id: str,
    prep_id: str,
    index: int,
    body: CreateWitnessRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a witness by index."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    witnesses = state.get("witnesses", [])
    if index < 0 or index >= len(witnesses):
        raise HTTPException(status_code=404, detail="Witness not found")
    witnesses[index] = {**witnesses[index], **body.model_dump()}
    cm.save_prep_state(case_id, prep_id, {"witnesses": witnesses})
    return {"status": "updated", "name": body.name}


@router.get("/cross-examination", response_model=List[CrossExamPoint])
def get_cross_examination(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get cross-examination plan."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("cross_examination_plan", [])


@router.get("/direct-examination")
def get_direct_examination(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get direct examination plan."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("direct_examination_plan", [])
