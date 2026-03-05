# ---- CRM Router ----------------------------------------------------------
# CRUD for clients, case linking, intake forms.
# Wraps core/crm.py functions via the API.

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["CRM"])


# ---- Schemas -------------------------------------------------------------

class ClientCreate(BaseModel):
    first_name: str = Field(default="", max_length=200)
    last_name: str = Field(default="", max_length=200)
    name: str = Field(default="", max_length=400)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=30)
    mailing_address: str = Field(default="", max_length=1000)
    home_address: str = Field(default="", max_length=1000)
    home_same_as_mailing: bool = False
    notes: str = Field(default="", max_length=10000)
    referral_source: str = Field(default="", max_length=200)
    tags: List[str] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=200)
    last_name: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=30)
    mailing_address: Optional[str] = Field(default=None, max_length=1000)
    home_address: Optional[str] = Field(default=None, max_length=1000)
    notes: Optional[str] = Field(default=None, max_length=10000)
    intake_status: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[List[str]] = None


class LinkRequest(BaseModel):
    case_id: str


class IntakeAnswers(BaseModel):
    template_key: str = Field(..., max_length=100)
    answers: dict = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def limit_answers_size(cls, v):
        import json
        if len(json.dumps(v, default=str)) > 100_000:
            raise ValueError("Intake answers too large (max 100KB)")
        return v


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
        logger.exception("Failed to list clients")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to get client")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to create client")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to update client")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to delete client")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to link client to case")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to unlink client from case")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to get client cases")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to get intake templates")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to save intake")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to get intake answers")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Rep Agreement -------------------------------------------------------

@router.post("/clients/{client_id}/rep-agreement")
async def upload_rep_agreement(
    client_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Upload a representation agreement for a client. Replaces any existing."""
    try:
        from core.crm import save_rep_agreement
        data = await file.read()
        filename = file.filename or "rep_agreement"
        user_name = user.get("name", user.get("user_id", ""))
        if not save_rep_agreement(client_id, data, filename, uploaded_by=user_name):
            raise HTTPException(status_code=404, detail="Client not found")
        return {"status": "uploaded", "filename": filename}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to upload rep agreement")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/clients/{client_id}/rep-agreement")
def download_rep_agreement(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Download the client's rep agreement."""
    try:
        from core.crm import get_rep_agreement_path, get_rep_agreement_metadata
        path = get_rep_agreement_path(client_id)
        if not path:
            raise HTTPException(status_code=404, detail="No rep agreement found")
        meta = get_rep_agreement_metadata(client_id)
        filename = meta.get("filename", "rep_agreement") if meta else "rep_agreement"
        return FileResponse(path, filename=filename)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to download rep agreement")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/clients/{client_id}/rep-agreement")
def delete_rep_agreement(
    client_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete the client's rep agreement."""
    try:
        from core.crm import delete_rep_agreement as _delete_rep
        if not _delete_rep(client_id):
            raise HTTPException(status_code=404, detail="No rep agreement found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete rep agreement")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to get CRM stats")
        raise HTTPException(status_code=500, detail="Internal server error")
