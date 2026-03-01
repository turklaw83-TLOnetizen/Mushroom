# ---- Documents Router ----------------------------------------------------
# Major document drafting (outlines, sections, citations).

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


class DraftResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    title: str = ""
    type: str = ""
    content: str = ""
    created_at: str = ""
    last_updated: str = ""

    model_config = {"extra": "allow"}


class CreateDraftRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="brief", max_length=50)
    content: str = Field(default="")


@router.get("/drafts/{case_id}", response_model=List[DraftResponse])
def list_drafts(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List major document drafts for a case."""
    cm = get_case_manager()
    try:
        return cm.load_major_drafts(case_id) or []
    except Exception:
        return []


@router.post("/drafts/{case_id}")
def save_draft(
    case_id: str,
    body: CreateDraftRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save a document draft."""
    cm = get_case_manager()
    try:
        draft_id = cm.save_major_draft(case_id, body.model_dump())
        return {"status": "saved", "id": draft_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/drafts/{case_id}/{draft_id}")
def delete_draft(
    case_id: str,
    draft_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a document draft."""
    cm = get_case_manager()
    try:
        cm.delete_major_draft(case_id, draft_id)
        return {"status": "deleted", "id": draft_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/drafts/{case_id}/{draft_id}")
def update_draft(
    case_id: str,
    draft_id: str,
    body: CreateDraftRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a document draft."""
    cm = get_case_manager()
    try:
        cm.delete_major_draft(case_id, draft_id)
        new_id = cm.save_major_draft(case_id, {"id": draft_id, **body.model_dump()})
        return {"status": "updated", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Research Data -------------------------------------------------------

@router.get("/research/{case_id}/{prep_id}")
def get_research(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get legal research data for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("legal_research_data", [])
