# ---- Cloud Backup Router -------------------------------------------------
# Backup/restore via Dropbox sync or Backblaze B2.
# Wraps core/cloud_backup.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backup", tags=["Backup"])


# ---- Schemas -------------------------------------------------------------

class BackupRequest(BaseModel):
    case_id: str = ""  # Empty = full backup
    target: str = "dropbox"  # dropbox | b2


# ---- Endpoints -----------------------------------------------------------

@router.get("/status")
def backup_status(
    user: dict = Depends(require_role("admin")),
):
    """Check which backup targets are available."""
    try:
        from core.cloud_backup import DropboxSyncBackup, B2Backup
        dropbox = DropboxSyncBackup()
        b2 = B2Backup()
        return {
            "dropbox": {"available": dropbox.is_available()},
            "b2": {"available": b2.is_available()},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
def run_backup(
    body: BackupRequest,
    user: dict = Depends(require_role("admin")),
):
    """Trigger a backup (case-specific or full)."""
    try:
        import os
        data_dir = os.path.join(os.getcwd(), "data")

        if body.target == "b2":
            from core.cloud_backup import B2Backup
            b2 = B2Backup()
            if not b2.is_available():
                raise HTTPException(status_code=400, detail="B2 not configured")
            if body.case_id:
                result = b2.backup_case_archive(
                    os.path.join(data_dir, "cases", body.case_id)
                )
            else:
                result = b2.backup_full(data_dir)
            return {"status": "complete", "result": result}
        else:
            from core.cloud_backup import DropboxSyncBackup
            dropbox = DropboxSyncBackup()
            if not dropbox.is_available():
                raise HTTPException(status_code=400, detail="Dropbox folder not found")
            if body.case_id:
                result = dropbox.backup_case(data_dir, body.case_id)
            else:
                result = dropbox.backup_full(data_dir)
            return {"status": "complete", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def list_backups(
    target: str = "dropbox",
    user: dict = Depends(require_role("admin")),
):
    """List available backups."""
    try:
        if target == "b2":
            from core.cloud_backup import B2Backup
            return {"items": B2Backup().list_backups()}
        else:
            from core.cloud_backup import DropboxSyncBackup
            return {"items": DropboxSyncBackup().list_backups()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
