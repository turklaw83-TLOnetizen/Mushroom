# ---- E-Sign Router -------------------------------------------------------
# Dropbox Sign integration: send documents for signature, track status.
# Wraps core/esign.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

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


# ---- Endpoints -----------------------------------------------------------

@router.post("/send")
def send_for_signature(
    case_id: str,
    body: SignatureRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Send a document for e-signature via Dropbox Sign."""
    try:
        from core.esign import create_signature_request
        result = create_signature_request(
            case_id,
            file_key=body.file_key,
            signer_name=body.signer_name,
            signer_email=body.signer_email,
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
        from core.esign import list_requests
        return {"items": list_requests(case_id)}
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
        from core.esign import get_request_status
        status = get_request_status(case_id, request_id)
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
        from core.esign import download_signed_document
        from fastapi.responses import StreamingResponse
        data = download_signed_document(case_id, request_id)
        if not data:
            raise HTTPException(status_code=404, detail="Signed document not available")
        return StreamingResponse(
            iter([data]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=signed_{request_id}.pdf"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
