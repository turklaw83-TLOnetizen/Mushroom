"""
comms.py -- Automated Client Communication Engine
Queue-based communication system with AI drafting, trigger scanning,
template management, and full audit log.
Storage: data/comms/ (queue.json, templates.json, log.json, settings.json)
"""

import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# -- Paths -----------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_COMMS_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "comms")

_QUEUE_FILE = os.path.join(_COMMS_DIR, "queue.json")
_TEMPLATES_FILE = os.path.join(_COMMS_DIR, "templates.json")
_LOG_FILE = os.path.join(_COMMS_DIR, "log.json")
_SETTINGS_FILE = os.path.join(_COMMS_DIR, "settings.json")

TRIGGER_TYPES = [
    "payment_reminder", "payment_overdue", "court_prep",
    "status_update", "intake_followup", "phase_change",
    "payment_received", "morning_brief", "custom",
]
COMM_STATUSES = ["pending", "approved", "sent", "failed", "dismissed"]
PRIORITIES = ["low", "medium", "high", "critical"]
CHANNELS = ["email", "sms"]


def _ensure_dir():
    os.makedirs(_COMMS_DIR, exist_ok=True)


# ===================================================================
#  1.  QUEUE  — draft communications awaiting review
# ===================================================================

def _load_queue() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_QUEUE_FILE):
        with open(_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_queue(queue: List[Dict]):
    _ensure_dir()
    with open(_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def add_to_queue(
    client_id: str,
    trigger_type: str,
    subject: str,
    body_html: str,
    body_sms: str = "",
    case_id: str = "",
    trigger_id: str = "",
    channel: str = "email",
    priority: str = "medium",
    scheduled_for: str = "",
    metadata: Optional[Dict] = None,
) -> str:
    """Add a draft communication to the review queue. Returns comm_id."""
    queue = _load_queue()
    comm_id = f"comm_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": comm_id,
        "client_id": client_id,
        "case_id": case_id,
        "trigger_type": trigger_type,
        "trigger_id": trigger_id,
        "channel": channel,
        "subject": subject,
        "body_html": body_html,
        "body_sms": body_sms,
        "status": "pending",
        "priority": priority,
        "scheduled_for": scheduled_for or datetime.now().isoformat(),
        "created_at": datetime.now().isoformat(),
        "reviewed_at": None,
        "reviewed_by": None,
        "sent_at": None,
        "send_result": None,
        "dismissed_reason": "",
        "metadata": metadata or {},
    }
    queue.append(entry)
    _save_queue(queue)
    logger.info("Queued comm %s (%s) for client %s", comm_id, trigger_type, client_id)
    return comm_id


def get_queue(status_filter: str = "") -> List[Dict]:
    """List queue items, optionally filtered by status."""
    queue = _load_queue()
    if status_filter:
        queue = [q for q in queue if q["status"] == status_filter]
    return sorted(queue, key=lambda q: q.get("created_at", ""), reverse=True)


def get_queue_item(comm_id: str) -> Optional[Dict]:
    """Get a single queue item by ID."""
    for q in _load_queue():
        if q["id"] == comm_id:
            return q
    return None


def approve_comm(
    comm_id: str,
    reviewed_by: str,
    edited_body: Optional[str] = None,
    edited_sms: Optional[str] = None,
) -> bool:
    """Approve a communication. Optionally update the body text."""
    queue = _load_queue()
    for q in queue:
        if q["id"] == comm_id and q["status"] == "pending":
            q["status"] = "approved"
            q["reviewed_at"] = datetime.now().isoformat()
            q["reviewed_by"] = reviewed_by
            if edited_body is not None:
                q["body_html"] = edited_body
            if edited_sms is not None:
                q["body_sms"] = edited_sms
            _save_queue(queue)
            logger.info("Approved comm %s by %s", comm_id, reviewed_by)
            return True
    return False


def dismiss_comm(comm_id: str, reason: str, reviewed_by: str) -> bool:
    """Dismiss a communication with an optional reason."""
    queue = _load_queue()
    for q in queue:
        if q["id"] == comm_id and q["status"] == "pending":
            q["status"] = "dismissed"
            q["dismissed_reason"] = reason
            q["reviewed_at"] = datetime.now().isoformat()
            q["reviewed_by"] = reviewed_by
            _save_queue(queue)
            logger.info("Dismissed comm %s: %s", comm_id, reason)
            return True
    return False


def get_queue_stats() -> Dict:
    """Return counts by status."""
    queue = _load_queue()
    stats = {s: 0 for s in COMM_STATUSES}
    for q in queue:
        s = q.get("status", "pending")
        if s in stats:
            stats[s] += 1
    return stats


# ===================================================================
#  2.  TEMPLATES  — reusable communication templates
# ===================================================================

_DEFAULT_TEMPLATES: List[Dict] = [
    {
        "id": "tpl_pay_remind",
        "name": "Payment Reminder",
        "trigger_type": "payment_reminder",
        "channel": "email",
        "subject_template": "Payment Reminder - {{client_name}}",
        "body_template": (
            "Dear {{client_name}},\n\n"
            "This is a friendly reminder that your payment of ${{amount}} "
            "is due on {{due_date}}.\n\n"
            "Please let us know if you have any questions or need to "
            "make alternate arrangements.\n\n"
            "Sincerely,\n{{firm_name}}"
        ),
        "sms_template": (
            "Hi {{client_name}}, reminder: ${{amount}} payment due {{due_date}}. "
            "Questions? Call our office."
        ),
        "ai_enhance": True,
        "active": True,
        "created_at": "2026-03-05T00:00:00",
    },
    {
        "id": "tpl_pay_overdue",
        "name": "Payment Overdue",
        "trigger_type": "payment_overdue",
        "channel": "email",
        "subject_template": "Overdue Payment Notice - {{client_name}}",
        "body_template": (
            "Dear {{client_name}},\n\n"
            "Our records indicate that your payment of ${{amount}}, "
            "which was due on {{due_date}}, has not been received.\n\n"
            "Please remit payment at your earliest convenience or contact "
            "our office to discuss payment arrangements.\n\n"
            "Sincerely,\n{{firm_name}}"
        ),
        "sms_template": (
            "Hi {{client_name}}, your ${{amount}} payment was due {{due_date}} "
            "and is now overdue. Please contact our office."
        ),
        "ai_enhance": True,
        "active": True,
        "created_at": "2026-03-05T00:00:00",
    },
    {
        "id": "tpl_court_prep",
        "name": "Court Date Preparation",
        "trigger_type": "court_prep",
        "channel": "email",
        "subject_template": "Upcoming Court Date - {{event_title}}",
        "body_template": (
            "Dear {{client_name}},\n\n"
            "This is a reminder that you have an upcoming court date:\n\n"
            "Event: {{event_title}}\n"
            "Date: {{event_date}}\n"
            "Location: {{event_location}}\n\n"
            "Please plan to arrive at least 30 minutes early. "
            "Dress professionally and bring any documents we have discussed.\n\n"
            "If you have questions, please contact our office.\n\n"
            "Sincerely,\n{{firm_name}}"
        ),
        "sms_template": (
            "Hi {{client_name}}, court date reminder: {{event_title}} on "
            "{{event_date}}. Arrive 30 min early. Questions? Call us."
        ),
        "ai_enhance": True,
        "active": True,
        "created_at": "2026-03-05T00:00:00",
    },
    {
        "id": "tpl_intake_follow",
        "name": "Intake Follow-up",
        "trigger_type": "intake_followup",
        "channel": "email",
        "subject_template": "Following Up - {{firm_name}}",
        "body_template": (
            "Dear {{client_name}},\n\n"
            "Thank you for contacting our office. We wanted to follow up "
            "regarding your inquiry.\n\n"
            "If you are still in need of legal representation, we would be "
            "happy to schedule a consultation. Please call or reply to this "
            "email at your convenience.\n\n"
            "Sincerely,\n{{firm_name}}"
        ),
        "sms_template": (
            "Hi {{client_name}}, following up on your inquiry with {{firm_name}}. "
            "Still need help? Call or reply to schedule a consultation."
        ),
        "ai_enhance": False,
        "active": True,
        "created_at": "2026-03-05T00:00:00",
    },
    {
        "id": "tpl_pay_received",
        "name": "Payment Received — Thank You",
        "trigger_type": "payment_received",
        "channel": "email",
        "subject_template": "Payment Received — Thank You, {{client_name}}",
        "body_template": (
            "Dear {{client_name}},\n\n"
            "We have received your payment of ${{amount}}. "
            "Thank you for your prompt attention to this matter.\n\n"
            "If you have any questions about your account or upcoming "
            "payments, please do not hesitate to contact our office.\n\n"
            "Sincerely,\n{{firm_name}}"
        ),
        "sms_template": (
            "Hi {{client_name}}, we received your payment of ${{amount}}. "
            "Thank you! Questions? Call our office."
        ),
        "ai_enhance": False,
        "active": True,
        "created_at": "2026-03-05T00:00:00",
    },
]


def _load_templates() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_TEMPLATES_FILE):
        with open(_TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Seed with defaults on first run
    _save_templates(_DEFAULT_TEMPLATES)
    return list(_DEFAULT_TEMPLATES)


def _save_templates(templates: List[Dict]):
    _ensure_dir()
    with open(_TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)


def list_templates() -> List[Dict]:
    return _load_templates()


def get_template(template_id: str) -> Optional[Dict]:
    for t in _load_templates():
        if t["id"] == template_id:
            return t
    return None


def create_template(
    name: str,
    trigger_type: str,
    channel: str = "email",
    subject_template: str = "",
    body_template: str = "",
    sms_template: str = "",
    ai_enhance: bool = True,
) -> str:
    """Create a new template. Returns template ID."""
    templates = _load_templates()
    tpl_id = f"tpl_{uuid.uuid4().hex[:8]}"
    templates.append({
        "id": tpl_id,
        "name": name,
        "trigger_type": trigger_type,
        "channel": channel,
        "subject_template": subject_template,
        "body_template": body_template,
        "sms_template": sms_template,
        "ai_enhance": ai_enhance,
        "active": True,
        "created_at": datetime.now().isoformat(),
    })
    _save_templates(templates)
    return tpl_id


def update_template(template_id: str, updates: Dict) -> bool:
    templates = _load_templates()
    allowed = {"name", "subject_template", "body_template", "sms_template",
               "ai_enhance", "active", "trigger_type", "channel"}
    for t in templates:
        if t["id"] == template_id:
            for k, v in updates.items():
                if k in allowed:
                    t[k] = v
            t["updated_at"] = datetime.now().isoformat()
            _save_templates(templates)
            return True
    return False


def delete_template(template_id: str) -> bool:
    templates = _load_templates()
    before = len(templates)
    templates = [t for t in templates if t["id"] != template_id]
    if len(templates) < before:
        _save_templates(templates)
        return True
    return False


# ===================================================================
#  3.  COMMUNICATION LOG  — records of sent messages
# ===================================================================

def _load_log() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_log(log: List[Dict]):
    _ensure_dir()
    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def log_communication(
    comm_id: str,
    client_id: str,
    case_id: str,
    channel: str,
    subject: str,
    body: str,
    sent_to: str,
    trigger_type: str,
    approved_by: str,
) -> str:
    """Record a sent communication in the log. Returns log entry ID."""
    log = _load_log()
    log_id = f"log_{uuid.uuid4().hex[:8]}"
    log.append({
        "id": log_id,
        "comm_id": comm_id,
        "client_id": client_id,
        "case_id": case_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "sent_at": datetime.now().isoformat(),
        "sent_to": sent_to,
        "status": "delivered",
        "trigger_type": trigger_type,
        "approved_by": approved_by,
    })
    _save_log(log)
    return log_id


def get_client_comm_log(client_id: str) -> List[Dict]:
    """Return all communications for a client, newest first."""
    log = _load_log()
    return sorted(
        [e for e in log if e.get("client_id") == client_id],
        key=lambda e: e.get("sent_at", ""),
        reverse=True,
    )


def get_comm_log(limit: int = 50, client_id: str = "", case_id: str = "") -> List[Dict]:
    """Return communication log entries, optionally filtered."""
    log = _load_log()
    if client_id:
        log = [e for e in log if e.get("client_id") == client_id]
    if case_id:
        log = [e for e in log if e.get("case_id") == case_id]
    log.sort(key=lambda e: e.get("sent_at", ""), reverse=True)
    return log[:limit]


# ===================================================================
#  4.  SETTINGS  — trigger configuration
# ===================================================================

_DEFAULT_SETTINGS: Dict = {
    "triggers": {
        "payment_reminder": {
            "active": True,
            "days_before": [7, 3, 1],
            "channels": ["email", "sms"],
        },
        "payment_overdue": {
            "active": True,
            "days_after": [1, 3, 7, 14],
            "channels": ["email", "sms"],
        },
        "court_prep": {
            "active": True,
            "use_event_reminder_days": True,
            "channels": ["email"],
        },
        "phase_change": {
            "active": True,
            "channels": ["email"],
        },
        "intake_followup": {
            "active": True,
            "days_after_intake": [3, 7],
            "channels": ["email"],
        },
    },
    "firm_name": "",
    "default_sender_name": "Legal Team",
    "updated_at": None,
}


def _load_settings() -> Dict:
    _ensure_dir()
    if os.path.exists(_SETTINGS_FILE):
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Merge defaults for any missing keys
        merged = dict(_DEFAULT_SETTINGS)
        merged.update(saved)
        if "triggers" in saved:
            for k, v in _DEFAULT_SETTINGS["triggers"].items():
                if k not in saved["triggers"]:
                    merged["triggers"][k] = v
        return merged
    return dict(_DEFAULT_SETTINGS)


def _save_settings(settings: Dict):
    _ensure_dir()
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_comm_settings() -> Dict:
    return _load_settings()


def update_comm_settings(updates: Dict) -> Dict:
    settings = _load_settings()
    allowed_top = {"firm_name", "default_sender_name", "triggers"}
    for k, v in updates.items():
        if k in allowed_top:
            if k == "triggers" and isinstance(v, dict):
                settings["triggers"].update(v)
            else:
                settings[k] = v
    settings["updated_at"] = datetime.now().isoformat()
    _save_settings(settings)
    return settings


# ===================================================================
#  5.  AI DRAFT GENERATION
# ===================================================================

def _fill_template(template_text: str, context: Dict) -> str:
    """Simple {{variable}} substitution."""
    result = template_text
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value) if value else "")
    return result


def generate_ai_draft(template: Dict, context: Dict) -> Dict:
    """
    Generate a personalized communication using LLM.
    Falls back to simple template substitution if LLM is unavailable.
    Returns {subject, body_html, body_sms}.
    """
    # Simple substitution first (always available)
    subject = _fill_template(template.get("subject_template", ""), context)
    body = _fill_template(template.get("body_template", ""), context)
    sms = _fill_template(template.get("sms_template", ""), context)

    if not template.get("ai_enhance", False):
        return {"subject": subject, "body_html": body, "body_sms": sms}

    # Try AI enhancement
    try:
        from core.llm import get_llm, invoke_with_retry

        llm = get_llm(max_output_tokens=2048)
        if not llm:
            logger.warning("No LLM available for AI draft — using template substitution")
            return {"subject": subject, "body_html": body, "body_sms": sms}

        ctx_summary = "\n".join(f"- {k}: {v}" for k, v in context.items() if v)

        system_msg = (
            "You are a legal office communication assistant. "
            "Draft a professional, warm, and concise client communication. "
            "The tone should be professional but approachable. "
            "Keep the email body to 2-3 short paragraphs. "
            "Keep the SMS under 160 characters. "
            "Do not include legal advice or case strategy. "
            "Output ONLY valid JSON with keys: subject, body_html, body_sms"
        )

        user_msg = (
            f"Personalize this communication template for the client.\n\n"
            f"Template type: {template.get('trigger_type', 'general')}\n"
            f"Template name: {template.get('name', '')}\n\n"
            f"Base template (email):\n{body}\n\n"
            f"Base template (SMS):\n{sms}\n\n"
            f"Context:\n{ctx_summary}\n\n"
            f"Generate a personalized version. Return JSON only."
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        response = invoke_with_retry(llm, [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg),
        ])

        # Parse LLM JSON response
        text = response.content.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        return {
            "subject": result.get("subject", subject),
            "body_html": result.get("body_html", body),
            "body_sms": result.get("body_sms", sms),
        }

    except Exception:
        logger.exception("AI draft generation failed — using template substitution")
        return {"subject": subject, "body_html": body, "body_sms": sms}


# ===================================================================
#  6.  TRIGGER SCANNER  — checks conditions and generates drafts
# ===================================================================

def scan_triggers() -> int:
    """
    Scan all trigger conditions and generate draft communications.
    Returns count of new drafts created.

    Checks:
    1. Payment reminders (X days before due date)
    2. Payment overdue (X days after due date)
    3. Court prep / calendar events (reminder_days before event)
    4. Intake follow-ups (X days after intake for prospective clients)
    """
    settings = _load_settings()
    queue = _load_queue()
    today = date.today()

    # Build set of existing trigger keys to prevent duplicates
    existing = {
        (q["trigger_type"], q.get("trigger_id", ""), q["client_id"])
        for q in queue
        if q["status"] in ("pending", "approved", "sent")
    }

    count = 0
    firm_name = settings.get("firm_name", "Our Firm")

    # ---- 1. Payment Reminders ----
    pay_remind = settings["triggers"].get("payment_reminder", {})
    pay_overdue = settings["triggers"].get("payment_overdue", {})

    if pay_remind.get("active") or pay_overdue.get("active"):
        try:
            from core.billing import load_payment_plans
            from core.crm import _load_all as load_all_clients

            clients = load_all_clients()
            days_before = pay_remind.get("days_before", [7, 3, 1])
            days_after = pay_overdue.get("days_after", [1, 3, 7, 14])

            for client in clients:
                client_id = client.get("id", "")
                if not client_id:
                    continue

                plans = load_payment_plans(client_id)
                for plan in plans:
                    if plan.get("status") != "active":
                        continue

                    for sp in plan.get("scheduled_payments", []):
                        if sp["status"] in ("paid", "waived"):
                            continue

                        try:
                            due = datetime.strptime(sp["due_date"], "%Y-%m-%d").date()
                        except (ValueError, KeyError):
                            continue

                        days_until = (due - today).days
                        trigger_id = f"{plan['id']}_{sp['id']}"
                        client_name = client.get("name", "Client")
                        client_email = client.get("email", "")

                        # Payment reminder (upcoming)
                        if (pay_remind.get("active")
                                and days_until >= 0
                                and days_until in days_before):
                            key = ("payment_reminder", f"{trigger_id}_d{days_until}", client_id)
                            if key not in existing:
                                template = _find_template("payment_reminder")
                                ctx = {
                                    "client_name": client_name,
                                    "amount": f"{sp['amount']:,.2f}",
                                    "due_date": sp["due_date"],
                                    "firm_name": firm_name,
                                    "case_name": plan.get("client_name", ""),
                                }
                                draft = generate_ai_draft(template, ctx) if template else {
                                    "subject": f"Payment Reminder - {client_name}",
                                    "body_html": f"Reminder: ${sp['amount']:,.2f} due {sp['due_date']}",
                                    "body_sms": f"Reminder: ${sp['amount']:,.2f} due {sp['due_date']}",
                                }
                                add_to_queue(
                                    client_id=client_id,
                                    trigger_type="payment_reminder",
                                    subject=draft["subject"],
                                    body_html=draft["body_html"],
                                    body_sms=draft["body_sms"],
                                    trigger_id=f"{trigger_id}_d{days_until}",
                                    priority="medium" if days_until > 1 else "high",
                                    metadata={
                                        "client_name": client_name,
                                        "client_email": client_email,
                                        "client_phone": client.get("phone", ""),
                                        "amount_due": sp["amount"],
                                        "due_date": sp["due_date"],
                                    },
                                )
                                existing.add(key)
                                count += 1

                        # Payment overdue
                        if (pay_overdue.get("active")
                                and days_until < 0
                                and abs(days_until) in days_after):
                            key = ("payment_overdue", f"{trigger_id}_d{abs(days_until)}", client_id)
                            if key not in existing:
                                template = _find_template("payment_overdue")
                                ctx = {
                                    "client_name": client_name,
                                    "amount": f"{sp['amount'] - sp.get('paid_amount', 0):,.2f}",
                                    "due_date": sp["due_date"],
                                    "firm_name": firm_name,
                                }
                                draft = generate_ai_draft(template, ctx) if template else {
                                    "subject": f"Overdue Payment - {client_name}",
                                    "body_html": f"Payment of ${sp['amount']:,.2f} was due {sp['due_date']}",
                                    "body_sms": f"Payment overdue since {sp['due_date']}. Please contact us.",
                                }
                                add_to_queue(
                                    client_id=client_id,
                                    trigger_type="payment_overdue",
                                    subject=draft["subject"],
                                    body_html=draft["body_html"],
                                    body_sms=draft["body_sms"],
                                    trigger_id=f"{trigger_id}_d{abs(days_until)}",
                                    priority="high" if abs(days_until) > 7 else "critical",
                                    metadata={
                                        "client_name": client_name,
                                        "client_email": client_email,
                                        "client_phone": client.get("phone", ""),
                                        "amount_due": sp["amount"] - sp.get("paid_amount", 0),
                                        "due_date": sp["due_date"],
                                    },
                                )
                                existing.add(key)
                                count += 1

        except Exception:
            logger.exception("Error scanning payment triggers")

    # ---- 2. Court Prep / Calendar Events ----
    court_prep = settings["triggers"].get("court_prep", {})
    if court_prep.get("active"):
        try:
            from core.calendar_events import get_upcoming_events
            from core.crm import _load_all as load_all_clients

            events = get_upcoming_events(days=30)
            clients = load_all_clients()
            client_by_case = {}
            for c in clients:
                for cid in c.get("cases", c.get("linked_case_ids", [])):
                    client_by_case[cid] = c

            for event in events:
                case_id = event.get("case_id", "")
                client = client_by_case.get(case_id)
                if not client:
                    continue

                client_id = client.get("id", "")
                client_email = client.get("email", "")
                if not client_email:
                    continue

                # Calculate days until event
                try:
                    event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    continue

                days_until = (event_date - today).days
                reminder_days = event.get("reminder_days", [7, 1])
                if not isinstance(reminder_days, list):
                    reminder_days = [7, 1]

                if days_until in reminder_days:
                    key = ("court_prep", f"{event['id']}_d{days_until}", client_id)
                    if key not in existing:
                        template = _find_template("court_prep")
                        ctx = {
                            "client_name": client.get("name", "Client"),
                            "event_title": event.get("title", "Court Date"),
                            "event_date": event["date"],
                            "event_location": event.get("location", "TBD"),
                            "firm_name": firm_name,
                        }
                        draft = generate_ai_draft(template, ctx) if template else {
                            "subject": f"Court Date: {event.get('title', '')} - {event['date']}",
                            "body_html": f"Reminder: {event.get('title', '')} on {event['date']}",
                            "body_sms": f"Court date: {event.get('title', '')} on {event['date']}",
                        }
                        add_to_queue(
                            client_id=client_id,
                            case_id=case_id,
                            trigger_type="court_prep",
                            subject=draft["subject"],
                            body_html=draft["body_html"],
                            body_sms=draft["body_sms"],
                            trigger_id=f"{event['id']}_d{days_until}",
                            priority="high" if days_until <= 1 else "medium",
                            metadata={
                                "client_name": client.get("name", ""),
                                "client_email": client_email,
                                "client_phone": client.get("phone", ""),
                                "case_name": event.get("case_name", ""),
                                "event_title": event.get("title", ""),
                            },
                        )
                        existing.add(key)
                        count += 1

        except Exception:
            logger.exception("Error scanning court prep triggers")

    # ---- 3. Intake Follow-ups ----
    intake = settings["triggers"].get("intake_followup", {})
    if intake.get("active"):
        try:
            from core.crm import _load_all as load_all_clients

            clients = load_all_clients()
            days_after = intake.get("days_after_intake", [3, 7])

            for client in clients:
                if client.get("intake_status") != "prospective":
                    continue

                client_id = client.get("id", "")
                client_email = client.get("email", "")
                if not client_email:
                    continue

                created = client.get("created_at", "")
                if not created:
                    continue

                try:
                    intake_date = datetime.fromisoformat(created).date()
                except (ValueError, TypeError):
                    continue

                days_since = (today - intake_date).days
                if days_since in days_after:
                    key = ("intake_followup", f"day_{days_since}", client_id)
                    if key not in existing:
                        template = _find_template("intake_followup")
                        ctx = {
                            "client_name": client.get("name", "Client"),
                            "firm_name": firm_name,
                        }
                        draft = generate_ai_draft(template, ctx) if template else {
                            "subject": f"Following Up - {firm_name}",
                            "body_html": "Thank you for contacting us. We wanted to follow up.",
                            "body_sms": f"Following up on your inquiry. Call us: {firm_name}",
                        }
                        add_to_queue(
                            client_id=client_id,
                            trigger_type="intake_followup",
                            subject=draft["subject"],
                            body_html=draft["body_html"],
                            body_sms=draft["body_sms"],
                            trigger_id=f"day_{days_since}",
                            priority="low",
                            metadata={
                                "client_name": client.get("name", ""),
                                "client_email": client_email,
                                "client_phone": client.get("phone", ""),
                            },
                        )
                        existing.add(key)
                        count += 1

        except Exception:
            logger.exception("Error scanning intake follow-up triggers")

    logger.info("Trigger scan complete: %d new drafts created", count)
    return count


def _find_template(trigger_type: str) -> Optional[Dict]:
    """Find the first active template for a trigger type."""
    for t in _load_templates():
        if t.get("trigger_type") == trigger_type and t.get("active", True):
            return t
    return None


# ===================================================================
#  7.  SEND  — deliver approved communications
# ===================================================================

def send_approved_comms() -> Dict:
    """
    Send all approved communications via email.
    Returns {sent, failed, errors}.
    """
    from api.email_alerts import send_email

    queue = _load_queue()
    sent = 0
    failed = 0
    errors = []

    for q in queue:
        if q["status"] != "approved":
            continue

        to_email = q.get("metadata", {}).get("client_email", "")
        if not to_email:
            q["status"] = "failed"
            q["send_result"] = "No client email address"
            failed += 1
            errors.append(f"{q['id']}: No email address")
            continue

        success = send_email(to_email, q["subject"], q["body_html"])

        if success:
            q["status"] = "sent"
            q["sent_at"] = datetime.now().isoformat()
            q["send_result"] = "delivered"
            sent += 1

            # Log the communication
            log_communication(
                comm_id=q["id"],
                client_id=q["client_id"],
                case_id=q.get("case_id", ""),
                channel=q["channel"],
                subject=q["subject"],
                body=q["body_html"],
                sent_to=to_email,
                trigger_type=q["trigger_type"],
                approved_by=q.get("reviewed_by", ""),
            )
        else:
            q["status"] = "failed"
            q["send_result"] = "SMTP send failed"
            failed += 1
            errors.append(f"{q['id']}: SMTP send failed")

    _save_queue(queue)
    logger.info("Send complete: %d sent, %d failed", sent, failed)
    return {"sent": sent, "failed": failed, "errors": errors}
