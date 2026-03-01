# ---- Evidence Router -----------------------------------------------------
# Evidence tagging and foundations for a case preparation.

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/preparations/{prep_id}/evidence", tags=["Evidence"])


class EvidenceItem(BaseModel):
    id: str = ""
    description: str = ""
    type: str = ""
    source: str = ""
    foundation: str = ""
    admissibility_notes: str = ""
    tags: List[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class CreateEvidenceRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    type: str = Field(default="", max_length=100)
    source: str = Field(default="", max_length=500)
    foundation: str = Field(default="", max_length=2000)
    tags: List[str] = Field(default_factory=list)


@router.get("", response_model=List[EvidenceItem])
def list_evidence(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """List all evidence items for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("evidence_foundations", [])


@router.post("")
def add_evidence(
    case_id: str,
    prep_id: str,
    body: CreateEvidenceRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add an evidence item."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    evidence = state.get("evidence_foundations", [])
    import uuid
    item = {"id": str(uuid.uuid4())[:8], **body.model_dump()}
    evidence.append(item)
    cm.save_prep_state(case_id, prep_id, {"evidence_foundations": evidence})
    return {"status": "added", "id": item["id"]}


@router.delete("/{evidence_id}")
def remove_evidence(
    case_id: str,
    prep_id: str,
    evidence_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Remove an evidence item by ID."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    evidence = state.get("evidence_foundations", [])
    new_evidence = [e for e in evidence if e.get("id") != evidence_id]
    if len(new_evidence) == len(evidence):
        raise HTTPException(status_code=404, detail="Evidence not found")
    cm.save_prep_state(case_id, prep_id, {"evidence_foundations": new_evidence})
    return {"status": "removed", "id": evidence_id}


@router.put("/{evidence_id}")
def update_evidence(
    case_id: str,
    prep_id: str,
    evidence_id: str,
    body: CreateEvidenceRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update an evidence item by ID."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    evidence = state.get("evidence_foundations", [])
    updated = False
    for i, e in enumerate(evidence):
        if e.get("id") == evidence_id:
            evidence[i] = {"id": evidence_id, **body.model_dump()}
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Evidence not found")
    cm.save_prep_state(case_id, prep_id, {"evidence_foundations": evidence})
    return {"status": "updated", "id": evidence_id}
