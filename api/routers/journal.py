# ---- Journal Router ------------------------------------------------------
# Case journal entries for attorney notes, observations, and reflections.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/journal", tags=["Journal"])


# ---- Schemas -------------------------------------------------------------

class JournalEntry(BaseModel):
    id: str = ""
    text: str = ""
    category: str = "General"
    timestamp: str = ""

    model_config = {"extra": "allow"}


class CreateJournalRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    category: str = Field(default="General", max_length=100)


class UpdateJournalRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    category: str = Field(default="General", max_length=100)


# ---- Endpoints -----------------------------------------------------------

@router.get("", response_model=List[JournalEntry])
def list_journal(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all journal entries for a case (newest first)."""
    cm = get_case_manager()
    return cm.load_journal(case_id)


@router.post("")
def add_entry(
    case_id: str,
    body: CreateJournalRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a journal entry."""
    cm = get_case_manager()
    entry_id = cm.add_journal_entry(case_id, body.text, body.category)
    return {"entry_id": entry_id}


@router.put("/{entry_id}")
def update_entry(
    case_id: str,
    entry_id: str,
    body: UpdateJournalRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a journal entry."""
    cm = get_case_manager()
    entries = cm.load_journal(case_id)
    updated = False
    for entry in entries:
        if entry.get("id") == entry_id:
            entry["text"] = body.text
            entry["category"] = body.category
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    cm.storage.save_json(case_id, "journal.json", entries)
    return {"status": "updated", "entry_id": entry_id}


@router.delete("/{entry_id}")
def delete_entry(
    case_id: str,
    entry_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a journal entry."""
    cm = get_case_manager()
    cm.delete_journal_entry(case_id, entry_id)
    return {"status": "deleted", "entry_id": entry_id}
