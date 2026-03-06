# ---- Client Portal Router ------------------------------------------------
# Read-only view for client status information.
# Returns case status, payment summaries, and recent communications.

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portal", tags=["Portal"])


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
            from core.calendar_events import list_events
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            for cid in case_ids[:10]:
                events = list_events(case_id=cid)
                future = [e for e in events if e.get("date", "") >= today]
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
            from core.billing import get_plans_for_client
            plans = get_plans_for_client(client_id)
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
