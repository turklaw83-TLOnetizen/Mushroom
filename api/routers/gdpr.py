# ---- GDPR Data Export & Erasure Endpoints --------------------------------
# GDPR Articles 17, 20 — Right to Erasure and Right to Data Portability.
# Provides data export, erasure requests, consent tracking, and audit logging.

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gdpr", tags=["GDPR / Privacy"])

# ---- Audit Log Storage ---------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_GDPR_DIR = os.path.join(_SCRIPT_DIR, os.pardir, os.pardir, "data", "gdpr")
_AUDIT_LOG_FILE = os.path.join(_GDPR_DIR, "audit_log.json")
_ERASURE_REQUESTS_FILE = os.path.join(_GDPR_DIR, "erasure_requests.json")


def _ensure_dir():
    os.makedirs(_GDPR_DIR, exist_ok=True)


def _load_audit_log() -> List[Dict]:
    """Load the GDPR audit log."""
    _ensure_dir()
    if os.path.exists(_AUDIT_LOG_FILE):
        try:
            with open(_AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_audit_log(log: List[Dict]):
    """Persist the GDPR audit log."""
    _ensure_dir()
    with open(_AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _append_audit_entry(
    action: str,
    client_id: str,
    performed_by: str,
    details: str = "",
):
    """Append an entry to the GDPR audit log."""
    log = _load_audit_log()
    log.append({
        "id": f"gdpr_{uuid.uuid4().hex[:8]}",
        "action": action,
        "client_id": client_id,
        "performed_by": performed_by,
        "details": details,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    _save_audit_log(log)


def _load_erasure_requests() -> List[Dict]:
    """Load pending/completed erasure requests."""
    _ensure_dir()
    if os.path.exists(_ERASURE_REQUESTS_FILE):
        try:
            with open(_ERASURE_REQUESTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_erasure_requests(requests: List[Dict]):
    """Persist erasure requests."""
    _ensure_dir()
    with open(_ERASURE_REQUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2, ensure_ascii=False)


# ---- Endpoints -----------------------------------------------------------


@router.get("/export/{client_id}")
def export_client_data(client_id: str, user: dict = Depends(require_role("admin"))):
    """
    Export all data associated with a client in JSON format.
    GDPR Article 20 -- Right to Data Portability.

    Collects: personal data, linked cases (metadata only), billing records,
    communications, calendar events, and consent records.
    """
    from core.crm import get_client, get_cases_for_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # --- Personal data ---
    personal_data = {
        "client_id": client.get("id", ""),
        "name": client.get("name", ""),
        "first_name": client.get("first_name", ""),
        "last_name": client.get("last_name", ""),
        "email": client.get("email", ""),
        "phone": client.get("phone", ""),
        "mailing_address": client.get("mailing_address", ""),
        "home_address": client.get("home_address", ""),
        "date_of_birth": client.get("date_of_birth", ""),
        "employer": client.get("employer", ""),
        "referral_source": client.get("referral_source", ""),
        "intake_status": client.get("intake_status", ""),
        "intake_date": client.get("intake_date", ""),
        "tags": client.get("tags", []),
        "notes": client.get("notes", ""),
        "created_at": client.get("created_at", ""),
    }

    # --- Linked cases (metadata only, no analysis) ---
    from api.deps import get_case_manager
    cm = get_case_manager()
    case_ids = get_cases_for_client(client_id)
    cases = []
    for cid in case_ids:
        meta = cm.get_case_metadata(cid)
        if meta:
            cases.append({
                "id": cid,
                "name": meta.get("name", cid),
                "case_type": meta.get("case_type", ""),
                "phase": meta.get("phase", meta.get("status", "active")),
                "sub_phase": meta.get("sub_phase", ""),
                "created_at": meta.get("created_at", ""),
                "last_updated": meta.get("last_updated", ""),
                "jurisdiction": meta.get("jurisdiction", ""),
                "docket_number": meta.get("docket_number", ""),
            })

    # --- Billing records ---
    billing_records = []
    try:
        from core.billing import load_invoices, load_payment_plans
        # Invoices linked to this client's cases
        all_invoices = load_invoices()
        client_case_set = set(case_ids)
        for inv in all_invoices:
            if inv.get("case_id") in client_case_set:
                billing_records.append({
                    "type": "invoice",
                    "id": inv.get("id", ""),
                    "case_id": inv.get("case_id", ""),
                    "status": inv.get("status", ""),
                    "total": inv.get("total", 0),
                    "date_created": inv.get("date_created", ""),
                    "due_date": inv.get("due_date", ""),
                })

        # Payment plans
        plans = load_payment_plans(client_id)
        for plan in plans:
            billing_records.append({
                "type": "payment_plan",
                "id": plan.get("id", ""),
                "status": plan.get("status", ""),
                "total_amount": plan.get("total_amount", 0),
                "created_at": plan.get("created_at", ""),
                "payments": [
                    {
                        "amount": p.get("amount", 0),
                        "date": p.get("date", p.get("paid_at", "")),
                        "method": p.get("method", ""),
                    }
                    for p in plan.get("payments", [])
                ],
            })
    except Exception:
        logger.warning("Failed to load billing records for GDPR export (client %s)", client_id)

    # --- Communications ---
    communications = []
    try:
        from core.comms import get_client_comm_log
        for comm in get_client_comm_log(client_id):
            communications.append({
                "id": comm.get("id", ""),
                "subject": comm.get("subject", ""),
                "channel": comm.get("channel", ""),
                "sent_at": comm.get("sent_at", ""),
                "status": comm.get("status", ""),
                "trigger_type": comm.get("trigger_type", ""),
            })
    except Exception:
        logger.warning("Failed to load communications for GDPR export (client %s)", client_id)

    # --- Calendar events ---
    calendar_events = []
    try:
        from core.calendar_events import load_events
        all_events = load_events()
        for evt in all_events:
            if evt.get("client_id") == client_id or evt.get("case_id") in client_case_set:
                calendar_events.append({
                    "id": evt.get("id", ""),
                    "title": evt.get("title", ""),
                    "event_type": evt.get("event_type", ""),
                    "date": evt.get("date", ""),
                    "time": evt.get("time", ""),
                    "location": evt.get("location", ""),
                    "status": evt.get("status", ""),
                })
    except Exception:
        logger.warning("Failed to load calendar events for GDPR export (client %s)", client_id)

    # --- Consent records ---
    consent_records = _get_consent_records(client)

    # --- Intake answers ---
    intake_data = client.get("intake_answers", {})

    export = {
        "export_metadata": {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "client_id": client_id,
            "format": "JSON",
            "gdpr_article": "Article 20 -- Right to Data Portability",
            "exported_by": user.get("name", user.get("id", "")),
        },
        "personal_data": personal_data,
        "cases": cases,
        "billing_records": billing_records,
        "communications": communications,
        "calendar_events": calendar_events,
        "consent_records": consent_records,
        "intake_data": intake_data,
    }

    # Audit trail
    _append_audit_entry(
        action="data_export",
        client_id=client_id,
        performed_by=user.get("name", user.get("id", "")),
        details=f"Full data export generated. {len(cases)} cases, "
                f"{len(billing_records)} billing records, "
                f"{len(communications)} communications.",
    )

    logger.info("GDPR data export generated for client %s by %s", client_id, user.get("id"))
    return export


@router.post("/forget/{client_id}")
def forget_client(client_id: str, user: dict = Depends(require_role("admin"))):
    """
    Right to be forgotten -- create an erasure request.
    GDPR Article 17 -- Right to Erasure.

    Does not delete immediately. Creates an erasure request record,
    marks the client as 'erasure_pending', and returns an estimated
    completion timeline. Actual erasure is performed after a retention
    review period.
    """
    from core.crm import get_client, update_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check if an erasure request already exists
    existing_requests = _load_erasure_requests()
    for req in existing_requests:
        if req.get("client_id") == client_id and req.get("status") in ("pending", "processing"):
            raise HTTPException(
                status_code=409,
                detail=f"Erasure request already exists (ID: {req['id']}, status: {req['status']})",
            )

    # Create erasure request record
    request_id = f"erase_{uuid.uuid4().hex[:8]}"
    estimated_completion = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
    erasure_request = {
        "id": request_id,
        "client_id": client_id,
        "client_name": client.get("name", ""),
        "requested_by": user.get("name", user.get("id", "")),
        "requested_at": datetime.utcnow().isoformat() + "Z",
        "estimated_completion": estimated_completion,
        "status": "pending",
        "reason": "GDPR Article 17 -- Right to Erasure",
        "notes": "",
    }
    existing_requests.append(erasure_request)
    _save_erasure_requests(existing_requests)

    # Mark client as erasure_pending
    update_client(client_id, {"intake_status": "erasure_pending"})

    # Audit trail
    _append_audit_entry(
        action="erasure_request",
        client_id=client_id,
        performed_by=user.get("name", user.get("id", "")),
        details=f"Erasure request {request_id} created. "
                f"Client marked as erasure_pending. "
                f"Estimated completion: {estimated_completion}",
    )

    logger.info("GDPR erasure request %s created for client %s", request_id, client_id)
    return {
        "request_id": request_id,
        "status": "pending",
        "client_id": client_id,
        "estimated_completion": estimated_completion,
        "message": (
            "Erasure request has been recorded. Client data will be anonymized "
            "within 30 days after legal retention review. The client has been "
            "marked as 'erasure_pending'."
        ),
        "gdpr_article": "Article 17 -- Right to Erasure",
    }


@router.get("/consent/{client_id}")
def get_consent_status(client_id: str, user: dict = Depends(get_current_user)):
    """
    Check what data processing consents are on file for a client.
    Returns consent status per category with timestamps.
    """
    from core.crm import get_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    consent_records = _get_consent_records(client)

    # Audit trail (read-only, but still logged for compliance)
    _append_audit_entry(
        action="consent_check",
        client_id=client_id,
        performed_by=user.get("name", user.get("id", "")),
        details="Consent status checked.",
    )

    return {
        "client_id": client_id,
        "client_name": client.get("name", ""),
        "consents": consent_records,
    }


class ConsentUpdate(BaseModel):
    """Schema for updating consent status."""
    purpose: str
    granted: bool


@router.post("/consent/{client_id}")
def update_consent(
    client_id: str,
    body: ConsentUpdate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update consent for a specific processing purpose."""
    from core.crm import get_client, update_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    consents = client.get("gdpr_consents", {})
    consents[body.purpose] = {
        "granted": body.granted,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "updated_by": user.get("name", user.get("id", "")),
    }
    update_client(client_id, {"gdpr_consents": consents})

    action = "consent_granted" if body.granted else "consent_revoked"
    _append_audit_entry(
        action=action,
        client_id=client_id,
        performed_by=user.get("name", user.get("id", "")),
        details=f"Consent for '{body.purpose}' {'granted' if body.granted else 'revoked'}.",
    )

    return {
        "status": "updated",
        "client_id": client_id,
        "purpose": body.purpose,
        "granted": body.granted,
    }


@router.get("/audit-log")
def get_audit_log(
    client_id: str = "",
    action: str = "",
    limit: int = 100,
    user: dict = Depends(require_role("admin")),
):
    """
    Return the GDPR action audit trail.
    Optionally filter by client_id and/or action type.
    """
    log = _load_audit_log()

    # Apply filters
    if client_id:
        log = [e for e in log if e.get("client_id") == client_id]
    if action:
        log = [e for e in log if e.get("action") == action]

    # Sort newest first
    log.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return {
        "total": len(log),
        "items": log[:limit],
    }


@router.get("/erasure-requests")
def list_erasure_requests(
    status_filter: str = "",
    user: dict = Depends(require_role("admin")),
):
    """List all erasure requests, optionally filtered by status."""
    requests = _load_erasure_requests()
    if status_filter:
        requests = [r for r in requests if r.get("status") == status_filter]
    requests.sort(key=lambda r: r.get("requested_at", ""), reverse=True)
    return {"items": requests}


# ---- Helpers -------------------------------------------------------------


def _get_consent_records(client: Dict) -> List[Dict]:
    """Build consent records from client data, with defaults for standard categories."""
    stored_consents = client.get("gdpr_consents", {})
    created_at = client.get("created_at", "")

    # Standard consent categories
    standard_purposes = [
        "Case management",
        "AI analysis",
        "Email communications",
        "SMS communications",
        "Billing and invoicing",
        "Analytics",
    ]

    records = []
    for purpose in standard_purposes:
        if purpose in stored_consents:
            entry = stored_consents[purpose]
            records.append({
                "purpose": purpose,
                "granted": entry.get("granted", False),
                "date": entry.get("updated_at", created_at),
                "updated_by": entry.get("updated_by", ""),
            })
        else:
            # Default: case management and billing implied by engagement,
            # everything else defaults to not explicitly consented
            implied = purpose in ("Case management", "Billing and invoicing")
            records.append({
                "purpose": purpose,
                "granted": implied,
                "date": created_at if implied else None,
                "updated_by": "",
            })

    # Include any non-standard consents stored on the client
    for purpose, entry in stored_consents.items():
        if purpose not in standard_purposes:
            records.append({
                "purpose": purpose,
                "granted": entry.get("granted", False),
                "date": entry.get("updated_at", ""),
                "updated_by": entry.get("updated_by", ""),
            })

    return records
