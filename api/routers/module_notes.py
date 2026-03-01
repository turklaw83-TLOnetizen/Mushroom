# ---- Module Notes Router --------------------------------------------------
# Per-module attorney notes that persist across re-analysis.
# Notes are stored separately from analysis results and are injected
# into the AI context for subsequent analysis runs.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/notes",
    tags=["Module Notes"],
)


# ---- Schemas -------------------------------------------------------------

class ModuleNoteResponse(BaseModel):
    module_name: str = ""
    content: str = ""


class SaveNoteRequest(BaseModel):
    content: str = Field(default="", max_length=50000)


class AllNotesResponse(BaseModel):
    notes: List[ModuleNoteResponse] = Field(default_factory=list)


# ---- Endpoints -----------------------------------------------------------

from core.module_definitions import MODULE_NAMES


@router.get("", response_model=AllNotesResponse)
def list_all_notes(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all module notes for a preparation."""
    cm = get_case_manager()
    notes = []
    for module in MODULE_NAMES:
        content = cm.load_module_notes(case_id, prep_id, module)
        if content:
            notes.append({"module_name": module, "content": content})
    return {"notes": notes}


@router.get("/{module_name}", response_model=ModuleNoteResponse)
def get_note(
    case_id: str,
    prep_id: str,
    module_name: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific module note."""
    cm = get_case_manager()
    content = cm.load_module_notes(case_id, prep_id, module_name)
    return {"module_name": module_name, "content": content or ""}


@router.put("/{module_name}")
def save_note(
    case_id: str,
    prep_id: str,
    module_name: str,
    body: SaveNoteRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save or update a module note. Persists through re-analysis."""
    cm = get_case_manager()
    cm.save_module_notes(case_id, prep_id, module_name, body.content)
    return {"status": "saved", "module_name": module_name}


@router.delete("/{module_name}")
def delete_note(
    case_id: str,
    prep_id: str,
    module_name: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a module note."""
    cm = get_case_manager()
    cm.save_module_notes(case_id, prep_id, module_name, "")
    return {"status": "deleted", "module_name": module_name}
