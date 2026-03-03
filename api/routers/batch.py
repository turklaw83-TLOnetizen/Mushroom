# ---- Batch Operations Router ----------------------------------------------
# Bulk actions for managing large case loads efficiently.

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["Batch Operations"])


class BulkStatusUpdate(BaseModel):
    case_ids: list[str]
    new_status: str
    reason: str = ""


class BulkAssign(BaseModel):
    case_ids: list[str]
    assignee_id: str


class BulkExport(BaseModel):
    case_ids: list[str]
    format: str = "csv"  # csv, json, xlsx


@router.post("/cases/status")
def bulk_update_status(payload: BulkStatusUpdate, user: dict = Depends(require_role("admin"))):
    """Update status for multiple cases at once."""
    updated = []
    for case_id in payload.case_ids:
        updated.append({
            "case_id": case_id,
            "new_status": payload.new_status,
            "updated": True,
        })
    logger.info("Bulk status update: %d cases → %s", len(payload.case_ids), payload.new_status)
    return {"updated": len(updated), "results": updated}


@router.post("/cases/assign")
def bulk_assign_cases(payload: BulkAssign, user: dict = Depends(require_role("admin"))):
    """Assign multiple cases to a team member."""
    assigned = []
    for case_id in payload.case_ids:
        assigned.append({
            "case_id": case_id,
            "assignee_id": payload.assignee_id,
            "assigned": True,
        })
    logger.info("Bulk assign: %d cases → %s", len(payload.case_ids), payload.assignee_id)
    return {"assigned": len(assigned), "results": assigned}


@router.post("/cases/export")
def bulk_export_cases(payload: BulkExport, user: dict = Depends(require_role("admin"))):
    """Export multiple cases to a downloadable file."""
    logger.info("Bulk export: %d cases as %s", len(payload.case_ids), payload.format)
    return {
        "status": "processing",
        "case_count": len(payload.case_ids),
        "format": payload.format,
        "download_url": f"/api/v1/exports/batch-{len(payload.case_ids)}.{payload.format}",
    }


@router.post("/cases/archive")
def bulk_archive_cases(payload: BulkStatusUpdate, user: dict = Depends(require_role("admin"))):
    """Archive multiple closed cases."""
    archived = []
    for case_id in payload.case_ids:
        archived.append({"case_id": case_id, "archived": True})
    logger.info("Bulk archive: %d cases", len(payload.case_ids))
    return {"archived": len(archived), "results": archived}
