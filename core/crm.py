"""
crm.py -- Client Relationship Management Module
Firm-wide client directory with contacts, intake forms, and case linking.
Storage: data/crm/clients.json
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# -- Data Directory --
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CRM_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "crm")
_CLIENTS_FILE = os.path.join(_CRM_DIR, "clients.json")


def _ensure_dir():
    os.makedirs(_CRM_DIR, exist_ok=True)


# -- Constants --
CLIENT_TYPES = ["Individual", "Business", "Government", "Organization", "Trust/Estate"]

CLIENT_STATUSES = ["prospective", "active", "former", "declined"]

REFERRAL_SOURCES = [
    "Word of Mouth", "Website", "Bar Referral", "Court Appointment",
    "Existing Client", "Social Media", "Advertisement", "Other"
]

INTAKE_TEMPLATES = {
    "general": {
        "name": "General Client Intake",
        "fields": [
            {"key": "first_name", "label": "First Name", "type": "text", "required": True},
            {"key": "last_name", "label": "Last Name", "type": "text", "required": True},
            {"key": "preferred_name", "label": "Preferred Name", "type": "text", "required": False},
            {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": False},
            {"key": "ssn_last4", "label": "Last 4 of SSN", "type": "text", "required": False},
            {"key": "phone", "label": "Phone Number", "type": "text", "required": True},
            {"key": "email", "label": "Email Address", "type": "text", "required": False},
            {"key": "address", "label": "Street Address", "type": "text", "required": False},
            {"key": "city", "label": "City", "type": "text", "required": False},
            {"key": "state", "label": "State", "type": "text", "required": False},
            {"key": "zip_code", "label": "ZIP Code", "type": "text", "required": False},
            {"key": "employer", "label": "Employer", "type": "text", "required": False},
            {"key": "occupation", "label": "Occupation", "type": "text", "required": False},
            {"key": "emergency_contact", "label": "Emergency Contact Name", "type": "text", "required": False},
            {"key": "emergency_phone", "label": "Emergency Contact Phone", "type": "text", "required": False},
            {"key": "how_heard", "label": "How did you hear about us?", "type": "text", "required": False},
        ],
    },
    "criminal": {
        "name": "Criminal Defense Intake",
        "fields": [
            {"key": "first_name", "label": "First Name", "type": "text", "required": True},
            {"key": "last_name", "label": "Last Name", "type": "text", "required": True},
            {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
            {"key": "phone", "label": "Phone Number", "type": "text", "required": True},
            {"key": "email", "label": "Email Address", "type": "text", "required": False},
            {"key": "address", "label": "Address", "type": "text", "required": False},
            {"key": "charges", "label": "Charges/Allegations", "type": "textarea", "required": True},
            {"key": "arrest_date", "label": "Date of Arrest", "type": "date", "required": False},
            {"key": "court", "label": "Court / Jurisdiction", "type": "text", "required": False},
            {"key": "case_number", "label": "Case/Docket Number", "type": "text", "required": False},
            {"key": "bond_status", "label": "Bond Status", "type": "text", "required": False},
            {"key": "prior_record", "label": "Prior Criminal Record?", "type": "textarea", "required": False},
            {"key": "attorney_prev", "label": "Previous Attorney (if any)", "type": "text", "required": False},
            {"key": "witnesses", "label": "Known Witnesses", "type": "textarea", "required": False},
            {"key": "statement_given", "label": "Did you give a statement to police?", "type": "text", "required": False},
            {"key": "additional_info", "label": "Anything else we should know?", "type": "textarea", "required": False},
        ],
    },
    "civil": {
        "name": "Civil Litigation Intake",
        "fields": [
            {"key": "first_name", "label": "First Name", "type": "text", "required": True},
            {"key": "last_name", "label": "Last Name", "type": "text", "required": True},
            {"key": "phone", "label": "Phone Number", "type": "text", "required": True},
            {"key": "email", "label": "Email Address", "type": "text", "required": False},
            {"key": "address", "label": "Address", "type": "text", "required": False},
            {"key": "opposing_party", "label": "Opposing Party Name(s)", "type": "text", "required": True},
            {"key": "dispute_summary", "label": "Brief Summary of Dispute", "type": "textarea", "required": True},
            {"key": "incident_date", "label": "Date of Incident", "type": "date", "required": False},
            {"key": "damages", "label": "Damages / Amount in Controversy", "type": "text", "required": False},
            {"key": "insurance", "label": "Insurance Information", "type": "text", "required": False},
            {"key": "prior_legal_action", "label": "Any prior legal action taken?", "type": "textarea", "required": False},
            {"key": "documents_available", "label": "Documents available?", "type": "textarea", "required": False},
            {"key": "desired_outcome", "label": "What outcome are you seeking?", "type": "textarea", "required": False},
            {"key": "additional_info", "label": "Anything else we should know?", "type": "textarea", "required": False},
        ],
    },
}


# -- Helper: Load / Save --

def _ensure_name_fields(client: Dict) -> Dict:
    """Backward compat: split legacy 'name' into first_name/last_name if missing."""
    if "first_name" not in client or "last_name" not in client:
        full = client.get("name", "")
        # Detect "Last, First" format (used by existing data)
        if "," in full:
            parts = full.split(",", 1)
            client.setdefault("last_name", parts[0].strip())
            client.setdefault("first_name", parts[1].strip())
        else:
            parts = full.split(" ", 1)
            client.setdefault("first_name", parts[0].strip())
            client.setdefault("last_name", parts[1].strip() if len(parts) > 1 else "")
    return client


def _ensure_address_fields(client: Dict) -> Dict:
    """Backward compat: migrate legacy 'address' to mailing_address."""
    if "mailing_address" not in client:
        client["mailing_address"] = client.get("address", "")
    if "home_address" not in client:
        client["home_address"] = ""
    if "home_same_as_mailing" not in client:
        client["home_same_as_mailing"] = False
    return client


def _load_all() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_CLIENTS_FILE):
        with open(_CLIENTS_FILE, "r", encoding="utf-8") as f:
            clients = json.load(f)
        return [_ensure_address_fields(_ensure_name_fields(c)) for c in clients]
    return []


def _save_all(clients: List[Dict]):
    _ensure_dir()
    with open(_CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)


# -- CRUD --
def add_client(
    name: str = "",
    client_type: str = "Individual",
    email: str = "",
    phone: str = "",
    address: str = "",
    date_of_birth: str = "",
    employer: str = "",
    notes: str = "",
    intake_status: str = "active",
    referral_source: str = "",
    tags: List[str] = None,
    first_name: str = "",
    last_name: str = "",
    middle_name: str = "",
    suffix: str = "",
    mailing_address: str = "",
    home_address: str = "",
    home_same_as_mailing: bool = False,
) -> str:
    """Add a new client. Returns client ID.

    Accepts first_name/last_name (preferred) or legacy 'name' parameter.
    Accepts mailing_address/home_address or legacy 'address' parameter.
    """
    clients = _load_all()

    # Compute display name from first/last or legacy name
    if first_name or last_name:
        parts = [first_name.strip(), middle_name.strip(), last_name.strip()]
        _computed_name = " ".join(p for p in parts if p)
        if suffix and suffix.strip():
            _computed_name += f", {suffix.strip()}"
    elif name:
        _computed_name = name.strip()
    else:
        _computed_name = "Unknown"

    # Normalize addresses
    _mailing = mailing_address.strip() if mailing_address else address.strip()
    _home = "" if home_same_as_mailing else home_address.strip()

    client = {
        "id": uuid.uuid4().hex[:8],
        "name": _computed_name,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "middle_name": middle_name.strip(),
        "suffix": suffix.strip(),
        "client_type": client_type,
        "email": email.strip(),
        "phone": phone.strip(),
        "address": _mailing,  # legacy compat
        "mailing_address": _mailing,
        "home_address": _home,
        "home_same_as_mailing": home_same_as_mailing,
        "date_of_birth": date_of_birth,
        "employer": employer.strip(),
        "notes": notes.strip(),
        "intake_date": datetime.now().strftime("%Y-%m-%d"),
        "intake_status": intake_status,
        "referral_source": referral_source,
        "linked_case_ids": [],
        "tags": tags or [],
        "intake_answers": {},
        "created_at": datetime.now().isoformat(),
    }
    clients.append(client)
    _save_all(clients)
    return client["id"]


def load_clients() -> List[Dict]:
    """Load all clients."""
    return _load_all()


def get_client(client_id: str) -> Optional[Dict]:
    """Get a single client by ID."""
    for c in _load_all():
        if c.get("id") == client_id:
            return c
    return None


def update_client(client_id: str, updates: Dict) -> bool:
    """Update fields on a client. Returns True if found."""
    clients = _load_all()
    for c in clients:
        if c.get("id") == client_id:
            for k, v in updates.items():
                if k != "id":
                    c[k] = v
            c["updated_at"] = datetime.now().isoformat()
            _save_all(clients)
            return True
    return False


def delete_client(client_id: str) -> bool:
    """Delete a client. Returns True if found."""
    clients = _load_all()
    filtered = [c for c in clients if c.get("id") != client_id]
    if len(filtered) < len(clients):
        _save_all(filtered)
        return True
    return False


# -- Search --
def search_clients(query: str) -> List[Dict]:
    """Search clients by name, email, or phone (case-insensitive partial match)."""
    if not query.strip():
        return _load_all()
    q = query.lower().strip()
    results = []
    for c in _load_all():
        if (q in c.get("name", "").lower()
                or q in c.get("first_name", "").lower()
                or q in c.get("last_name", "").lower()
                or q in c.get("email", "").lower()
                or q in c.get("phone", "").lower()
                or q in c.get("employer", "").lower()
                or q in c.get("mailing_address", "").lower()
                or q in c.get("home_address", "").lower()
                or any(q in t.lower() for t in c.get("tags", []))):
            results.append(c)
    return results


# -- Case Linking --
def link_client_to_case(client_id: str, case_id: str) -> bool:
    """Link a client to a case. Returns True if successful."""
    clients = _load_all()
    for c in clients:
        if c.get("id") == client_id:
            linked = c.get("linked_case_ids", [])
            if case_id not in linked:
                linked.append(case_id)
                c["linked_case_ids"] = linked
                _save_all(clients)
            return True
    return False


def unlink_client_from_case(client_id: str, case_id: str) -> bool:
    """Unlink a client from a case. Returns True if found."""
    clients = _load_all()
    for c in clients:
        if c.get("id") == client_id:
            linked = c.get("linked_case_ids", [])
            if case_id in linked:
                linked.remove(case_id)
                c["linked_case_ids"] = linked
                _save_all(clients)
            return True
    return False


def get_cases_for_client(client_id: str) -> List[str]:
    """Get all case IDs linked to a client."""
    client = get_client(client_id)
    if client:
        return client.get("linked_case_ids", [])
    return []


def get_clients_for_case(case_id: str) -> List[Dict]:
    """Get all clients linked to a specific case."""
    return [c for c in _load_all() if case_id in c.get("linked_case_ids", [])]


# -- Intake Templates & Answers --
def get_intake_templates() -> Dict:
    """Returns available intake form templates."""
    return INTAKE_TEMPLATES


def save_intake_answers(client_id: str, template_key: str, answers: Dict) -> bool:
    """Save intake questionnaire answers for a client."""
    clients = _load_all()
    for c in clients:
        if c.get("id") == client_id:
            intake = c.get("intake_answers", {})
            intake[template_key] = {
                "answers": answers,
                "completed_at": datetime.now().isoformat(),
            }
            c["intake_answers"] = intake
            _save_all(clients)
            return True
    return False


def get_intake_answers(client_id: str, template_key: str = "") -> Dict:
    """Get intake answers for a client. If template_key is empty, returns all."""
    client = get_client(client_id)
    if not client:
        return {}
    all_answers = client.get("intake_answers", {})
    if template_key:
        return all_answers.get(template_key, {})
    return all_answers


# -- Client-Centric Helpers --

def get_client_for_case(case_id: str) -> Optional[Dict]:
    """Get the primary (first-linked) client for a case. Returns None if no link."""
    for c in _load_all():
        if case_id in c.get("linked_case_ids", []):
            return c
    return None


def get_all_clients_grouped(case_mgr=None) -> List[Dict]:
    """
    Returns clients sorted alphabetically, each with a 'cases' list pre-loaded.
    If case_mgr is provided, each case entry includes its full metadata.
    """
    clients = _load_all()
    result = []
    for c in sorted(clients, key=lambda x: x.get("name", "").lower()):
        entry = dict(c)
        case_ids = c.get("linked_case_ids", [])
        if case_mgr:
            cases = []
            for cid in case_ids:
                meta = case_mgr.get_case_metadata(cid)
                if meta:
                    cases.append(meta)
            entry["cases"] = cases
        else:
            entry["cases"] = [{"id": cid} for cid in case_ids]
        result.append(entry)
    return result


# -- Stats --
def get_crm_stats() -> Dict:
    """Aggregate CRM statistics for dashboard display."""
    clients = _load_all()
    total = len(clients)

    status_counts = {}
    type_counts = {}
    referral_counts = {}

    for c in clients:
        s = c.get("intake_status", "active")
        status_counts[s] = status_counts.get(s, 0) + 1

        t = c.get("client_type", "Individual")
        type_counts[t] = type_counts.get(t, 0) + 1

        r = c.get("referral_source", "")
        if r:
            referral_counts[r] = referral_counts.get(r, 0) + 1

    # Recently added (last 30 days)
    thirty_days_ago = datetime.now().strftime("%Y-%m-%d")
    recent = [c for c in clients if c.get("intake_date", "") >= thirty_days_ago[:7]]

    # Clients without linked cases
    unlinked = [c for c in clients if not c.get("linked_case_ids")]

    return {
        "total_clients": total,
        "active": status_counts.get("active", 0),
        "prospective": status_counts.get("prospective", 0),
        "former": status_counts.get("former", 0),
        "declined": status_counts.get("declined", 0),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "referral_counts": referral_counts,
        "recent_count": len(recent),
        "unlinked_count": len(unlinked),
    }
