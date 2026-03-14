# ---- Discovery Command Center Router ----------------------------------------
# Civil-only discovery tracking, AI drafting, productions, and privilege log.

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases/{case_id}/discovery", tags=["Discovery"])
dashboard_router = APIRouter(prefix="/discovery", tags=["Discovery Dashboard"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class DiscoveryRequestCreate(BaseModel):
    direction: str = "outbound"
    request_type: str = "interrogatories"
    title: str = ""
    served_on: str = ""
    served_by: str = ""
    date_served: str = ""
    items: Optional[List[Dict]] = None
    notes: str = ""
    response_days: int = 0


class DiscoveryRequestUpdate(BaseModel):
    title: Optional[str] = None
    served_on: Optional[str] = None
    served_by: Optional[str] = None
    date_served: Optional[str] = None
    response_due: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[List[Dict]] = None


class StatusUpdate(BaseModel):
    status: str


class ItemResponseUpdate(BaseModel):
    response: Optional[str] = None
    objection: Optional[str] = None
    status: Optional[str] = None


class ProductionSetCreate(BaseModel):
    title: str
    bates_prefix: str = "DEF"
    documents: Optional[List[Dict]] = None
    produced_to: str = ""
    date_produced: str = ""


class ProductionSetUpdate(BaseModel):
    title: Optional[str] = None
    produced_to: Optional[str] = None
    date_produced: Optional[str] = None
    status: Optional[str] = None


class PrivilegeEntryCreate(BaseModel):
    document: str = ""
    bates_number: str = ""
    privilege_type: str = "attorney-client"
    description: str = ""
    entry_date: str = ""
    from_party: str = ""
    to_party: str = ""
    subject: str = ""
    basis: str = ""


class DraftRequest(BaseModel):
    request_type: str = "interrogatories"
    focus_witnesses: Optional[List[str]] = None
    focus_themes: Optional[List[str]] = None
    focus_evidence_gaps: Optional[List[str]] = None
    date_range: str = ""
    custom_instructions: str = ""
    num_items: int = 25


class MeetConferRequest(BaseModel):
    request_id: str
    deficient_item_numbers: List[int]
    custom_instructions: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_civil(case_id: str) -> dict:
    """Raise 400 if the case is not a civil case. Returns case metadata."""
    from core.discovery import is_civil_case
    case_mgr = get_case_manager()
    meta = case_mgr.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")
    case_type = meta.get("case_type", "")
    if not is_civil_case(case_type):
        raise HTTPException(
            status_code=400,
            detail=f"Discovery Command Center is only available for civil cases. This case is '{case_type}'.",
        )
    return meta


# ---------------------------------------------------------------------------
# Discovery Requests — CRUD
# ---------------------------------------------------------------------------

@router.get("")
def get_discovery(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all discovery data + summary for a case."""
    try:
        from core.discovery import load_discovery, get_discovery_summary, is_civil_case
        case_mgr = get_case_manager()
        meta = case_mgr.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        case_type = meta.get("case_type", "")
        if not is_civil_case(case_type):
            return {
                "civil": False,
                "case_type": case_type,
                "requests": [],
                "production_sets": [],
                "privilege_log": [],
                "summary": {},
            }

        data_dir = get_data_dir()
        data = load_discovery(data_dir, case_id)
        summary = get_discovery_summary(data_dir, case_id)
        return {
            "civil": True,
            "case_type": case_type,
            **data,
            "summary": summary,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get discovery for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/requests")
def create_request(
    case_id: str,
    body: DiscoveryRequestCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new discovery request."""
    _assert_civil(case_id)
    try:
        from core.discovery import add_request
        data_dir = get_data_dir()
        rid = add_request(
            data_dir,
            case_id,
            direction=body.direction,
            request_type=body.request_type,
            title=body.title,
            served_on=body.served_on,
            served_by=body.served_by,
            date_served=body.date_served,
            items=body.items,
            notes=body.notes,
            response_days=body.response_days,
        )
        return {"success": True, "request_id": rid}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create discovery request")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/requests/{request_id}")
def get_request(
    case_id: str,
    request_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single discovery request."""
    _assert_civil(case_id)
    try:
        from core.discovery import get_request as _get_request
        data_dir = get_data_dir()
        req = _get_request(data_dir, case_id, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        return req
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get discovery request")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/requests/{request_id}")
def update_request_endpoint(
    case_id: str,
    request_id: str,
    body: DiscoveryRequestUpdate,
    user: dict = Depends(get_current_user),
):
    """Update a discovery request."""
    _assert_civil(case_id)
    try:
        from core.discovery import update_request
        data_dir = get_data_dir()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not update_request(data_dir, case_id, request_id, updates):
            raise HTTPException(status_code=404, detail="Request not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update discovery request")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/requests/{request_id}")
def delete_request_endpoint(
    case_id: str,
    request_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a discovery request."""
    _assert_civil(case_id)
    try:
        from core.discovery import delete_request
        data_dir = get_data_dir()
        if not delete_request(data_dir, case_id, request_id):
            raise HTTPException(status_code=404, detail="Request not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete discovery request")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/requests/{request_id}/status")
def update_status(
    case_id: str,
    request_id: str,
    body: StatusUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the status of a discovery request."""
    _assert_civil(case_id)
    try:
        from core.discovery import update_request_status
        data_dir = get_data_dir()
        if not update_request_status(data_dir, case_id, request_id, body.status):
            raise HTTPException(status_code=404, detail="Request not found")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update request status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/requests/{request_id}/items/{item_number}")
def update_item(
    case_id: str,
    request_id: str,
    item_number: int,
    body: ItemResponseUpdate,
    user: dict = Depends(get_current_user),
):
    """Update an individual item's response/objection/status."""
    _assert_civil(case_id)
    try:
        from core.discovery import update_item_response
        data_dir = get_data_dir()
        if not update_item_response(
            data_dir,
            case_id,
            request_id,
            item_number,
            response=body.response,
            objection=body.objection,
            status=body.status,
        ):
            raise HTTPException(status_code=404, detail="Request or item not found")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update item response")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# AI Drafting
# ---------------------------------------------------------------------------

@router.post("/draft")
def draft_discovery(
    case_id: str,
    body: DraftRequest,
    user: dict = Depends(get_current_user),
):
    """AI-draft discovery requests (interrogatories, RFP, or RFA)."""
    _assert_civil(case_id)
    try:
        from core.discovery_drafter import (
            draft_interrogatories,
            draft_requests_for_production,
            draft_requests_for_admission,
        )
        case_mgr = get_case_manager()
        data_dir = get_data_dir()

        targeting = {
            "focus_witnesses": body.focus_witnesses or [],
            "focus_themes": body.focus_themes or [],
            "focus_evidence_gaps": body.focus_evidence_gaps or [],
            "date_range": body.date_range,
        }

        if body.request_type == "interrogatories":
            items = draft_interrogatories(
                case_mgr, data_dir, case_id,
                targeting=targeting,
                custom_instructions=body.custom_instructions,
                num_items=body.num_items,
            )
        elif body.request_type == "rfp":
            items = draft_requests_for_production(
                case_mgr, data_dir, case_id,
                targeting=targeting,
                custom_instructions=body.custom_instructions,
                num_items=body.num_items,
            )
        elif body.request_type == "rfa":
            items = draft_requests_for_admission(
                case_mgr, data_dir, case_id,
                targeting=targeting,
                custom_instructions=body.custom_instructions,
                num_items=body.num_items,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid request_type: {body.request_type}")

        return {
            "success": True,
            "request_type": body.request_type,
            "items": items,
            "count": len(items),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to draft discovery")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/meet-confer")
def meet_confer(
    case_id: str,
    body: MeetConferRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a meet-and-confer letter for deficient discovery responses."""
    _assert_civil(case_id)
    try:
        from core.discovery import get_request as _get_request
        from core.discovery_drafter import generate_meet_confer_letter
        case_mgr = get_case_manager()
        data_dir = get_data_dir()

        request_data = _get_request(data_dir, case_id, body.request_id)
        if not request_data:
            raise HTTPException(status_code=404, detail="Request not found")

        letter = generate_meet_confer_letter(
            case_mgr, data_dir, case_id,
            request_data=request_data,
            deficient_item_numbers=body.deficient_item_numbers,
            custom_instructions=body.custom_instructions,
        )
        return {"success": True, "letter": letter}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate meet-and-confer letter")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Production Sets
# ---------------------------------------------------------------------------

@router.get("/productions")
def list_productions(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all production sets for a case."""
    _assert_civil(case_id)
    try:
        from core.discovery import get_production_sets
        data_dir = get_data_dir()
        return {"production_sets": get_production_sets(data_dir, case_id)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list production sets")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/productions")
def create_production(
    case_id: str,
    body: ProductionSetCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new production set with Bates numbering."""
    _assert_civil(case_id)
    try:
        from core.discovery import add_production_set
        data_dir = get_data_dir()
        sid = add_production_set(
            data_dir, case_id,
            title=body.title,
            bates_prefix=body.bates_prefix,
            documents=body.documents,
            produced_to=body.produced_to,
            date_produced=body.date_produced,
        )
        return {"success": True, "set_id": sid}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create production set")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/productions/{set_id}")
def update_production(
    case_id: str,
    set_id: str,
    body: ProductionSetUpdate,
    user: dict = Depends(get_current_user),
):
    """Update a production set."""
    _assert_civil(case_id)
    try:
        from core.discovery import update_production_set
        data_dir = get_data_dir()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not update_production_set(data_dir, case_id, set_id, updates):
            raise HTTPException(status_code=404, detail="Production set not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update production set")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Privilege Log
# ---------------------------------------------------------------------------

@router.get("/privilege")
def list_privilege(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the privilege log for a case."""
    _assert_civil(case_id)
    try:
        from core.discovery import get_privilege_log
        data_dir = get_data_dir()
        return {"privilege_log": get_privilege_log(data_dir, case_id)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get privilege log")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/privilege")
def create_privilege_entry(
    case_id: str,
    body: PrivilegeEntryCreate,
    user: dict = Depends(get_current_user),
):
    """Add a privilege log entry."""
    _assert_civil(case_id)
    try:
        from core.discovery import add_privilege_entry
        data_dir = get_data_dir()
        eid = add_privilege_entry(
            data_dir, case_id,
            document=body.document,
            bates_number=body.bates_number,
            privilege_type=body.privilege_type,
            description=body.description,
            entry_date=body.entry_date,
            from_party=body.from_party,
            to_party=body.to_party,
            subject=body.subject,
            basis=body.basis,
        )
        return {"success": True, "entry_id": eid}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to add privilege entry")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/privilege/{entry_id}")
def delete_privilege(
    case_id: str,
    entry_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a privilege log entry."""
    _assert_civil(case_id)
    try:
        from core.discovery import delete_privilege_entry
        data_dir = get_data_dir()
        if not delete_privilege_entry(data_dir, case_id, entry_id):
            raise HTTPException(status_code=404, detail="Privilege entry not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete privilege entry")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Cross-Case Dashboard
# ---------------------------------------------------------------------------

@dashboard_router.get("/dashboard")
def discovery_dashboard(
    user: dict = Depends(get_current_user),
):
    """Cross-case discovery dashboard — aggregates all civil cases."""
    try:
        from core.discovery import get_cross_case_discovery
        case_mgr = get_case_manager()
        data_dir = get_data_dir()
        items = get_cross_case_discovery(data_dir, case_mgr)

        # Compute summary stats
        total = len(items)
        overdue = sum(1 for i in items if i.get("is_overdue"))
        pending = sum(1 for i in items if i.get("status") in ("served", "response_pending"))
        upcoming_7 = sum(
            1 for i in items
            if i.get("days_until_due") is not None and 0 <= i["days_until_due"] <= 7
        )

        return {
            "items": items,
            "stats": {
                "total_requests": total,
                "overdue": overdue,
                "pending_response": pending,
                "due_within_7_days": upcoming_7,
            },
        }
    except Exception:
        logger.exception("Failed to get discovery dashboard")
        raise HTTPException(status_code=500, detail="Internal server error")
