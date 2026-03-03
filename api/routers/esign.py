# ---- E-Sign Router -------------------------------------------------------
# Dropbox Sign integration: send documents for signature, track status.
# Wraps core/esign.py (class-based ESignManager API)

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/esign", tags=["E-Signature"])


# ---- Schemas -------------------------------------------------------------

class SignatureRequest(BaseModel):
    file_key: str
    signer_name: str
    signer_email: str
    title: str = ""
    subject: str = ""
    message: str = ""


def _get_esign_manager(case_id: str):
    """Get an ESignManager instance for a case."""
    from core.esign import ESignManager
    data_dir = get_data_dir()
    case_dir = os.path.join(data_dir, "cases", case_id)
    return ESignManager(case_dir)


# ---- Endpoints -----------------------------------------------------------

@router.post("/send")
def send_for_signature(
    case_id: str,
    body: SignatureRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Send a document for e-signature via Dropbox Sign."""
    try:
        mgr = _get_esign_manager(case_id)
        cm = get_case_manager()
        # Resolve file path from case files
        data_dir = get_data_dir()
        file_path = os.path.join(data_dir, "cases", case_id, "source_docs", body.file_key)
        result = mgr.send_request(
            file_path=file_path,
            signers=[{"name": body.signer_name, "email_address": body.signer_email}],
            title=body.title,
            subject=body.subject,
            message=body.message,
        )
        return {"status": "sent", "signature_request_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests")
def list_signature_requests(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all signature requests for a case."""
    try:
        mgr = _get_esign_manager(case_id)
        return {"items": mgr.list_requests()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests/{request_id}/status")
def check_signature_status(
    case_id: str,
    request_id: str,
    user: dict = Depends(get_current_user),
):
    """Check status of a signature request."""
    try:
        mgr = _get_esign_manager(case_id)
        status = mgr.get_request_status(request_id)
        if not status:
            raise HTTPException(status_code=404, detail="Request not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests/{request_id}/download")
def download_signed(
    case_id: str,
    request_id: str,
    user: dict = Depends(get_current_user),
):
    """Download a signed document."""
    try:
        from fastapi.responses import FileResponse
        mgr = _get_esign_manager(case_id)
        file_path = mgr.download_signed(request_id)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Signed document not available")
        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=f"signed_{request_id}.pdf",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
