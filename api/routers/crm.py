# ---- CRM Router ----------------------------------------------------------
# CRUD for clients, case linking, intake forms.
# Wraps core/crm.py functions via the API.

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["CRM"])


# ---- Schemas -------------------------------------------------------------

class ClientCreate(BaseModel):
    first_name: str = ""
    last_name: str = ""
    name: str = ""  # Legacy fallback
    email: str = ""
    phone: str = ""
    mailing_address: str = ""
    home_address: str = ""
    home_same_as_mailing: bool = False
    notes: str = ""
    referral_source: str = ""
    tags: List[str] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    home_address: Optional[str] = None
    notes: Optional[str] = None
    intake_status: Optional[str] = None
    tags: Optional[List[str]] = None


class LinkRequest(BaseModel):
    case_id: str


class IntakeAnswers(BaseModel):
    template_key: str
    answers: dict


# ---- Endpoints -----------------------------------------------------------

@router.get("/clients")
def list_clients(
    q: str = "",
    user: dict = Depends(get_current_user),
):
    """List all clients, optionally filtered by search query."""
    try:
        from core.crm import load_clients, search_clients
        if q:
            return {"items": search_clients(q)}
        return {"items": load_clients()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{client_id}")
def get_client(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single client by ID."""
    try:
        from core.crm import get_client as _get
        client = _get(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clients")
def create_client(
    body: ClientCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new client."""
    try:
        from core.crm import add_client
        client_id = add_client(
            first_name=body.first_name,
            last_name=body.last_name,
            name=body.name,
            email=body.email,
            phone=body.phone,
            mailing_address=body.mailing_address,
            home_address=body.home_address,
            home_same_as_mailing=body.home_same_as_mailing,
            referral_source=body.referral_source,
            tags=body.tags,
        )
        return {"id": client_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/clients/{client_id}")
def update_client(
    client_id: str,
    body: ClientUpdate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a client's fields."""
    try:
        from core.crm import update_client as _update
        updates = body.model_dump(exclude_none=True)
        if not _update(client_id, updates):
            raise HTTPException(status_code=404, detail="Client not found")
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clients/{client_id}")
def delete_client(
    client_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Delete a client."""
    try:
        from core.crm import delete_client as _delete
        if not _delete(client_id):
            raise HTTPException(status_code=404, detail="Client not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Case Linking --------------------------------------------------------

@router.post("/clients/{client_id}/link")
def link_to_case(
    client_id: str,
    body: LinkRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Link a client to a case."""
    try:
        from core.crm import link_client_to_case
        if not link_client_to_case(client_id, body.case_id):
            raise HTTPException(status_code=404, detail="Client not found")
        return {"status": "linked"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clients/{client_id}/link/{case_id}")
def unlink_from_case(
    client_id: str,
    case_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Unlink a client from a case."""
    try:
        from core.crm import unlink_client_from_case
        unlink_client_from_case(client_id, case_id)
        return {"status": "unlinked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{client_id}/cases")
def client_cases(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all case IDs linked to a client."""
    try:
        from core.crm import get_cases_for_client
        return {"case_ids": get_cases_for_client(client_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Intake Forms --------------------------------------------------------

@router.get("/intake/templates")
def intake_templates(
    user: dict = Depends(get_current_user),
):
    """Get available intake form templates."""
    try:
        from core.crm import get_intake_templates
        return {"templates": get_intake_templates()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clients/{client_id}/intake")
def save_intake(
    client_id: str,
    body: IntakeAnswers,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save intake form answers for a client."""
    try:
        from core.crm import save_intake_answers
        save_intake_answers(client_id, body.template_key, body.answers)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{client_id}/intake")
def get_intake(
    client_id: str,
    template_key: str = "",
    user: dict = Depends(get_current_user),
):
    """Get intake form answers for a client."""
    try:
        from core.crm import get_intake_answers
        return {"answers": get_intake_answers(client_id, template_key)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Stats ---------------------------------------------------------------

@router.get("/stats")
def crm_stats(
    user: dict = Depends(get_current_user),
):
    """Get CRM statistics for dashboard."""
    try:
        from core.crm import get_crm_stats
        return get_crm_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
