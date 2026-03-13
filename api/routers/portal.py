# ---- Client Portal Router ------------------------------------------------
# Read-only and limited-write views for client status information.
# Returns case status, documents, invoices, messages, and deadlines.
# No internal analysis or attorney work product exposed.

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portal", tags=["Portal"])


# ---- Schemas -------------------------------------------------------------


class ClientMessage(BaseModel):
    """Schema for client message submission."""
    subject: str = Field(..., max_length=500)
    message: str = Field(..., max_length=10000)
    case_id: Optional[str] = None


# ---- Endpoints -----------------------------------------------------------


@router.get("/client/{client_id}/status")
def client_portal_status(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a read-only portal view for a client.
    Returns: client name, linked cases (with phases/next dates),
    payment plan summary, recent communications.
    No sensitive analysis data exposed.
    """
    try:
        from core.crm import get_client, get_cases_for_client
        client = get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        client_name = client.get("name", "") or f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()

        # Get linked cases with basic info
        from api.deps import get_case_manager
        cm = get_case_manager()
        case_ids = get_cases_for_client(client_id)
        cases = []
        for cid in case_ids[:10]:  # Limit to 10 cases
            meta = cm.get_case_metadata(cid)
            if meta:
                cases.append({
                    "id": cid,
                    "name": meta.get("name", cid),
                    "phase": meta.get("phase", meta.get("status", "active")),
                    "sub_phase": meta.get("sub_phase", ""),
                    "case_type": meta.get("case_type", ""),
                    "last_updated": meta.get("last_updated", ""),
                })

        # Get next court dates from calendar events
        next_dates = {}
        try:
            from core.calendar_events import get_events_for_case
            today = datetime.now().strftime("%Y-%m-%d")
            for cid in case_ids[:10]:
                events = get_events_for_case(cid)
                future = [e for e in events
                          if e.get("date", "") >= today
                          and e.get("status") != "cancelled"]
                future.sort(key=lambda e: e.get("date", ""))
                if future:
                    next_dates[cid] = {
                        "date": future[0].get("date", ""),
                        "title": future[0].get("title", ""),
                    }
        except Exception:
            pass

        for c in cases:
            c["next_court_date"] = next_dates.get(c["id"])

        # Payment plan summary
        payment_summary = None
        try:
            from core.billing import load_payment_plans
            plans = load_payment_plans(client_id)
            if plans:
                active_plans = [p for p in plans if p.get("status") == "active"]
                plan = active_plans[0] if active_plans else plans[0]
                total = plan.get("total_amount", 0)
                payments = plan.get("payments", [])
                paid = sum(p.get("amount", 0) for p in payments)
                payment_summary = {
                    "plan_id": plan.get("id", ""),
                    "total_amount": total,
                    "total_paid": round(paid, 2),
                    "remaining": round(total - paid, 2),
                    "status": plan.get("status", "active"),
                    "next_due_date": None,
                    "next_due_amount": 0,
                }
                # Find next unpaid scheduled payment
                scheduled = plan.get("scheduled_payments", [])
                for sp in scheduled:
                    if sp.get("status") in ("pending", "overdue"):
                        payment_summary["next_due_date"] = sp.get("due_date")
                        payment_summary["next_due_amount"] = sp.get("amount", 0)
                        break
        except Exception:
            logger.warning("Failed to load payment plan for portal")

        # Recent communications (last 5)
        recent_comms = []
        try:
            from core.comms import get_comm_log
            log = get_comm_log()
            client_comms = [e for e in log if e.get("client_id") == client_id]
            client_comms.sort(key=lambda e: e.get("sent_at", ""), reverse=True)
            for comm in client_comms[:5]:
                recent_comms.append({
                    "subject": comm.get("subject", ""),
                    "channel": comm.get("channel", "email"),
                    "sent_at": comm.get("sent_at", ""),
                    "status": comm.get("status", "sent"),
                })
        except Exception:
            pass

        return {
            "client_id": client_id,
            "client_name": client_name,
            "cases": cases,
            "payment_summary": payment_summary,
            "recent_communications": recent_comms,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load portal status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/client/{client_id}/documents")
def client_portal_documents(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get client-accessible documents.

    Returns documents that are tagged as 'client-visible' or are in
    commonly shared categories (Court Filing, Correspondence).
    Internal analysis and attorney work product are excluded.
    """
    from core.crm import get_client, get_cases_for_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from api.deps import get_case_manager
    cm = get_case_manager()
    case_ids = get_cases_for_client(client_id)

    # Categories safe to share with clients
    client_visible_categories = {
        "Court Filing", "Correspondence", "Contract/Agreement",
    }

    documents = []
    for cid in case_ids[:10]:
        try:
            meta = cm.get_case_metadata(cid)
            case_name = meta.get("name", cid) if meta else cid

            files = cm.storage.list_files(cid)
            for f in files:
                # Include files tagged as client-visible or in safe categories
                tags = f.get("tags", [])
                is_client_visible = "client-visible" in tags
                in_safe_category = any(t in client_visible_categories for t in tags)

                if is_client_visible or in_safe_category:
                    documents.append({
                        "case_id": cid,
                        "case_name": case_name,
                        "filename": f.get("filename", f.get("name", "")),
                        "tags": [t for t in tags if t in client_visible_categories or t == "client-visible"],
                        "uploaded_at": f.get("uploaded_at", f.get("created_at", "")),
                        "size_bytes": f.get("size", f.get("size_bytes", 0)),
                    })
        except Exception:
            logger.warning("Failed to list documents for case %s in portal", cid)

    documents.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)

    return {
        "client_id": client_id,
        "documents": documents,
        "total": len(documents),
    }


@router.get("/client/{client_id}/invoices")
def client_portal_invoices(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """Get outstanding invoices for a client.

    Returns invoices with status (paid, unpaid, overdue) for all
    cases linked to the client.
    """
    from core.crm import get_client, get_cases_for_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    case_ids = get_cases_for_client(client_id)
    client_case_set = set(case_ids)

    invoices = []
    try:
        from core.billing import load_invoices

        all_invoices = load_invoices()
        for inv in all_invoices:
            if inv.get("case_id") in client_case_set:
                # Determine display status
                status = inv.get("status", "draft")
                if status == "void":
                    continue  # Don't show voided invoices to clients

                invoices.append({
                    "id": inv.get("id", ""),
                    "invoice_number": inv.get("invoice_number", ""),
                    "case_id": inv.get("case_id", ""),
                    "status": status,
                    "total": inv.get("total", 0),
                    "amount_paid": inv.get("amount_paid", 0),
                    "balance_due": inv.get("total", 0) - inv.get("amount_paid", 0),
                    "date_created": inv.get("date_created", ""),
                    "due_date": inv.get("due_date", ""),
                })
    except Exception:
        logger.warning("Failed to load invoices for portal (client %s)", client_id)

    # Also include payment plan info
    payment_plans = []
    try:
        from core.billing import load_payment_plans

        plans = load_payment_plans(client_id)
        for plan in plans:
            payments = plan.get("payments", [])
            total_paid = sum(p.get("amount", 0) for p in payments)
            total = plan.get("total_amount", 0)

            # Upcoming scheduled payments
            upcoming = []
            for sp in plan.get("scheduled_payments", []):
                if sp.get("status") in ("pending", "overdue"):
                    upcoming.append({
                        "due_date": sp.get("due_date", ""),
                        "amount": sp.get("amount", 0),
                        "status": sp.get("status", "pending"),
                    })

            payment_plans.append({
                "id": plan.get("id", ""),
                "status": plan.get("status", ""),
                "total_amount": total,
                "total_paid": round(total_paid, 2),
                "remaining": round(total - total_paid, 2),
                "upcoming_payments": upcoming[:5],
            })
    except Exception:
        logger.warning("Failed to load payment plans for portal (client %s)", client_id)

    invoices.sort(key=lambda i: i.get("date_created", ""), reverse=True)

    return {
        "client_id": client_id,
        "invoices": invoices,
        "payment_plans": payment_plans,
        "total_invoices": len(invoices),
    }


@router.post("/client/{client_id}/messages")
def client_portal_send_message(
    client_id: str,
    body: ClientMessage,
    user: dict = Depends(get_current_user),
):
    """Submit a message from the client to the firm.

    Adds the message to the communications queue for attorney review.
    """
    from core.crm import get_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        from core.comms import add_to_queue

        client_name = client.get("name", "") or (
            f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        )

        comm_id = add_to_queue(
            client_id=client_id,
            trigger_type="custom",
            subject=body.subject,
            body_html=body.message,
            case_id=body.case_id or "",
            channel="portal",
            priority="medium",
            metadata={
                "client_name": client_name,
                "client_email": client.get("email", ""),
                "source": "client_portal",
                "submitted_by": user.get("name", user.get("id", "")),
            },
        )

        logger.info(
            "Portal message submitted by client %s (comm_id: %s)",
            client_id, comm_id,
        )

        return {
            "status": "submitted",
            "message_id": comm_id,
            "client_id": client_id,
            "confirmation": (
                "Your message has been received and will be reviewed "
                "by your attorney. You will receive a response shortly."
            ),
        }
    except Exception:
        logger.exception("Failed to submit portal message for client %s", client_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/client/{client_id}/messages")
def client_portal_messages(
    client_id: str,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get message history between client and firm.

    Returns both sent communications and portal-submitted messages.
    """
    from core.crm import get_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    messages = []

    # Communication log (firm -> client)
    try:
        from core.comms import get_client_comm_log
        for comm in get_client_comm_log(client_id):
            messages.append({
                "id": comm.get("id", ""),
                "direction": "firm_to_client",
                "subject": comm.get("subject", ""),
                "body": comm.get("body", ""),
                "channel": comm.get("channel", "email"),
                "sent_at": comm.get("sent_at", ""),
                "status": comm.get("status", ""),
            })
    except Exception:
        logger.warning("Failed to load comm log for portal messages (client %s)", client_id)

    # Queue items from portal (client -> firm)
    try:
        from core.comms import get_queue
        queue = get_queue()
        for item in queue:
            if (item.get("client_id") == client_id
                    and item.get("metadata", {}).get("source") == "client_portal"):
                messages.append({
                    "id": item.get("id", ""),
                    "direction": "client_to_firm",
                    "subject": item.get("subject", ""),
                    "body": item.get("body_html", ""),
                    "channel": "portal",
                    "sent_at": item.get("created_at", ""),
                    "status": item.get("status", "pending"),
                })
    except Exception:
        logger.warning("Failed to load portal messages from queue (client %s)", client_id)

    # Sort by date, newest first
    messages.sort(key=lambda m: m.get("sent_at", ""), reverse=True)

    return {
        "client_id": client_id,
        "messages": messages[:limit],
        "total": len(messages),
    }


@router.get("/client/{client_id}/deadlines")
def client_portal_deadlines(
    client_id: str,
    days: int = 60,
    user: dict = Depends(get_current_user),
):
    """Get upcoming deadlines and events relevant to the client.

    Returns calendar events linked to the client's cases, limited to
    future events within the specified number of days.
    """
    from core.crm import get_client, get_cases_for_client

    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    case_ids = get_cases_for_client(client_id)
    client_case_set = set(case_ids)

    deadlines = []

    # Calendar events for client's cases
    try:
        from core.calendar_events import get_upcoming_events

        upcoming = get_upcoming_events(days=days)
        for evt in upcoming:
            # Include events linked to client's cases or directly to the client
            if (evt.get("case_id") in client_case_set
                    or evt.get("client_id") == client_id):
                deadlines.append({
                    "id": evt.get("id", ""),
                    "title": evt.get("title", ""),
                    "event_type": evt.get("event_type", "Other"),
                    "date": evt.get("date", ""),
                    "time": evt.get("time", ""),
                    "location": evt.get("location", ""),
                    "case_id": evt.get("case_id", ""),
                    "status": evt.get("status", "scheduled"),
                    "days_until": evt.get("days_until", 999),
                })
    except Exception:
        logger.warning("Failed to load calendar events for portal (client %s)", client_id)

    # Case deadlines
    try:
        from api.deps import get_case_manager
        cm = get_case_manager()

        for cid in case_ids[:10]:
            try:
                case_deadlines = cm.get_deadlines(cid)
                today_str = datetime.now().strftime("%Y-%m-%d")
                for dl in case_deadlines:
                    dl_date = dl.get("date", "")
                    if dl_date >= today_str:
                        deadlines.append({
                            "id": dl.get("id", ""),
                            "title": dl.get("label", dl.get("title", "Deadline")),
                            "event_type": "Filing Deadline",
                            "date": dl_date,
                            "time": "",
                            "location": "",
                            "case_id": cid,
                            "status": "upcoming",
                            "days_until": dl.get("days_remaining", 999),
                        })
            except Exception:
                pass  # Some cases may not have deadlines
    except Exception:
        logger.warning("Failed to load case deadlines for portal (client %s)", client_id)

    # Sort by date
    deadlines.sort(key=lambda d: (d.get("date", "9999"), d.get("time", "99:99")))

    return {
        "client_id": client_id,
        "deadlines": deadlines,
        "total": len(deadlines),
    }
