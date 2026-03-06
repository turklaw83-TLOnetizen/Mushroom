# ---- Ethical Compliance Router --------------------------------------------
# Full RPC-grounded ethical compliance: conflict scans, prospective clients,
# trust ledger, fee agreements, SOL tracking, supervision, and dashboard.
# Wraps the 11 tools from core/ethical_compliance.py.

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance", tags=["Ethical Compliance"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ProspectiveClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    subject: str = ""
    disclosed_info: str = ""
    date: str = ""
    notes: str = ""
    declined_reason: str = ""


class ProspectiveClientUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    disclosed_info: Optional[str] = None
    date: Optional[str] = None
    notes: Optional[str] = None
    declined_reason: Optional[str] = None


class TrustEntryCreate(BaseModel):
    entry_type: str = Field(..., pattern="^(deposit|disbursement)$")
    amount: float = Field(..., gt=0)
    description: str = ""
    date: str = ""
    reference: str = ""
    client_notified: bool = False


class FeeAgreementSave(BaseModel):
    fee_type: str = Field(..., min_length=1)
    rate: str = ""
    retainer: str = ""
    signed: bool = False
    signed_date: str = ""
    notes: str = ""
    contingent_pct: str = ""
    closing_statement: bool = False


class SOLClaimCreate(BaseModel):
    claim_type: str = Field(..., min_length=1)
    incident_date: str = Field(..., min_length=1)
    discovery_date: str = ""
    tolling_notes: str = ""
    description: str = ""


class SupervisionEntryCreate(BaseModel):
    task: str = Field(..., min_length=1)
    assignee: str = Field(..., min_length=1)
    supervisor: str = Field(..., min_length=1)
    assignee_type: str = "Attorney"
    due_date: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# 1. Compliance Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def compliance_dashboard(
    user: dict = Depends(get_current_user),
):
    """Aggregate compliance metrics across all cases."""
    try:
        from core.ethical_compliance import get_compliance_dashboard
        cm = get_case_manager()
        result = get_compliance_dashboard(cm)
        return result
    except Exception:
        logger.exception("Failed to load compliance dashboard")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. Smart Conflict Scan
# ---------------------------------------------------------------------------

@router.post("/conflicts/{case_id}/scan")
def scan_conflicts(
    case_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run smart conflict scan for a case against all other cases + prospective clients."""
    try:
        from core.ethical_compliance import scan_conflicts_smart, load_prospective_clients

        cm = get_case_manager()

        # Verify case exists
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        # Collect entities across all cases
        all_entities: Dict[str, list] = {}
        cases = cm.list_cases() or []
        for case in cases:
            cid = case.get("id", "")
            if not cid:
                continue
            preps = cm.list_preparations(cid) or []
            case_entities = []
            for prep in preps:
                try:
                    state = cm.load_prep_state(cid, prep.get("id", ""))
                    if state:
                        entities = state.get("entities", [])
                        for ent in entities:
                            name = ent.get("name", "")
                            if name:
                                case_entities.append({
                                    "name": name,
                                    "role": ent.get("type", ent.get("role", "unknown")),
                                    "source": ent.get("source", "entity_extraction"),
                                    "case_id": cid,
                                    "case_name": case.get("name", cid),
                                })
                except Exception:
                    logger.debug("Failed to load prep state for case=%s prep=%s",
                                 cid, prep.get("id", ""))
                    continue
            if case_entities:
                all_entities[cid] = case_entities

        # Load prospective clients
        prospective = load_prospective_clients()

        # Run the scan
        result = scan_conflicts_smart(case_id, all_entities, prospective)
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Conflict scan failed for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 3–6. Prospective Client CRUD
# ---------------------------------------------------------------------------

@router.get("/prospective-clients")
def list_prospective_clients(
    user: dict = Depends(get_current_user),
):
    """List all prospective client records."""
    try:
        from core.ethical_compliance import load_prospective_clients
        return {"clients": load_prospective_clients()}
    except Exception:
        logger.exception("Failed to list prospective clients")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/prospective-clients")
def add_prospective_client(
    body: ProspectiveClientCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a new prospective client record."""
    try:
        from core.ethical_compliance import save_prospective_client
        client_id = save_prospective_client(
            name=body.name,
            subject=body.subject,
            disclosed_info=body.disclosed_info,
            consultation_date=body.date,
            notes=body.notes,
            declined_reason=body.declined_reason,
        )
        return {"success": True, "client_id": client_id}
    except Exception:
        logger.exception("Failed to add prospective client")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/prospective-clients/{client_id}")
def update_prospective_client_endpoint(
    client_id: str,
    body: ProspectiveClientUpdate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a prospective client record."""
    try:
        from core.ethical_compliance import update_prospective_client
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        update_prospective_client(client_id, updates)
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update prospective client %s", client_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/prospective-clients/{client_id}")
def delete_prospective_client_endpoint(
    client_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a prospective client record."""
    try:
        from core.ethical_compliance import delete_prospective_client
        delete_prospective_client(client_id)
        return {"success": True}
    except Exception:
        logger.exception("Failed to delete prospective client %s", client_id)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 7–8. Trust Ledger
# ---------------------------------------------------------------------------

@router.get("/trust/{case_id}")
def get_trust_ledger(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get trust account ledger entries + balance for a case."""
    try:
        from core.ethical_compliance import load_trust_ledger, get_trust_balance
        entries = load_trust_ledger(case_id)
        balance = get_trust_balance(case_id)
        return {"entries": entries, "balance": balance, "case_id": case_id}
    except Exception:
        logger.exception("Failed to load trust ledger for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trust/{case_id}")
def add_trust_entry_endpoint(
    case_id: str,
    body: TrustEntryCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a trust account entry (deposit or disbursement)."""
    try:
        from core.ethical_compliance import add_trust_entry, get_trust_balance

        # Verify case exists
        cm = get_case_manager()
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        entry_id = add_trust_entry(
            case_id=case_id,
            entry_type=body.entry_type,
            amount=body.amount,
            description=body.description,
            date_str=body.date,
            reference=body.reference,
            client_notified=body.client_notified,
        )
        balance = get_trust_balance(case_id)
        return {"success": True, "entry_id": entry_id, "balance": balance}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to add trust entry for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 9–10. Fee Agreements
# ---------------------------------------------------------------------------

@router.get("/fee-agreements/{case_id}")
def get_fee_agreement(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get fee agreement data for a case."""
    try:
        from core.ethical_compliance import load_fee_agreement, get_fee_agreement_status
        agreement = load_fee_agreement(case_id)
        status = get_fee_agreement_status(case_id)
        return {
            "agreement": agreement,
            "status": status,
            "case_id": case_id,
        }
    except Exception:
        logger.exception("Failed to load fee agreement for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/fee-agreements/{case_id}")
def save_fee_agreement_endpoint(
    case_id: str,
    body: FeeAgreementSave,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save or update fee agreement for a case."""
    try:
        from core.ethical_compliance import save_fee_agreement

        # Verify case exists
        cm = get_case_manager()
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        agreement = save_fee_agreement(
            case_id=case_id,
            fee_type=body.fee_type,
            rate=body.rate,
            retainer=body.retainer,
            signed=body.signed,
            signed_date=body.signed_date,
            notes=body.notes,
            contingent_pct=body.contingent_pct,
            closing_statement=body.closing_statement,
        )
        return {"success": True, "agreement": agreement}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save fee agreement for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 11–13. SOL (Statute of Limitations) Tracking
# ---------------------------------------------------------------------------

@router.get("/sol/{case_id}")
def get_sol_tracking(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get SOL claims and deadlines for a case.

    Recalculates days_remaining and urgency dynamically so values
    are always fresh rather than stale from creation time.
    """
    try:
        from core.ethical_compliance import (
            load_sol_tracking,
            calculate_sol_deadline,
            compute_sol_urgency,
        )
        data = load_sol_tracking(case_id)
        # Recalculate days_remaining for each claim so it's always current
        for claim in data.get("claims", []):
            calc = calculate_sol_deadline(
                claim.get("claim_type", ""),
                claim.get("incident_date", ""),
                claim.get("discovery_date", ""),
            )
            if "error" not in calc:
                claim["days_remaining"] = calc.get("days_remaining")
                claim["deadline"] = calc.get("deadline", claim.get("deadline", ""))
                claim["urgency"] = calc.get("urgency", claim.get("urgency", ""))
                dr = calc.get("days_remaining")
                claim["urgency_level"] = compute_sol_urgency(dr) if dr is not None else "ok"
            else:
                claim["urgency_level"] = "ok"
        return {"case_id": case_id, **data}
    except Exception:
        logger.exception("Failed to load SOL tracking for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sol/{case_id}/claims")
def add_sol_claim_endpoint(
    case_id: str,
    body: SOLClaimCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a SOL claim to track for a case."""
    try:
        from core.ethical_compliance import add_sol_claim

        # Verify case exists
        cm = get_case_manager()
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        claim_id = add_sol_claim(
            case_id=case_id,
            claim_type=body.claim_type,
            incident_date=body.incident_date,
            discovery_date=body.discovery_date,
            tolling_notes=body.tolling_notes,
            description=body.description,
        )
        return {"success": True, "claim_id": claim_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to add SOL claim for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/sol/{case_id}/claims/{claim_id}")
def delete_sol_claim_endpoint(
    case_id: str,
    claim_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a SOL claim from tracking."""
    try:
        from core.ethical_compliance import delete_sol_claim
        delete_sol_claim(case_id, claim_id)
        return {"success": True}
    except Exception:
        logger.exception("Failed to delete SOL claim %s for case %s", claim_id, case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sol/alerts")
def get_sol_alerts(
    user: dict = Depends(get_current_user),
):
    """Get SOL alerts across all cases."""
    try:
        from core.ethical_compliance import get_sol_alerts
        cm = get_case_manager()
        return get_sol_alerts(cm)
    except ImportError:
        return []
    except Exception:
        logger.exception("Failed to load SOL alerts")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 14–15. Supervision Tracker
# ---------------------------------------------------------------------------

@router.get("/supervision/{case_id}")
def get_supervision_log(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get supervision/delegation log for a case."""
    try:
        from core.ethical_compliance import load_supervision_log
        entries = load_supervision_log(case_id)
        return {"entries": entries, "case_id": case_id}
    except Exception:
        logger.exception("Failed to load supervision log for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/supervision/{case_id}")
def add_supervision_entry_endpoint(
    case_id: str,
    body: SupervisionEntryCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Add a supervision/delegation entry."""
    try:
        from core.ethical_compliance import add_supervision_entry

        # Verify case exists
        cm = get_case_manager()
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")

        entry_id = add_supervision_entry(
            case_id=case_id,
            task=body.task,
            assignee=body.assignee,
            supervisor=body.supervisor,
            assignee_type=body.assignee_type,
            due_date=body.due_date,
            notes=body.notes,
        )
        return {"success": True, "entry_id": entry_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to add supervision entry for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")
