# ---- Security Dashboard Router -------------------------------------------
# File scanning results, access logs, and encryption status for cases.

import json
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_storage_backend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/security", tags=["Security"])

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


# ---- Response Models -----------------------------------------------------

class FileScanEntry(BaseModel):
    file_name: str
    status: str  # "clean" | "threat" | "pending"
    scanned_at: str
    sha256: str = ""
    threats: List[str] = []


class FileScanResponse(BaseModel):
    scans: List[FileScanEntry]


class AccessLogEntry(BaseModel):
    user: str
    action: str
    timestamp: str
    ip: str


class AccessLogResponse(BaseModel):
    entries: List[AccessLogEntry]


class EncryptionStatusResponse(BaseModel):
    status: str
    encrypted_count: int
    total_count: int
    last_rotated: str


# ---- Scan Log Helpers ----------------------------------------------------

def _scan_log_path(case_id: str) -> Path:
    return DATA_DIR / "cases" / case_id / "scan_log.json"


def load_scan_log(case_id: str) -> list[dict]:
    p = _scan_log_path(case_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_scan_entry(case_id: str, entry: dict):
    """Append a scan result to the case's scan log."""
    p = _scan_log_path(case_id)
    entries = load_scan_log(case_id)
    entries.append(entry)
    # Keep last 5000 entries
    entries = entries[-5000:]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, default=str), encoding="utf-8")


# ---- Endpoints -----------------------------------------------------------

@router.get("/scans", response_model=FileScanResponse)
def get_file_scans(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Return file scan results for a case."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")

    raw = load_scan_log(case_id)

    # Deduplicate: keep latest scan per file_name
    latest: dict[str, dict] = {}
    for entry in raw:
        fname = entry.get("file_name", "")
        latest[fname] = entry

    scans = []
    for entry in latest.values():
        scans.append(FileScanEntry(
            file_name=entry.get("file_name", ""),
            status=entry.get("status", "clean"),
            scanned_at=entry.get("scanned_at", ""),
            sha256=entry.get("sha256", ""),
            threats=entry.get("threats", []),
        ))

    return FileScanResponse(scans=scans)


@router.get("/access-log", response_model=AccessLogResponse)
def get_access_log(
    case_id: str,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Return access log entries for a case from the audit trail."""
    storage = get_storage_backend()
    activity = storage.load_preparation_data(case_id, "activity") or []

    entries = []
    for record in activity[:limit]:
        entries.append(AccessLogEntry(
            user=record.get("user_id", "unknown"),
            action=record.get("action", record.get("method", "")),
            timestamp=record.get("timestamp", ""),
            ip=record.get("ip", ""),
        ))

    return AccessLogResponse(entries=entries)


@router.get("/encryption", response_model=EncryptionStatusResponse)
def get_encryption_status(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Return encryption status for case files."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")

    file_paths = cm.get_case_files(case_id)
    total = len(file_paths)

    # Check if storage backend supports encryption
    backend = get_storage_backend()
    is_encrypted_backend = hasattr(backend, "is_encrypted") and backend.is_encrypted

    encrypted_count = total if is_encrypted_backend else 0
    status = "active" if is_encrypted_backend else "inactive"

    # Check for key rotation timestamp
    last_rotated = ""
    if hasattr(backend, "last_key_rotation"):
        last_rotated = backend.last_key_rotation or ""

    return EncryptionStatusResponse(
        status=status,
        encrypted_count=encrypted_count,
        total_count=total,
        last_rotated=last_rotated,
    )
