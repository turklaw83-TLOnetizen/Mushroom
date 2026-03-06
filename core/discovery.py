# ---- Discovery Command Center ------------------------------------------------
# Civil-only discovery request tracking, production sets, and privilege log.
# Storage: data/cases/{case_id}/discovery.json

import json
import logging
import os
import secrets
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CIVIL_CASE_TYPES = ("civil-plaintiff", "civil-defendant", "civil-juvenile")

REQUEST_TYPES = ("interrogatories", "rfp", "rfa")

REQUEST_STATUSES = (
    "draft",
    "served",
    "response_pending",
    "response_received",
    "deficient",
    "motion_to_compel",
    "complete",
)

ITEM_STATUSES = ("pending", "answered", "objected", "supplemented")

PRODUCTION_STATUSES = ("preparing", "produced", "supplemented")

PRIVILEGE_TYPES = ("attorney-client", "work_product", "joint_defense", "other")

# Default response deadlines (days) by request type
DEFAULT_DEADLINES = {
    "interrogatories": 30,
    "rfp": 30,
    "rfa": 30,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_id() -> str:
    return secrets.token_hex(4)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _discovery_path(data_dir: str, case_id: str) -> str:
    case_dir = os.path.join(data_dir, "cases", case_id)
    os.makedirs(case_dir, exist_ok=True)
    return os.path.join(case_dir, "discovery.json")


def _empty_discovery() -> Dict:
    return {"requests": [], "production_sets": [], "privilege_log": []}


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_discovery(data_dir: str, case_id: str) -> Dict:
    """Load discovery data for a case, returning empty structure if none."""
    path = _discovery_path(data_dir, case_id)
    if not os.path.exists(path):
        return _empty_discovery()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all keys exist
        for key in ("requests", "production_sets", "privilege_log"):
            if key not in data:
                data[key] = []
        return data
    except Exception:
        logger.exception("Failed to load discovery.json for case %s", case_id)
        return _empty_discovery()


def save_discovery(data_dir: str, case_id: str, data: Dict) -> None:
    """Persist discovery data to disk."""
    path = _discovery_path(data_dir, case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def is_civil_case(case_type: str) -> bool:
    """Check if a case type is civil (discovery-eligible)."""
    return case_type in CIVIL_CASE_TYPES


# ---------------------------------------------------------------------------
# Discovery Requests — CRUD
# ---------------------------------------------------------------------------

def add_request(
    data_dir: str,
    case_id: str,
    *,
    direction: str = "outbound",
    request_type: str = "interrogatories",
    title: str = "",
    served_on: str = "",
    served_by: str = "",
    date_served: str = "",
    items: Optional[List[Dict]] = None,
    notes: str = "",
    ai_drafted: bool = False,
    targeting: Optional[Dict] = None,
    response_days: int = 0,
) -> str:
    """Add a new discovery request. Returns the request ID."""
    if request_type not in REQUEST_TYPES:
        raise ValueError(f"Invalid request_type: {request_type}")
    if direction not in ("outbound", "inbound"):
        raise ValueError(f"Invalid direction: {direction}")

    rid = _gen_id()
    now = _now_iso()

    # Calculate response deadline
    if not response_days:
        response_days = DEFAULT_DEADLINES.get(request_type, 30)
    if date_served:
        try:
            served_dt = date.fromisoformat(date_served)
            response_due = str(served_dt + timedelta(days=response_days))
        except ValueError:
            response_due = ""
    else:
        response_due = ""

    # Normalize items
    normalized_items = []
    for i, item in enumerate(items or [], start=1):
        normalized_items.append({
            "number": item.get("number", i),
            "text": item.get("text", ""),
            "response": item.get("response", ""),
            "objection": item.get("objection", ""),
            "status": item.get("status", "pending"),
        })

    request = {
        "id": rid,
        "direction": direction,
        "request_type": request_type,
        "title": title or f"{request_type.replace('_', ' ').title()} — Set {rid[:4].upper()}",
        "served_on": served_on,
        "served_by": served_by,
        "date_served": date_served,
        "response_due": response_due,
        "status": "draft",
        "items": normalized_items,
        "notes": notes,
        "created_at": now,
        "updated_at": now,
        "ai_drafted": ai_drafted,
        "targeting": targeting or {},
    }

    data = load_discovery(data_dir, case_id)
    data["requests"].append(request)
    save_discovery(data_dir, case_id, data)
    return rid


def get_request(data_dir: str, case_id: str, request_id: str) -> Optional[Dict]:
    """Get a single discovery request by ID."""
    data = load_discovery(data_dir, case_id)
    for req in data["requests"]:
        if req["id"] == request_id:
            return req
    return None


def update_request(
    data_dir: str,
    case_id: str,
    request_id: str,
    updates: Dict[str, Any],
) -> bool:
    """Update fields on a discovery request. Returns True if found."""
    data = load_discovery(data_dir, case_id)
    for req in data["requests"]:
        if req["id"] == request_id:
            # Prevent updating immutable fields
            updates.pop("id", None)
            updates.pop("created_at", None)
            req.update(updates)
            req["updated_at"] = _now_iso()
            save_discovery(data_dir, case_id, data)
            return True
    return False


def delete_request(data_dir: str, case_id: str, request_id: str) -> bool:
    """Delete a discovery request. Returns True if found."""
    data = load_discovery(data_dir, case_id)
    before = len(data["requests"])
    data["requests"] = [r for r in data["requests"] if r["id"] != request_id]
    if len(data["requests"]) < before:
        save_discovery(data_dir, case_id, data)
        return True
    return False


def update_request_status(
    data_dir: str,
    case_id: str,
    request_id: str,
    new_status: str,
) -> bool:
    """Update the status of a discovery request."""
    if new_status not in REQUEST_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    return update_request(data_dir, case_id, request_id, {"status": new_status})


def update_item_response(
    data_dir: str,
    case_id: str,
    request_id: str,
    item_number: int,
    *,
    response: Optional[str] = None,
    objection: Optional[str] = None,
    status: Optional[str] = None,
) -> bool:
    """Update an individual item's response/objection/status within a request."""
    data = load_discovery(data_dir, case_id)
    for req in data["requests"]:
        if req["id"] == request_id:
            for item in req.get("items", []):
                if item.get("number") == item_number:
                    if response is not None:
                        item["response"] = response
                    if objection is not None:
                        item["objection"] = objection
                    if status is not None:
                        if status not in ITEM_STATUSES:
                            raise ValueError(f"Invalid item status: {status}")
                        item["status"] = status
                    req["updated_at"] = _now_iso()
                    save_discovery(data_dir, case_id, data)
                    return True
            return False
    return False


# ---------------------------------------------------------------------------
# Discovery Summary & Cross-Case
# ---------------------------------------------------------------------------

def get_discovery_summary(data_dir: str, case_id: str) -> Dict:
    """Get summary stats for a case's discovery."""
    data = load_discovery(data_dir, case_id)
    requests = data.get("requests", [])

    summary = {
        "total_requests": len(requests),
        "outbound": 0,
        "inbound": 0,
        "by_type": {"interrogatories": 0, "rfp": 0, "rfa": 0},
        "by_status": {},
        "overdue": 0,
        "total_items": 0,
        "items_pending": 0,
        "items_answered": 0,
        "production_sets": len(data.get("production_sets", [])),
        "privilege_entries": len(data.get("privilege_log", [])),
    }

    today = date.today()
    for req in requests:
        if req.get("direction") == "outbound":
            summary["outbound"] += 1
        else:
            summary["inbound"] += 1

        rtype = req.get("request_type", "other")
        summary["by_type"][rtype] = summary["by_type"].get(rtype, 0) + 1

        status = req.get("status", "draft")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

        # Overdue check
        due = req.get("response_due", "")
        if due and status in ("served", "response_pending"):
            try:
                if date.fromisoformat(due) < today:
                    summary["overdue"] += 1
            except ValueError:
                pass

        # Item counts
        items = req.get("items", [])
        summary["total_items"] += len(items)
        for item in items:
            if item.get("status") == "pending":
                summary["items_pending"] += 1
            elif item.get("status") in ("answered", "supplemented"):
                summary["items_answered"] += 1

    return summary


def get_cross_case_discovery(data_dir: str, case_mgr) -> List[Dict]:
    """Aggregate discovery data across all civil cases for the dashboard."""
    results = []
    try:
        cases = case_mgr.list_cases()
    except Exception:
        logger.exception("Failed to list cases for cross-case discovery")
        return results

    today = date.today()
    for case in cases:
        case_id = case.get("id", "")
        case_type = case.get("case_type", "")
        if not is_civil_case(case_type):
            continue

        data = load_discovery(data_dir, case_id)
        for req in data.get("requests", []):
            # Calculate if overdue
            due = req.get("response_due", "")
            is_overdue = False
            days_until_due = None
            if due:
                try:
                    due_dt = date.fromisoformat(due)
                    days_until_due = (due_dt - today).days
                    is_overdue = days_until_due < 0 and req.get("status") in (
                        "served", "response_pending",
                    )
                except ValueError:
                    pass

            results.append({
                "case_id": case_id,
                "case_name": case.get("name", ""),
                "case_type": case_type,
                "request_id": req.get("id", ""),
                "direction": req.get("direction", ""),
                "request_type": req.get("request_type", ""),
                "title": req.get("title", ""),
                "status": req.get("status", ""),
                "date_served": req.get("date_served", ""),
                "response_due": due,
                "is_overdue": is_overdue,
                "days_until_due": days_until_due,
                "item_count": len(req.get("items", [])),
            })

    # Sort: overdue first, then by due date
    results.sort(key=lambda x: (
        not x.get("is_overdue", False),
        x.get("response_due", "9999-12-31"),
    ))
    return results


# ---------------------------------------------------------------------------
# Production Sets
# ---------------------------------------------------------------------------

def add_production_set(
    data_dir: str,
    case_id: str,
    *,
    title: str,
    bates_prefix: str = "DEF",
    documents: Optional[List[Dict]] = None,
    produced_to: str = "",
    date_produced: str = "",
) -> str:
    """Create a new production set. Returns the set ID."""
    sid = _gen_id()
    now = _now_iso()

    # Use BatesStamper for Bates numbering
    case_dir = os.path.join(data_dir, "cases", case_id)
    try:
        from core.bates import BatesStamper
        stamper = BatesStamper(case_dir, prefix=bates_prefix)
    except ImportError:
        stamper = None

    stamped_docs = []
    for doc in (documents or []):
        filename = doc.get("filename", "")
        page_count = doc.get("page_count", 1)
        description = doc.get("description", "")

        bates_range = ""
        if stamper and filename:
            try:
                assignment = stamper.assign_bates(filename, page_count)
                bates_range = assignment.get("range_str", "")
            except Exception:
                logger.warning("Bates stamping failed for %s", filename)

        stamped_docs.append({
            "filename": filename,
            "bates_range": bates_range,
            "description": description,
            "page_count": page_count,
        })

    prod_set = {
        "id": sid,
        "title": title,
        "case_id": case_id,
        "bates_prefix": bates_prefix,
        "documents": stamped_docs,
        "produced_to": produced_to,
        "date_produced": date_produced,
        "status": "preparing",
        "created_at": now,
        "updated_at": now,
    }

    data = load_discovery(data_dir, case_id)
    data["production_sets"].append(prod_set)
    save_discovery(data_dir, case_id, data)
    return sid


def get_production_sets(data_dir: str, case_id: str) -> List[Dict]:
    """Get all production sets for a case."""
    data = load_discovery(data_dir, case_id)
    return data.get("production_sets", [])


def update_production_set(
    data_dir: str,
    case_id: str,
    set_id: str,
    updates: Dict,
) -> bool:
    """Update a production set."""
    data = load_discovery(data_dir, case_id)
    for ps in data.get("production_sets", []):
        if ps["id"] == set_id:
            updates.pop("id", None)
            updates.pop("created_at", None)
            ps.update(updates)
            ps["updated_at"] = _now_iso()
            save_discovery(data_dir, case_id, data)
            return True
    return False


# ---------------------------------------------------------------------------
# Privilege Log
# ---------------------------------------------------------------------------

def add_privilege_entry(
    data_dir: str,
    case_id: str,
    *,
    document: str = "",
    bates_number: str = "",
    privilege_type: str = "attorney-client",
    description: str = "",
    entry_date: str = "",
    from_party: str = "",
    to_party: str = "",
    subject: str = "",
    basis: str = "",
) -> str:
    """Add a privilege log entry. Returns the entry ID."""
    if privilege_type not in PRIVILEGE_TYPES:
        raise ValueError(f"Invalid privilege_type: {privilege_type}")

    eid = _gen_id()
    entry = {
        "id": eid,
        "document": document,
        "bates_number": bates_number,
        "privilege_type": privilege_type,
        "description": description,
        "date": entry_date,
        "from_party": from_party,
        "to_party": to_party,
        "subject": subject,
        "basis": basis,
        "created_at": _now_iso(),
    }

    data = load_discovery(data_dir, case_id)
    data["privilege_log"].append(entry)
    save_discovery(data_dir, case_id, data)
    return eid


def get_privilege_log(data_dir: str, case_id: str) -> List[Dict]:
    """Get the privilege log for a case."""
    data = load_discovery(data_dir, case_id)
    return data.get("privilege_log", [])


def delete_privilege_entry(data_dir: str, case_id: str, entry_id: str) -> bool:
    """Delete a privilege log entry."""
    data = load_discovery(data_dir, case_id)
    before = len(data["privilege_log"])
    data["privilege_log"] = [e for e in data["privilege_log"] if e["id"] != entry_id]
    if len(data["privilege_log"]) < before:
        save_discovery(data_dir, case_id, data)
        return True
    return False


# ---------------------------------------------------------------------------
# Response Deadline Calculator
# ---------------------------------------------------------------------------

def calculate_response_deadline(
    date_served: str,
    request_type: str = "interrogatories",
    extra_days: int = 0,
) -> str:
    """Calculate the response deadline from service date.

    Args:
        date_served: ISO date string
        request_type: Type of discovery request
        extra_days: Additional days (e.g., 5 for mail service)

    Returns:
        ISO date string for the deadline
    """
    base_days = DEFAULT_DEADLINES.get(request_type, 30)
    total_days = base_days + extra_days
    try:
        served_dt = date.fromisoformat(date_served)
        return str(served_dt + timedelta(days=total_days))
    except ValueError:
        raise ValueError(f"Invalid date format: {date_served}")
