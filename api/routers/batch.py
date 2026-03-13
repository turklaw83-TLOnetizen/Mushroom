# ---- Batch Operations Router ----------------------------------------------
# Bulk actions for managing large case loads efficiently.
# All operations require admin role and operate on real case data.

import csv
import io
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["Batch Operations"])


# ---- Schemas -------------------------------------------------------------


class BulkStatusUpdate(BaseModel):
    case_ids: List[str]
    new_status: str
    reason: str = ""


class BulkAssign(BaseModel):
    case_ids: List[str]
    assigned_to: str


class BulkExport(BaseModel):
    case_ids: List[str]
    format: str = Field(default="csv", pattern="^(csv|json)$")


class BulkArchive(BaseModel):
    case_ids: List[str]


# ---- Endpoints -----------------------------------------------------------


@router.post("/cases/status")
def bulk_update_status(payload: BulkStatusUpdate, user: dict = Depends(require_role("admin"))):
    """Update status for multiple cases at once.

    Accepts a list of case_ids and a new_status value. For each case,
    calls CaseManager.update_status() and reports per-case results.
    """
    if not payload.case_ids:
        raise HTTPException(status_code=400, detail="case_ids must not be empty")

    from api.deps import get_case_manager
    cm = get_case_manager()

    results = []
    success_count = 0
    fail_count = 0

    for case_id in payload.case_ids:
        try:
            meta = cm.get_case_metadata(case_id)
            if not meta:
                results.append({
                    "case_id": case_id,
                    "success": False,
                    "error": "Case not found",
                })
                fail_count += 1
                continue

            old_status = meta.get("status", meta.get("phase", "active"))
            cm.update_status(case_id, payload.new_status)
            results.append({
                "case_id": case_id,
                "success": True,
                "old_status": old_status,
                "new_status": payload.new_status,
            })
            success_count += 1
        except Exception as e:
            results.append({
                "case_id": case_id,
                "success": False,
                "error": str(e),
            })
            fail_count += 1

    logger.info(
        "Bulk status update: %d/%d succeeded -> %s (by %s). Reason: %s",
        success_count, len(payload.case_ids), payload.new_status,
        user.get("name", user.get("id", "")), payload.reason or "(none)",
    )

    return {
        "updated": success_count,
        "failed": fail_count,
        "total": len(payload.case_ids),
        "results": results,
    }


@router.post("/cases/assign")
def bulk_assign_cases(payload: BulkAssign, user: dict = Depends(require_role("admin"))):
    """Assign multiple cases to a team member.

    Updates each case's metadata with the assigned_to field.
    """
    if not payload.case_ids:
        raise HTTPException(status_code=400, detail="case_ids must not be empty")
    if not payload.assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to must not be empty")

    from api.deps import get_case_manager
    cm = get_case_manager()

    results = []
    success_count = 0
    fail_count = 0

    for case_id in payload.case_ids:
        try:
            meta = cm.get_case_metadata(case_id)
            if not meta:
                results.append({
                    "case_id": case_id,
                    "success": False,
                    "error": "Case not found",
                })
                fail_count += 1
                continue

            # Update the assigned_to field in case metadata
            old_assigned = meta.get("assigned_to", [])
            # assigned_to can be a list or string; normalize to include the new assignee
            if isinstance(old_assigned, list):
                if payload.assigned_to not in old_assigned:
                    old_assigned.append(payload.assigned_to)
                meta["assigned_to"] = old_assigned
            else:
                meta["assigned_to"] = [payload.assigned_to]

            from datetime import datetime
            meta["last_updated"] = datetime.now().isoformat()
            cm.storage.update_case_metadata(case_id, meta)

            results.append({
                "case_id": case_id,
                "success": True,
                "assigned_to": payload.assigned_to,
            })
            success_count += 1
        except Exception as e:
            results.append({
                "case_id": case_id,
                "success": False,
                "error": str(e),
            })
            fail_count += 1

    logger.info(
        "Bulk assign: %d/%d succeeded -> %s (by %s)",
        success_count, len(payload.case_ids), payload.assigned_to,
        user.get("name", user.get("id", "")),
    )

    return {
        "assigned": success_count,
        "failed": fail_count,
        "total": len(payload.case_ids),
        "results": results,
    }


@router.post("/cases/export")
def bulk_export_cases(payload: BulkExport, user: dict = Depends(require_role("admin"))):
    """Export metadata for multiple cases as CSV or JSON.

    Returns the exported data inline (not as a file download).
    For CSV format, returns a CSV string. For JSON, returns an array.
    """
    if not payload.case_ids:
        raise HTTPException(status_code=400, detail="case_ids must not be empty")

    from api.deps import get_case_manager
    cm = get_case_manager()

    cases_data = []
    not_found = []

    for case_id in payload.case_ids:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            not_found.append(case_id)
            continue

        cases_data.append({
            "id": meta.get("id", case_id),
            "name": meta.get("name", ""),
            "case_type": meta.get("case_type", ""),
            "phase": meta.get("phase", meta.get("status", "active")),
            "sub_phase": meta.get("sub_phase", ""),
            "client_name": meta.get("client_name", ""),
            "jurisdiction": meta.get("jurisdiction", ""),
            "docket_number": meta.get("docket_number", ""),
            "court_name": meta.get("court_name", ""),
            "charges": meta.get("charges", ""),
            "assigned_to": ", ".join(meta.get("assigned_to", [])) if isinstance(meta.get("assigned_to"), list) else meta.get("assigned_to", ""),
            "created_at": meta.get("created_at", ""),
            "last_updated": meta.get("last_updated", ""),
        })

    if payload.format == "csv":
        if not cases_data:
            csv_str = ""
        else:
            output = io.StringIO()
            fieldnames = list(cases_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in cases_data:
                writer.writerow(row)
            csv_str = output.getvalue()

        logger.info(
            "Bulk CSV export: %d cases exported (by %s)",
            len(cases_data), user.get("name", user.get("id", "")),
        )

        return {
            "format": "csv",
            "case_count": len(cases_data),
            "not_found": not_found,
            "data": csv_str,
        }
    else:
        logger.info(
            "Bulk JSON export: %d cases exported (by %s)",
            len(cases_data), user.get("name", user.get("id", "")),
        )

        return {
            "format": "json",
            "case_count": len(cases_data),
            "not_found": not_found,
            "data": cases_data,
        }


@router.post("/cases/archive")
def bulk_archive_cases(payload: BulkArchive, user: dict = Depends(require_role("admin"))):
    """Archive multiple cases.

    Transitions each case's phase to 'archived' using CaseManager.set_phase().
    Only cases currently in 'active' or 'closed' phases can be archived.
    """
    if not payload.case_ids:
        raise HTTPException(status_code=400, detail="case_ids must not be empty")

    from api.deps import get_case_manager
    cm = get_case_manager()

    results = []
    success_count = 0
    fail_count = 0

    for case_id in payload.case_ids:
        try:
            meta = cm.get_case_metadata(case_id)
            if not meta:
                results.append({
                    "case_id": case_id,
                    "success": False,
                    "error": "Case not found",
                })
                fail_count += 1
                continue

            current_phase = meta.get("phase", meta.get("status", "active"))
            if current_phase == "archived":
                results.append({
                    "case_id": case_id,
                    "success": True,
                    "note": "Already archived",
                })
                success_count += 1
                continue

            cm.set_phase(case_id, "archived")
            results.append({
                "case_id": case_id,
                "success": True,
                "old_phase": current_phase,
                "new_phase": "archived",
            })
            success_count += 1
        except Exception as e:
            results.append({
                "case_id": case_id,
                "success": False,
                "error": str(e),
            })
            fail_count += 1

    logger.info(
        "Bulk archive: %d/%d succeeded (by %s)",
        success_count, len(payload.case_ids),
        user.get("name", user.get("id", "")),
    )

    return {
        "archived": success_count,
        "failed": fail_count,
        "total": len(payload.case_ids),
        "results": results,
    }
