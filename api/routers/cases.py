# ---- Cases Router --------------------------------------------------------
# Full case and preparation CRUD.
#
# All endpoint functions use sync `def` (not `async def`) so FastAPI
# runs them in a thread pool automatically.
#
# Fix #13: Pagination on list_cases, list_preparations
# Fix #14: Input length validation on create/update models

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_user_manager
from api.schemas import (
    CASE_NAME_MAX,
    DESCRIPTION_MAX,
    DIRECTIVE_MAX,
    SHORT_TEXT_MAX,
    PaginatedResponse,
    paginate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["Cases"])


# ---- Response Models -----------------------------------------------------

class CaseResponse(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    case_type: str = "criminal"
    case_category: str = ""
    case_subcategory: str = ""
    client_name: str = ""
    jurisdiction: str = ""
    phase: str = "active"
    sub_phase: str = ""
    status: str = "active"
    pinned: bool = False
    assigned_to: List[str] = Field(default_factory=list)
    created_at: str = ""
    last_updated: str = ""

    model_config = {"extra": "allow"}


class CreateCaseRequest(BaseModel):
    case_name: str = Field(..., min_length=1, max_length=CASE_NAME_MAX)
    description: str = Field(default="", max_length=DESCRIPTION_MAX)
    case_category: str = Field(default="", max_length=SHORT_TEXT_MAX)
    case_subcategory: str = Field(default="", max_length=SHORT_TEXT_MAX)
    case_type: str = Field(default="criminal", max_length=50)
    client_name: str = Field(default="", max_length=CASE_NAME_MAX)
    jurisdiction: str = Field(default="", max_length=SHORT_TEXT_MAX)


class CreateCaseResponse(BaseModel):
    case_id: str
    message: str


class UpdateCaseRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=CASE_NAME_MAX)
    description: Optional[str] = Field(default=None, max_length=DESCRIPTION_MAX)
    case_type: Optional[str] = Field(default=None, max_length=50)
    case_category: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX)
    case_subcategory: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX)
    client_name: Optional[str] = Field(default=None, max_length=CASE_NAME_MAX)
    jurisdiction: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX)


class SetPhaseRequest(BaseModel):
    phase: str = Field(..., max_length=50)
    sub_phase: str = Field(default="", max_length=50)


class PhaseResponse(BaseModel):
    phase: str
    sub_phase: str = ""


class PrepResponse(BaseModel):
    id: str
    type: str = "trial"
    name: str = ""
    created_at: str = ""
    last_updated: str = ""


class CreatePrepRequest(BaseModel):
    prep_type: str = Field(default="trial", max_length=50)
    name: str = Field(default="", max_length=CASE_NAME_MAX)


class AddDirectiveRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=DIRECTIVE_MAX)
    category: str = Field(default="instruction", max_length=50)


# ---- Case CRUD ----------------------------------------------------------

@router.get("", response_model=PaginatedResponse)
def list_cases(
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """List cases accessible to the current user (paginated)."""
    cm = get_case_manager()
    um = get_user_manager()

    allowed = um.get_cases_for_user(user["id"])
    if allowed is None:  # admin
        cases = cm.list_cases(include_archived=include_archived)
    else:
        cases = cm.list_cases_for_user(allowed, include_archived=include_archived)

    return paginate(cases, page, per_page)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateCaseResponse)
def create_case(
    body: CreateCaseRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new case."""
    cm = get_case_manager()
    case_id = cm.create_case(
        case_name=body.case_name,
        description=body.description,
        case_category=body.case_category,
        case_subcategory=body.case_subcategory,
        case_type=body.case_type,
        client_name=body.client_name,
        jurisdiction=body.jurisdiction,
        assigned_to=[user["id"]],
    )
    return CreateCaseResponse(case_id=case_id, message=f"Case '{body.case_name}' created")


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str, user: dict = Depends(get_current_user)):
    """Get case metadata."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")
    return meta


@router.patch("/{case_id}")
def update_case(
    case_id: str,
    body: UpdateCaseRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update case metadata."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")

    updates = body.model_dump(exclude_none=True)
    if "name" in updates:
        cm.rename_case(case_id, updates["name"])
        return {"status": "renamed", "note": "Case ID may have changed"}

    for k, v in updates.items():
        meta[k] = v
    from datetime import datetime
    meta["last_updated"] = datetime.now().isoformat()
    cm.storage.update_case_metadata(case_id, meta)
    return {"status": "updated"}


@router.delete("/{case_id}")
def delete_case(
    case_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Delete a case permanently (admin only)."""
    cm = get_case_manager()
    if not cm.get_case_metadata(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    cm.delete_case(case_id)
    return {"status": "deleted", "case_id": case_id}


# ---- Phase Management ----------------------------------------------------

@router.post("/{case_id}/phase", response_model=PhaseResponse)
def set_phase(
    case_id: str,
    body: SetPhaseRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Set case phase (active/closed/archived) and optional sub-phase."""
    cm = get_case_manager()
    try:
        cm.set_phase(case_id, body.phase, body.sub_phase)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PhaseResponse(phase=body.phase, sub_phase=body.sub_phase)


@router.get("/{case_id}/phase", response_model=PhaseResponse)
def get_phase(case_id: str, user: dict = Depends(get_current_user)):
    """Get current phase and sub-phase."""
    cm = get_case_manager()
    phase, sub_phase = cm.get_phase(case_id)
    return PhaseResponse(phase=phase, sub_phase=sub_phase)


# ---- Activity Log --------------------------------------------------------

@router.get("/{case_id}/activity")
def get_activity(
    case_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """Get case activity log."""
    cm = get_case_manager()
    return cm.get_activity_log(case_id, limit=limit)


# ---- Deadlines -----------------------------------------------------------

@router.get("/{case_id}/deadlines")
def get_deadlines(case_id: str, user: dict = Depends(get_current_user)):
    """Get all deadlines for a case."""
    cm = get_case_manager()
    return cm.get_all_deadlines(case_id)


# ---- Preparations --------------------------------------------------------

@router.get("/{case_id}/preparations", response_model=PaginatedResponse)
def list_preparations(
    case_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """List all preparations for a case (paginated)."""
    cm = get_case_manager()
    preps = cm.list_preparations(case_id)
    return paginate(preps, page, per_page)


@router.post("/{case_id}/preparations", status_code=status.HTTP_201_CREATED)
def create_preparation(
    case_id: str,
    body: CreatePrepRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new preparation."""
    cm = get_case_manager()
    prep_id = cm.create_preparation(case_id, body.prep_type, body.name)
    return {"prep_id": prep_id}


@router.get("/{case_id}/preparations/{prep_id}")
def get_preparation_state(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Load the full state for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        return {}
    return state


@router.delete("/{case_id}/preparations/{prep_id}")
def delete_preparation(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a preparation."""
    cm = get_case_manager()
    cm.delete_preparation(case_id, prep_id)
    return {"status": "deleted", "prep_id": prep_id}


# ---- Directives ---------------------------------------------------------

@router.get("/{case_id}/directives")
def get_directives(case_id: str, user: dict = Depends(get_current_user)):
    """Get attorney directives for a case."""
    cm = get_case_manager()
    return cm.load_directives(case_id)


@router.post("/{case_id}/directives")
def add_directive(
    case_id: str,
    body: AddDirectiveRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add an attorney directive."""
    cm = get_case_manager()
    directive_id = cm.save_directive(case_id, body.text, body.category)
    return {"directive_id": directive_id}


@router.put("/{case_id}/directives/{directive_id}")
def update_directive(
    case_id: str,
    directive_id: str,
    body: AddDirectiveRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update an attorney directive."""
    cm = get_case_manager()
    cm.update_directive(case_id, directive_id, body.text)
    return {"status": "updated", "directive_id": directive_id}


@router.delete("/{case_id}/directives/{directive_id}")
def delete_directive(
    case_id: str,
    directive_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete an attorney directive."""
    cm = get_case_manager()
    cm.delete_directive(case_id, directive_id)
    return {"status": "deleted", "directive_id": directive_id}
