# ---- Snapshots Router ----------------------------------------------------
# Version history: save, list, compare, and restore prep state snapshots.

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/snapshots",
    tags=["Snapshots"],
)


# ---- Schemas -------------------------------------------------------------

class SnapshotMeta(BaseModel):
    id: str = ""
    label: str = ""
    created_at: str = ""
    node_count: int = 0

    model_config = {"extra": "allow"}


class CreateSnapshotRequest(BaseModel):
    label: str = Field(default="Manual snapshot", max_length=256)


# ---- Endpoints -----------------------------------------------------------

@router.get("", response_model=List[SnapshotMeta])
def list_snapshots(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """List all snapshots for a preparation."""
    cm = get_case_manager()
    snapshots = cm.list_snapshots(case_id, prep_id)
    return snapshots


@router.post("")
def create_snapshot(
    case_id: str,
    prep_id: str,
    body: CreateSnapshotRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a manual snapshot of the current prep state."""
    cm = get_case_manager()
    snapshot_id = cm.save_snapshot(case_id, prep_id, body.label)
    return {"snapshot_id": snapshot_id, "status": "created"}


@router.get("/{snapshot_id}")
def get_snapshot(
    case_id: str,
    prep_id: str,
    snapshot_id: str,
    user: dict = Depends(get_current_user),
):
    """Get full snapshot state for comparison."""
    cm = get_case_manager()
    snapshots = cm.list_snapshots(case_id, prep_id)
    meta = next((s for s in snapshots if s.get("id") == snapshot_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Load the snapshot data
    state = cm.storage.load_snapshot(case_id, prep_id, snapshot_id)
    return {"meta": meta, "state": state}


@router.post("/{snapshot_id}/restore")
def restore_snapshot(
    case_id: str,
    prep_id: str,
    snapshot_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Restore a snapshot (saves current state as a snapshot first)."""
    cm = get_case_manager()
    # Save current state before restoring
    cm.save_snapshot(case_id, prep_id, f"Before restore to {snapshot_id}")
    restored = cm.restore_snapshot(case_id, prep_id, snapshot_id)
    if not restored:
        raise HTTPException(status_code=404, detail="Snapshot not found or empty")
    return {"status": "restored", "snapshot_id": snapshot_id}


@router.delete("/{snapshot_id}")
def delete_snapshot(
    case_id: str,
    prep_id: str,
    snapshot_id: str,
    user: dict = Depends(require_role("admin")),
):
    """Delete a snapshot."""
    cm = get_case_manager()
    try:
        cm.storage.delete_snapshot(case_id, prep_id, snapshot_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
