# ---- Module Notes Router --------------------------------------------------
# Per-module attorney notes CRUD.
# Each analysis module (e.g., "strategist", "cross_examiner") can have
# attorney notes attached.  Stored via CaseManager.save_module_notes().

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import sanitize_path_param

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/notes",
    tags=["Module Notes"],
)


class NoteBody(BaseModel):
    text: str = Field("", max_length=50000)


# ---- Get Notes -----------------------------------------------------------

@router.get("/{module_key}")
def get_module_notes(
    case_id: str,
    prep_id: str,
    module_key: str,
    user: dict = Depends(get_current_user),
):
    """Get attorney notes for a specific module."""
    module_key = sanitize_path_param(module_key, "module_key")
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()
        text = cm.load_module_notes(case_id, prep_id, module_key)
        return {"module_key": module_key, "text": text or ""}
    except Exception as e:
        logger.exception("Failed to load module notes")
        raise HTTPException(status_code=500, detail="Failed to load notes")


# ---- Save / Update Notes -------------------------------------------------

@router.put("/{module_key}")
def save_module_notes(
    case_id: str,
    prep_id: str,
    module_key: str,
    body: NoteBody,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save or update attorney notes for a specific module."""
    module_key = sanitize_path_param(module_key, "module_key")
    try:
        from api.deps import get_case_manager

        cm = get_case_manager()

        # Verify case + prep exist
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        cm.save_module_notes(case_id, prep_id, module_key, body.text)
        return {"status": "saved", "module_key": module_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to save module notes")
        raise HTTPException(status_code=500, detail="Failed to save notes")
