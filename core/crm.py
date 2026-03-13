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
        _computed_name = f"{first_name.strip()} {last_name.strip()}".strip()
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


# -- Rep Agreements --

_REP_AGREEMENTS_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "crm", "rep_agreements")


def _rep_agreement_dir(client_id: str) -> str:
    """Return (and ensure) the directory for a client's rep agreement."""
    d = os.path.join(_REP_AGREEMENTS_DIR, client_id)
    os.makedirs(d, exist_ok=True)
    return d


def save_rep_agreement(
    client_id: str,
    file_data: bytes,
    filename: str,
    uploaded_by: str = "",
) -> bool:
    """Save a rep agreement file for a client. Replaces any existing agreement.
    Updates the client record with metadata. Returns True on success."""
    client = get_client(client_id)
    if not client:
        return False

    safe_name = os.path.basename(filename)
    if not safe_name:
        safe_name = "rep_agreement"

    # Delete any existing file in the directory
    d = _rep_agreement_dir(client_id)
    for existing in os.listdir(d):
        existing_path = os.path.join(d, existing)
        if os.path.isfile(existing_path):
            os.remove(existing_path)

    # Write new file
    file_path = os.path.join(d, safe_name)
    # Path traversal check
    real_path = os.path.realpath(file_path)
    real_dir = os.path.realpath(d)
    if not real_path.startswith(real_dir):
        logger.warning("Path traversal attempt in rep agreement: %s", filename)
        return False

    with open(file_path, "wb") as f:
        f.write(file_data)

    # Update client record with metadata
    update_client(client_id, {
        "rep_agreement": {
            "filename": safe_name,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": uploaded_by,
            "size_bytes": len(file_data),
        },
    })
    logger.info("Saved rep agreement for client %s: %s", client_id, safe_name)
    return True


def get_rep_agreement_path(client_id: str) -> Optional[str]:
    """Return the full path to the client's rep agreement file, or None."""
    client = get_client(client_id)
    if not client:
        return None
    meta = client.get("rep_agreement")
    if not meta or not meta.get("filename"):
        return None
    path = os.path.join(_rep_agreement_dir(client_id), meta["filename"])
    if os.path.isfile(path):
        return path
    return None


def delete_rep_agreement(client_id: str) -> bool:
    """Delete the rep agreement file and clear metadata from client record."""
    client = get_client(client_id)
    if not client:
        return False
    meta = client.get("rep_agreement")
    if not meta:
        return False

    # Delete the file
    d = _rep_agreement_dir(client_id)
    for existing in os.listdir(d):
        existing_path = os.path.join(d, existing)
        if os.path.isfile(existing_path):
            os.remove(existing_path)

    # Clear metadata
    update_client(client_id, {"rep_agreement": None})
    logger.info("Deleted rep agreement for client %s", client_id)
    return True


def get_rep_agreement_metadata(client_id: str) -> Optional[Dict]:
    """Return rep_agreement metadata from the client record, or None."""
    client = get_client(client_id)
    if not client:
        return None
    return client.get("rep_agreement")


def get_last_contact_dates() -> Dict[str, str]:
    """Return a mapping of client_id -> last communication sent date.
    Reads from the communication log.
    """
    import os, json
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir, "data", "comms", "log.json",
    )
    if not os.path.exists(log_path):
        return {}
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

    last_dates: Dict[str, str] = {}
    for entry in log:
        cid = entry.get("client_id", "")
        sent_at = entry.get("sent_at", "")
        if cid and sent_at:
            if cid not in last_dates or sent_at > last_dates[cid]:
                last_dates[cid] = sent_at
    return last_dates


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


# ===================================================================
#  Smart Intake Wizard -- Multi-step conditional intake forms
# ===================================================================

# In-memory session storage for active intake wizards.
# Keys: session_id -> {template, current_step, responses, client_id, created_at}
_intake_sessions: Dict[str, Dict] = {}

# Step definitions for each template type.  Each step has:
#   step (int), title (str), fields (list of dicts), condition (optional dict)
#
# Conditions reference prior responses:
#   {"field": "<field_name>", "equals": "<value>"}
#   {"field": "<field_name>", "in": ["val1", "val2"]}

_INTAKE_STEPS: Dict[str, List[Dict]] = {
    "general": [
        {
            "step": 1,
            "title": "Basic Information",
            "fields": [
                {"name": "first_name", "type": "text", "label": "First Name", "required": True},
                {"name": "last_name", "type": "text", "label": "Last Name", "required": True},
                {"name": "preferred_name", "type": "text", "label": "Preferred Name", "required": False},
                {"name": "date_of_birth", "type": "date", "label": "Date of Birth", "required": False},
                {"name": "phone", "type": "text", "label": "Phone Number", "required": True},
                {"name": "email", "type": "text", "label": "Email Address", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 2,
            "title": "Address & Employment",
            "fields": [
                {"name": "address", "type": "text", "label": "Street Address", "required": False},
                {"name": "city", "type": "text", "label": "City", "required": False},
                {"name": "state", "type": "text", "label": "State", "required": False},
                {"name": "zip_code", "type": "text", "label": "ZIP Code", "required": False},
                {"name": "employer", "type": "text", "label": "Employer", "required": False},
                {"name": "occupation", "type": "text", "label": "Occupation", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 3,
            "title": "Emergency Contact & Referral",
            "fields": [
                {"name": "emergency_contact", "type": "text", "label": "Emergency Contact Name", "required": False},
                {"name": "emergency_phone", "type": "text", "label": "Emergency Contact Phone", "required": False},
                {"name": "how_heard", "type": "select", "label": "How did you hear about us?",
                 "options": ["Word of Mouth", "Website", "Bar Referral", "Court Appointment",
                             "Existing Client", "Social Media", "Advertisement", "Other"],
                 "required": False},
                {"name": "additional_notes", "type": "textarea", "label": "Additional Notes", "required": False},
            ],
            "condition": None,
        },
    ],
    "criminal": [
        {
            "step": 1,
            "title": "Personal Information",
            "fields": [
                {"name": "first_name", "type": "text", "label": "First Name", "required": True},
                {"name": "last_name", "type": "text", "label": "Last Name", "required": True},
                {"name": "date_of_birth", "type": "date", "label": "Date of Birth", "required": True},
                {"name": "phone", "type": "text", "label": "Phone Number", "required": True},
                {"name": "email", "type": "text", "label": "Email Address", "required": False},
                {"name": "address", "type": "text", "label": "Address", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 2,
            "title": "Charge Details",
            "fields": [
                {"name": "charge_level", "type": "select", "label": "Charge Level",
                 "options": ["felony", "misdemeanor", "infraction", "unknown"],
                 "required": True},
                {"name": "charges", "type": "textarea", "label": "Charges / Allegations", "required": True},
                {"name": "arrest_date", "type": "date", "label": "Date of Arrest", "required": False},
                {"name": "court", "type": "text", "label": "Court / Jurisdiction", "required": False},
                {"name": "case_number", "type": "text", "label": "Case / Docket Number", "required": False},
            ],
            "condition": None,
        },
        {
            # Shown only for felony charges
            "step": 3,
            "title": "Bond & Prior Record (Felony)",
            "fields": [
                {"name": "bond_status", "type": "select", "label": "Bond Status",
                 "options": ["Released on bond", "In custody", "Personal recognizance", "No bond set", "Unknown"],
                 "required": True},
                {"name": "bond_amount", "type": "text", "label": "Bond Amount (if applicable)", "required": False},
                {"name": "prior_felonies", "type": "textarea", "label": "Prior Felony Convictions", "required": False},
                {"name": "prior_record", "type": "textarea", "label": "Full Prior Criminal Record", "required": False},
                {"name": "probation_parole", "type": "select", "label": "Currently on Probation/Parole?",
                 "options": ["No", "Probation", "Parole", "Supervised Release"],
                 "required": True},
            ],
            "condition": {"field": "charge_level", "equals": "felony"},
        },
        {
            # Shown only for misdemeanor charges
            "step": 3,
            "title": "Bond & Prior Record (Misdemeanor)",
            "fields": [
                {"name": "bond_status", "type": "select", "label": "Bond Status",
                 "options": ["Released on bond", "In custody", "Personal recognizance", "Citation release", "Unknown"],
                 "required": False},
                {"name": "prior_misdemeanors", "type": "textarea", "label": "Prior Misdemeanor History (if any)", "required": False},
            ],
            "condition": {"field": "charge_level", "equals": "misdemeanor"},
        },
        {
            # Generic fallback for unknown/infraction charge levels
            "step": 3,
            "title": "Additional Charge Information",
            "fields": [
                {"name": "bond_status", "type": "text", "label": "Bond Status (if applicable)", "required": False},
                {"name": "prior_record", "type": "textarea", "label": "Prior Criminal Record (if any)", "required": False},
            ],
            "condition": {"field": "charge_level", "in": ["infraction", "unknown"]},
        },
        {
            "step": 4,
            "title": "Witnesses & Statements",
            "fields": [
                {"name": "statement_given", "type": "select", "label": "Did you give a statement to police?",
                 "options": ["Yes", "No", "Unsure"],
                 "required": True},
                {"name": "witnesses", "type": "textarea", "label": "Known Witnesses", "required": False},
                {"name": "attorney_prev", "type": "text", "label": "Previous Attorney (if any)", "required": False},
                {"name": "additional_info", "type": "textarea", "label": "Anything else we should know?", "required": False},
            ],
            "condition": None,
        },
    ],
    "civil": [
        {
            "step": 1,
            "title": "Personal Information",
            "fields": [
                {"name": "first_name", "type": "text", "label": "First Name", "required": True},
                {"name": "last_name", "type": "text", "label": "Last Name", "required": True},
                {"name": "phone", "type": "text", "label": "Phone Number", "required": True},
                {"name": "email", "type": "text", "label": "Email Address", "required": False},
                {"name": "address", "type": "text", "label": "Address", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 2,
            "title": "Dispute Overview",
            "fields": [
                {"name": "civil_type", "type": "select", "label": "Type of Civil Matter",
                 "options": ["personal_injury", "contract", "property", "employment", "family", "other"],
                 "required": True},
                {"name": "opposing_party", "type": "text", "label": "Opposing Party Name(s)", "required": True},
                {"name": "dispute_summary", "type": "textarea", "label": "Brief Summary of Dispute", "required": True},
                {"name": "incident_date", "type": "date", "label": "Date of Incident", "required": False},
            ],
            "condition": None,
        },
        {
            # Personal injury follow-up
            "step": 3,
            "title": "Personal Injury Details",
            "fields": [
                {"name": "injury_description", "type": "textarea", "label": "Describe Your Injuries", "required": True},
                {"name": "medical_treatment", "type": "textarea", "label": "Medical Treatment Received", "required": False},
                {"name": "treating_physician", "type": "text", "label": "Treating Physician / Hospital", "required": False},
                {"name": "insurance_company", "type": "text", "label": "Insurance Company", "required": False},
                {"name": "insurance_claim_number", "type": "text", "label": "Insurance Claim Number", "required": False},
                {"name": "lost_wages", "type": "select", "label": "Lost Wages?",
                 "options": ["Yes", "No"],
                 "required": False},
                {"name": "damages_estimate", "type": "text", "label": "Estimated Damages ($)", "required": False},
            ],
            "condition": {"field": "civil_type", "equals": "personal_injury"},
        },
        {
            # Contract dispute follow-up
            "step": 3,
            "title": "Contract Dispute Details",
            "fields": [
                {"name": "contract_type", "type": "select", "label": "Type of Contract",
                 "options": ["Business", "Employment", "Lease/Rental", "Service Agreement", "Purchase", "Other"],
                 "required": True},
                {"name": "contract_date", "type": "date", "label": "Date of Contract", "required": False},
                {"name": "breach_description", "type": "textarea", "label": "How Was the Contract Breached?", "required": True},
                {"name": "contract_amount", "type": "text", "label": "Contract Amount / Value ($)", "required": False},
                {"name": "documents_available", "type": "select", "label": "Do You Have a Copy of the Contract?",
                 "options": ["Yes", "No", "Partial"],
                 "required": True},
            ],
            "condition": {"field": "civil_type", "equals": "contract"},
        },
        {
            # Generic follow-up for other civil types
            "step": 3,
            "title": "Additional Details",
            "fields": [
                {"name": "damages", "type": "text", "label": "Damages / Amount in Controversy ($)", "required": False},
                {"name": "insurance", "type": "text", "label": "Insurance Information", "required": False},
                {"name": "documents_available", "type": "textarea", "label": "Documents Available?", "required": False},
            ],
            "condition": {"field": "civil_type", "in": ["property", "employment", "family", "other"]},
        },
        {
            "step": 4,
            "title": "Legal History & Goals",
            "fields": [
                {"name": "prior_legal_action", "type": "textarea", "label": "Any Prior Legal Action Taken?", "required": False},
                {"name": "desired_outcome", "type": "textarea", "label": "What Outcome Are You Seeking?", "required": False},
                {"name": "additional_info", "type": "textarea", "label": "Anything Else We Should Know?", "required": False},
            ],
            "condition": None,
        },
    ],
    "family": [
        {
            "step": 1,
            "title": "Personal Information",
            "fields": [
                {"name": "first_name", "type": "text", "label": "First Name", "required": True},
                {"name": "last_name", "type": "text", "label": "Last Name", "required": True},
                {"name": "date_of_birth", "type": "date", "label": "Date of Birth", "required": False},
                {"name": "phone", "type": "text", "label": "Phone Number", "required": True},
                {"name": "email", "type": "text", "label": "Email Address", "required": False},
                {"name": "address", "type": "text", "label": "Address", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 2,
            "title": "Family Matter Details",
            "fields": [
                {"name": "family_matter_type", "type": "select", "label": "Type of Family Matter",
                 "options": ["divorce", "custody", "child_support", "adoption", "guardianship",
                             "domestic_violence", "other"],
                 "required": True},
                {"name": "spouse_partner_name", "type": "text", "label": "Spouse / Partner Name", "required": False},
                {"name": "children_count", "type": "text", "label": "Number of Children (if applicable)", "required": False},
                {"name": "children_ages", "type": "text", "label": "Children's Ages", "required": False},
                {"name": "marriage_date", "type": "date", "label": "Date of Marriage (if applicable)", "required": False},
                {"name": "separation_date", "type": "date", "label": "Date of Separation (if applicable)", "required": False},
            ],
            "condition": None,
        },
        {
            "step": 3,
            "title": "Assets & Support",
            "fields": [
                {"name": "shared_assets", "type": "textarea", "label": "Shared Assets / Property", "required": False},
                {"name": "current_custody", "type": "textarea", "label": "Current Custody Arrangement", "required": False},
                {"name": "support_paid_received", "type": "text", "label": "Current Support Paid/Received ($)", "required": False},
                {"name": "desired_outcome", "type": "textarea", "label": "What Outcome Are You Seeking?", "required": False},
                {"name": "additional_info", "type": "textarea", "label": "Anything Else We Should Know?", "required": False},
            ],
            "condition": None,
        },
    ],
}


def get_intake_steps(template: str) -> List[Dict]:
    """Returns the ordered list of intake steps for a template type.

    Only returns step definitions (not filtered by conditions -- that
    requires responses context).
    """
    return _INTAKE_STEPS.get(template, [])


def _evaluate_condition(condition: Optional[Dict], responses: Dict) -> bool:
    """Check whether a step condition is met given current responses.

    Returns True if the step should be shown.
    """
    if condition is None:
        return True

    field = condition.get("field", "")
    value = responses.get(field, "")

    if "equals" in condition:
        return value == condition["equals"]
    if "in" in condition:
        return value in condition["in"]

    # Unknown condition type -- show the step
    return True


def get_next_step(template: str, current_step: int, responses: Dict) -> Optional[Dict]:
    """Returns the next applicable step based on conditional logic.

    Walks the steps list from current_step+1 onward, returning the first
    step whose condition is met by the accumulated responses.
    Returns None if no more steps (intake is complete).
    """
    steps = _INTAKE_STEPS.get(template, [])
    if not steps:
        return None

    # Find all steps with step number > current_step
    # Steps can share a step number (conditional variants) so we process in order
    candidates = [s for s in steps if s["step"] > current_step]
    candidates.sort(key=lambda s: s["step"])

    # Find the next step number
    if not candidates:
        return None

    next_step_num = candidates[0]["step"]

    # Among candidates at this step number, find the first whose condition matches
    for step in candidates:
        if step["step"] != next_step_num:
            break
        if _evaluate_condition(step.get("condition"), responses):
            return step

    # If no conditional step matched at next_step_num, skip to the step after
    further = [s for s in candidates if s["step"] > next_step_num]
    further.sort(key=lambda s: s["step"])
    if not further:
        return None

    next_next_num = further[0]["step"]
    for step in further:
        if step["step"] != next_next_num:
            break
        if _evaluate_condition(step.get("condition"), responses):
            return step

    return None


def complete_intake(template: str, responses: Dict) -> Dict:
    """Process completed intake responses and return a summary.

    Returns a dict with:
      - summary: human-readable summary of the intake
      - client_data: normalized client fields for CRM creation
      - case_data: normalized case fields for case creation
    """
    # Extract standard client fields
    client_data = {
        "first_name": responses.get("first_name", ""),
        "last_name": responses.get("last_name", ""),
        "email": responses.get("email", ""),
        "phone": responses.get("phone", ""),
        "mailing_address": responses.get("address", ""),
        "date_of_birth": responses.get("date_of_birth", ""),
        "employer": responses.get("employer", ""),
        "referral_source": responses.get("how_heard", ""),
    }

    # Build case data based on template type
    case_data = {}
    if template == "criminal":
        case_data = {
            "case_type": "criminal",
            "charges": responses.get("charges", ""),
            "court_name": responses.get("court", ""),
            "docket_number": responses.get("case_number", ""),
        }
    elif template == "civil":
        case_data = {
            "case_type": "civil-plaintiff",
            "description": responses.get("dispute_summary", ""),
        }
    elif template == "family":
        case_data = {
            "case_type": "civil-plaintiff",
            "description": responses.get("family_matter_type", ""),
        }

    # Build human-readable summary
    name = f"{responses.get('first_name', '')} {responses.get('last_name', '')}".strip() or "Unknown"
    summary_parts = [f"Intake for {name} ({template} template)."]

    if template == "criminal":
        charges = responses.get("charges", "N/A")
        level = responses.get("charge_level", "unknown")
        summary_parts.append(f"Charge level: {level}.")
        summary_parts.append(f"Charges: {charges[:100]}{'...' if len(charges) > 100 else ''}.")
    elif template == "civil":
        civil_type = responses.get("civil_type", "general")
        opposing = responses.get("opposing_party", "N/A")
        summary_parts.append(f"Civil type: {civil_type}.")
        summary_parts.append(f"Opposing party: {opposing}.")
    elif template == "family":
        matter = responses.get("family_matter_type", "general")
        summary_parts.append(f"Family matter: {matter}.")

    return {
        "summary": " ".join(summary_parts),
        "client_data": client_data,
        "case_data": case_data,
        "all_responses": responses,
    }


def create_intake_session(template: str, client_id: str = "") -> Dict:
    """Start a new intake session. Returns session info with first step."""
    if template not in _INTAKE_STEPS:
        raise ValueError(f"Unknown intake template: {template}")

    session_id = f"intake_{uuid.uuid4().hex[:8]}"

    # Get the first step (step number 1, no condition)
    first_step = None
    for step in _INTAKE_STEPS[template]:
        if step["step"] == 1 and _evaluate_condition(step.get("condition"), {}):
            first_step = step
            break

    if not first_step:
        raise ValueError(f"No initial step found for template: {template}")

    _intake_sessions[session_id] = {
        "template": template,
        "current_step": 0,  # Will become 1 when we return the first step
        "responses": {},
        "client_id": client_id,
        "created_at": datetime.now().isoformat(),
    }

    return {
        "session_id": session_id,
        "template": template,
        "step": first_step,
        "total_steps": max(s["step"] for s in _INTAKE_STEPS[template]),
    }


def submit_intake_step(session_id: str, responses: Dict) -> Dict:
    """Submit responses for the current step and get the next step.

    Returns either the next step or a completion indicator.
    """
    session = _intake_sessions.get(session_id)
    if not session:
        raise ValueError(f"Intake session not found: {session_id}")

    # Merge new responses into accumulated responses
    session["responses"].update(responses)

    # Determine current step from session
    template = session["template"]
    current = session.get("current_step", 0)

    # If current_step is 0, we just submitted step 1
    # Find which step number was just submitted based on the responses
    steps = _INTAKE_STEPS.get(template, [])
    if current == 0:
        current = 1
    else:
        # current already tracks the step we just showed
        pass

    session["current_step"] = current

    # Get next step
    next_step = get_next_step(template, current, session["responses"])

    if next_step is None:
        # Intake is complete
        result = complete_intake(template, session["responses"])
        return {
            "complete": True,
            "summary": result["summary"],
            "client_data": result["client_data"],
            "case_data": result["case_data"],
        }

    # Update session to track the new current step
    session["current_step"] = next_step["step"]

    total_steps = max(s["step"] for s in steps)
    return {
        "complete": False,
        "step": next_step,
        "progress": next_step["step"],
        "total_steps": total_steps,
    }


def finalize_intake(session_id: str, create_case: bool = False) -> Dict:
    """Finalize an intake session.

    Saves intake answers to the client record and optionally creates a case.
    Returns client_id and case_id (if created).
    """
    session = _intake_sessions.get(session_id)
    if not session:
        raise ValueError(f"Intake session not found: {session_id}")

    template = session["template"]
    responses = session["responses"]
    result = complete_intake(template, responses)
    client_data = result["client_data"]
    case_data = result["case_data"]

    client_id = session.get("client_id", "")

    # Create or update client
    if client_id:
        # Update existing client with intake data
        update_client(client_id, {k: v for k, v in client_data.items() if v})
    else:
        # Create new client
        client_id = add_client(
            first_name=client_data.get("first_name", ""),
            last_name=client_data.get("last_name", ""),
            email=client_data.get("email", ""),
            phone=client_data.get("phone", ""),
            mailing_address=client_data.get("mailing_address", ""),
            referral_source=client_data.get("referral_source", ""),
            intake_status="prospective",
        )

    # Save intake answers
    save_intake_answers(client_id, template, responses)

    # Optionally create a case
    case_id = None
    if create_case and case_data:
        try:
            from core.case_manager import CaseManager
            from core.storage.json_backend import JSONStorageBackend
            import os

            data_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                os.pardir, "data",
            )
            # Try to use the same storage as the running app
            try:
                from api.deps import get_case_manager
                cm = get_case_manager()
            except Exception:
                storage = JSONStorageBackend(data_dir)
                cm = CaseManager(storage)

            client_name = f"{client_data.get('first_name', '')} {client_data.get('last_name', '')}".strip()
            case_name = f"{client_name} - {template.title()} Case"

            case_id = cm.create_case(
                case_name=case_name,
                case_type=case_data.get("case_type", "criminal"),
                description=case_data.get("description", ""),
                charges=case_data.get("charges", ""),
                court_name=case_data.get("court_name", ""),
                docket_number=case_data.get("docket_number", ""),
                client_name=client_name,
            )

            # Link client to case
            link_client_to_case(client_id, case_id)
        except Exception:
            logger.exception("Failed to auto-create case from intake")

    # Clean up session
    _intake_sessions.pop(session_id, None)

    return {
        "client_id": client_id,
        "case_id": case_id,
        "summary": result["summary"],
    }
