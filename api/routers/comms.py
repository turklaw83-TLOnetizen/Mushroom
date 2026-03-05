# ---- Client Communications Router -----------------------------------------
# Review queue, templates, log, settings, trigger scanning, and sending.

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/comms",
    tags=["Communications"],
)


# ---- Request Models ------------------------------------------------------

class ApproveCommRequest(BaseModel):
    edited_body: Optional[str] = Field(default=None, max_length=50000)
    edited_sms: Optional[str] = Field(default=None, max_length=500)


class DismissCommRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class ManualCommRequest(BaseModel):
    client_id: str = Field(..., max_length=50)
    case_id: str = Field(default="", max_length=64)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)
    sms_body: str = Field(default="", max_length=500)
    channel: str = Field(default="email", max_length=10)


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    trigger_type: str = Field(..., max_length=50)
    channel: str = Field(default="email", max_length=10)
    subject_template: str = Field(default="", max_length=500)
    body_template: str = Field(default="", max_length=10000)
    sms_template: str = Field(default="", max_length=500)
    ai_enhance: bool = True


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    trigger_type: Optional[str] = Field(default=None, max_length=50)
    channel: Optional[str] = Field(default=None, max_length=10)
    subject_template: Optional[str] = Field(default=None, max_length=500)
    body_template: Optional[str] = Field(default=None, max_length=10000)
    sms_template: Optional[str] = Field(default=None, max_length=500)
    ai_enhance: Optional[bool] = None
    active: Optional[bool] = None


class UpdateSettingsRequest(BaseModel):
    triggers: Optional[dict] = None
    firm_name: Optional[str] = Field(default=None, max_length=200)
    default_sender_name: Optional[str] = Field(default=None, max_length=200)


# ---- Queue Endpoints -----------------------------------------------------

@router.get("/queue")
def list_queue(
    status: str = "",
    user: dict = Depends(get_current_user),
):
    """List communications queue, optionally filtered by status."""
    try:
        from core.comms import get_queue
        return {"items": get_queue(status_filter=status)}
    except Exception:
        logger.exception("Failed to list comm queue")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/queue/stats")
def queue_stats(
    user: dict = Depends(get_current_user),
):
    """Get queue item counts by status."""
    try:
        from core.comms import get_queue_stats
        return get_queue_stats()
    except Exception:
        logger.exception("Failed to get queue stats")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/queue/{comm_id}")
def get_queue_item(
    comm_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single queue item by ID."""
    try:
        from core.comms import get_queue_item as _get_item
        item = _get_item(comm_id)
        if not item:
            raise HTTPException(status_code=404, detail="Communication not found")
        return item
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get queue item")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/queue/{comm_id}/approve")
def approve_comm(
    comm_id: str,
    body: ApproveCommRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Approve a pending communication (with optional edits)."""
    try:
        from core.comms import approve_comm as _approve
        user_name = user.get("name", user.get("user_id", ""))
        if not _approve(comm_id, user_name, body.edited_body, body.edited_sms):
            raise HTTPException(status_code=404, detail="Communication not found or already processed")
        return {"status": "approved"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to approve communication")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/queue/{comm_id}/dismiss")
def dismiss_comm(
    comm_id: str,
    body: DismissCommRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Dismiss a pending communication."""
    try:
        from core.comms import dismiss_comm as _dismiss
        user_name = user.get("name", user.get("user_id", ""))
        if not _dismiss(comm_id, body.reason, user_name):
            raise HTTPException(status_code=404, detail="Communication not found or already processed")
        return {"status": "dismissed"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to dismiss communication")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/queue/manual")
def add_manual_comm(
    body: ManualCommRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a manual communication to the queue."""
    try:
        from core.comms import add_to_queue
        comm_id = add_to_queue(
            client_id=body.client_id,
            trigger_type="custom",
            subject=body.subject,
            body_html=body.body,
            body_sms=body.sms_body,
            case_id=body.case_id,
            channel=body.channel,
        )
        return {"status": "queued", "comm_id": comm_id}
    except Exception:
        logger.exception("Failed to add manual communication")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Send / Scan Endpoints -----------------------------------------------

@router.post("/send")
async def send_approved(
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Send all approved communications."""
    try:
        from core.comms import send_approved_comms
        result = await asyncio.to_thread(send_approved_comms)
        return result
    except Exception:
        logger.exception("Failed to send communications")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scan")
async def scan_triggers(
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run the trigger scanner to generate new draft communications."""
    try:
        from core.comms import scan_triggers as _scan
        count = await asyncio.to_thread(_scan)
        return {"status": "scanned", "new_drafts": count}
    except Exception:
        logger.exception("Failed to scan triggers")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Template Endpoints ---------------------------------------------------

@router.get("/templates")
def list_templates(
    user: dict = Depends(get_current_user),
):
    """List all communication templates."""
    try:
        from core.comms import list_templates
        return {"items": list_templates()}
    except Exception:
        logger.exception("Failed to list templates")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/templates")
def create_template(
    body: CreateTemplateRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new communication template."""
    try:
        from core.comms import create_template
        tpl_id = create_template(
            name=body.name,
            trigger_type=body.trigger_type,
            channel=body.channel,
            subject_template=body.subject_template,
            body_template=body.body_template,
            sms_template=body.sms_template,
            ai_enhance=body.ai_enhance,
        )
        return {"status": "created", "template_id": tpl_id}
    except Exception:
        logger.exception("Failed to create template")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/templates/{template_id}")
def update_template(
    template_id: str,
    body: UpdateTemplateRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update an existing template."""
    try:
        from core.comms import update_template
        updates = body.model_dump(exclude_none=True)
        if not updates:
            return {"status": "no_changes"}
        if not update_template(template_id, updates):
            raise HTTPException(status_code=404, detail="Template not found")
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update template")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Delete a template."""
    try:
        from core.comms import delete_template
        if not delete_template(template_id):
            raise HTTPException(status_code=404, detail="Template not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete template")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Log Endpoints --------------------------------------------------------

@router.get("/log")
def get_log(
    client_id: str = "",
    case_id: str = "",
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get communication log, optionally filtered."""
    try:
        from core.comms import get_comm_log
        return {"items": get_comm_log(limit=limit, client_id=client_id, case_id=case_id)}
    except Exception:
        logger.exception("Failed to get comm log")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/log/client/{client_id}")
def get_client_log(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get communication log for a specific client."""
    try:
        from core.comms import get_client_comm_log
        return {"items": get_client_comm_log(client_id)}
    except Exception:
        logger.exception("Failed to get client comm log")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Settings Endpoints ---------------------------------------------------

@router.get("/settings")
def get_settings(
    user: dict = Depends(get_current_user),
):
    """Get communication settings."""
    try:
        from core.comms import get_comm_settings
        return get_comm_settings()
    except Exception:
        logger.exception("Failed to get comm settings")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/settings")
def update_settings(
    body: UpdateSettingsRequest,
    user: dict = Depends(require_role("admin")),
):
    """Update communication settings."""
    try:
        from core.comms import update_comm_settings
        updates = body.model_dump(exclude_none=True)
        if not updates:
            return {"status": "no_changes"}
        settings = update_comm_settings(updates)
        return settings
    except Exception:
        logger.exception("Failed to update comm settings")
        raise HTTPException(status_code=500, detail="Internal server error")
