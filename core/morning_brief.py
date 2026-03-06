"""
morning_brief.py -- Morning Brief: Daily Case Autopilot
========================================================
Aggregation engine that scans ALL active cases and produces a single
prioritized action list for the attorney's day.

Components:
  1. Cross-Case Daily Triage — unified priority queue across every case
  2. Proactive Detection — surfaces issues before they become problems
  3. Deadline Chain Calculator — downstream deadlines from a single event
  4. One-Click Actions — actionable metadata on every triage item
  5. Daily Email Digest — HTML-formatted summary for email delivery

Location-Aware Suggestions:
  Reads calendar entries for today, extracts physical locations, and
  cross-references pending tasks across ALL cases that could be
  completed at the same location.

Storage:
  data/morning_brief/dismissed.json — dismissed item IDs + timestamps
  data/morning_brief/snoozed.json   — snoozed items with reappear dates
"""

import json
import logging
import os
import re
import secrets
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")
_BRIEF_DIR = os.path.join(_DATA_DIR, "morning_brief")

# Severity ordering for sort (lower = more urgent)
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Source priority for tie-breaking within same severity + date
_SOURCE_PRIORITY = {
    "calendar": 0,
    "tasks": 1,
    "billing": 2,
    "notifications": 3,
    "comms": 4,
    "proactive": 5,
}

# Maximum triage items to prevent information overload
_MAX_TRIAGE_ITEMS = 50

# Jurisdictional deadline chains (days relative to triggering event)
# Positive = days after, Negative = days before
_DEADLINE_CHAINS = {
    "motion_filed": [
        {"offset": 0, "label": "Motion filed", "type": "filing"},
        {"offset": 14, "label": "Opposition due", "type": "deadline"},
        {"offset": 21, "label": "Reply brief due", "type": "deadline"},
        {"offset": 30, "label": "Hearing date (estimated)", "type": "court_date"},
    ],
    "motion_to_suppress": [
        {"offset": 0, "label": "Motion to Suppress filed", "type": "filing"},
        {"offset": 14, "label": "State's response due", "type": "deadline"},
        {"offset": 21, "label": "Reply brief due", "type": "deadline"},
        {"offset": 30, "label": "Suppression hearing", "type": "court_date"},
    ],
    "discovery_request": [
        {"offset": 0, "label": "Discovery request served", "type": "filing"},
        {"offset": 30, "label": "Discovery responses due", "type": "deadline"},
        {"offset": 37, "label": "Meet and confer deadline (if deficient)", "type": "deadline"},
        {"offset": 45, "label": "Motion to compel deadline", "type": "deadline"},
    ],
    "deposition_noticed": [
        {"offset": 0, "label": "Deposition notice served", "type": "filing"},
        {"offset": -7, "label": "Prepare witness outline", "type": "task"},
        {"offset": -3, "label": "Witness prep session", "type": "task"},
        {"offset": 0, "label": "Deposition date", "type": "deposition"},
        {"offset": 30, "label": "Transcript review deadline", "type": "deadline"},
    ],
    "trial_date_set": [
        {"offset": 0, "label": "Trial date set", "type": "court_date"},
        {"offset": -60, "label": "Expert disclosures due", "type": "deadline"},
        {"offset": -45, "label": "Dispositive motions deadline", "type": "deadline"},
        {"offset": -30, "label": "Pretrial motions in limine due", "type": "deadline"},
        {"offset": -21, "label": "Exhibit and witness lists due", "type": "deadline"},
        {"offset": -14, "label": "Pretrial conference", "type": "court_date"},
        {"offset": -7, "label": "Jury instructions due", "type": "deadline"},
        {"offset": -3, "label": "Final witness prep", "type": "task"},
    ],
    "complaint_filed": [
        {"offset": 0, "label": "Complaint filed/served", "type": "filing"},
        {"offset": 21, "label": "Answer/responsive pleading due", "type": "deadline"},
        {"offset": 30, "label": "Initial disclosures due", "type": "deadline"},
        {"offset": 45, "label": "Scheduling conference", "type": "court_date"},
    ],
    "appeal_filed": [
        {"offset": 0, "label": "Notice of appeal filed", "type": "filing"},
        {"offset": 10, "label": "Transcript order deadline", "type": "deadline"},
        {"offset": 40, "label": "Appellant's brief due", "type": "deadline"},
        {"offset": 70, "label": "Appellee's brief due", "type": "deadline"},
        {"offset": 84, "label": "Reply brief due", "type": "deadline"},
    ],
}


def _ensure_brief_dir():
    """Create the morning_brief data directory if it does not exist."""
    os.makedirs(_BRIEF_DIR, exist_ok=True)


# ===================================================================
#  DISMISSED / SNOOZED PERSISTENCE
# ===================================================================

def _load_dismissed(data_dir: str = "") -> Dict[str, str]:
    """Load dismissed item IDs.  Returns {item_id: dismissed_at_iso}."""
    d = data_dir or _DATA_DIR
    path = os.path.join(d, "morning_brief", "dismissed.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_dismissed(dismissed: Dict[str, str], data_dir: str = ""):
    d = data_dir or _DATA_DIR
    brief_dir = os.path.join(d, "morning_brief")
    os.makedirs(brief_dir, exist_ok=True)
    path = os.path.join(brief_dir, "dismissed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dismissed, f, indent=2, default=str)


def _load_snoozed(data_dir: str = "") -> List[Dict]:
    """Load snoozed items.  Returns [{item_id, snoozed_until}, ...]."""
    d = data_dir or _DATA_DIR
    path = os.path.join(d, "morning_brief", "snoozed.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_snoozed(snoozed: List[Dict], data_dir: str = ""):
    d = data_dir or _DATA_DIR
    brief_dir = os.path.join(d, "morning_brief")
    os.makedirs(brief_dir, exist_ok=True)
    path = os.path.join(brief_dir, "snoozed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snoozed, f, indent=2, default=str)


def _get_suppressed_ids(data_dir: str = "") -> set:
    """Return item IDs that should be excluded (dismissed <24h ago or snoozed)."""
    suppressed = set()
    now = datetime.now()

    # Dismissed items: suppress for 24 hours
    dismissed = _load_dismissed(data_dir)
    for item_id, dismissed_at in dismissed.items():
        try:
            dt = datetime.fromisoformat(dismissed_at)
            if (now - dt).total_seconds() < 86400:
                suppressed.add(item_id)
        except (ValueError, TypeError):
            pass

    # Snoozed items: suppress until snoozed_until date
    snoozed = _load_snoozed(data_dir)
    today_str = str(date.today())
    for entry in snoozed:
        if entry.get("snoozed_until", "") > today_str:
            suppressed.add(entry.get("item_id", ""))

    return suppressed


# ===================================================================
#  PUBLIC API: dismiss / snooze
# ===================================================================

def dismiss_brief_item(data_dir: str, item_id: str) -> bool:
    """Mark a brief item as dismissed.  Dismissed items don't reappear for 24 hours.

    Args:
        data_dir: Path to the data directory.
        item_id: The brief item ID to dismiss (e.g. "brief_a1b2c3d4").

    Returns:
        True if the item was recorded as dismissed.
    """
    if not item_id:
        return False
    d = data_dir or _DATA_DIR
    dismissed = _load_dismissed(d)
    dismissed[item_id] = datetime.now().isoformat()
    _save_dismissed(dismissed, d)
    logger.info("Dismissed morning brief item: %s", item_id)
    return True


def snooze_brief_item(data_dir: str, item_id: str, days: int = 3) -> bool:
    """Snooze a brief item so it reappears after the snooze period.

    Args:
        data_dir: Path to the data directory.
        item_id: The brief item ID to snooze.
        days: Number of days to snooze (default 3).

    Returns:
        True if the item was snoozed.
    """
    if not item_id or days < 1:
        return False
    d = data_dir or _DATA_DIR
    snoozed = _load_snoozed(d)
    snoozed_until = str(date.today() + timedelta(days=days))

    # Update existing or append
    found = False
    for entry in snoozed:
        if entry.get("item_id") == item_id:
            entry["snoozed_until"] = snoozed_until
            found = True
            break
    if not found:
        snoozed.append({"item_id": item_id, "snoozed_until": snoozed_until})

    _save_snoozed(snoozed, d)
    logger.info("Snoozed morning brief item %s until %s", item_id, snoozed_until)
    return True


# ===================================================================
#  COMPONENT 3: Deadline Chain Calculator
# ===================================================================

def calculate_deadline_chain(
    event_type: str,
    event_date: str,
    case_id: str = "",
    case_name: str = "",
    custom_label: str = "",
) -> List[Dict]:
    """Calculate the full downstream deadline chain from a triggering event.

    Given a single event (e.g. "Motion to Suppress filed March 10"),
    generates every downstream deadline based on jurisdictional rules.

    Args:
        event_type: One of the keys in _DEADLINE_CHAINS (e.g. "motion_filed",
                    "trial_date_set", "discovery_request").
        event_date: The date of the triggering event, YYYY-MM-DD.
        case_id: Optional case ID for linking.
        case_name: Optional case name for display.
        custom_label: Optional custom label for the triggering event.

    Returns:
        List of deadline dicts with fields:
            date, label, type, case_id, case_name, days_from_trigger
    """
    chain_template = _DEADLINE_CHAINS.get(event_type, [])
    if not chain_template:
        logger.warning("Unknown deadline chain type: %s", event_type)
        return []

    try:
        base_date = date.fromisoformat(event_date)
    except (ValueError, TypeError):
        logger.warning("Invalid event_date for deadline chain: %s", event_date)
        return []

    chain = []
    for step in chain_template:
        offset = step["offset"]
        target_date = base_date + timedelta(days=offset)
        label = step["label"]
        if offset == 0 and custom_label:
            label = custom_label

        chain.append({
            "date": str(target_date),
            "label": label,
            "type": step["type"],
            "case_id": case_id,
            "case_name": case_name,
            "days_from_trigger": offset,
        })

    chain.sort(key=lambda x: x["date"])
    return chain


# ===================================================================
#  ITEM ID GENERATOR
# ===================================================================

def _make_item_id() -> str:
    """Generate a unique triage item ID."""
    return f"brief_{secrets.token_hex(4)}"


# ===================================================================
#  COMPONENT 1 + 4: Cross-Case Triage + One-Click Actions
# ===================================================================

def _collect_triage_items(
    case_mgr,
    data_dir: str,
    user_id: str,
    target_date: str,
) -> List[Dict]:
    """Collect triage items from all data sources and assign severity + actions.

    Sources:
        - Calendar events for today and approaching
        - Overdue and upcoming tasks
        - Deadlines from case manager
        - Low/exhausted retainer balances
        - Pending communications
        - Notifications (overdue deadlines, etc.)
        - Proactive issue detection

    Each item includes an ``action`` dict with one-click metadata and
    optional ``secondary_actions``.
    """
    _dir = data_dir or _DATA_DIR
    target = target_date or str(date.today())
    items: List[Dict] = []

    # Resolve all active cases once
    try:
        all_cases = case_mgr.list_cases(include_archived=False)
    except Exception:
        logger.exception("Failed to list cases for morning brief")
        all_cases = []

    case_ids = [c.get("id", "") for c in all_cases if c.get("id")]

    # Helper to safely get case name
    def _case_name(cid: str) -> str:
        try:
            return case_mgr.get_case_name(cid) or cid
        except Exception:
            return cid

    # ---- 1. Calendar events for today ----
    try:
        from core.calendar_events import get_events_for_date, get_upcoming_events

        today_events = get_events_for_date(target)
        for ev in today_events:
            severity = "high"
            if ev.get("event_type") in ("Court Date", "Filing Deadline"):
                severity = "critical"

            items.append({
                "id": _make_item_id(),
                "type": "court_date" if ev.get("event_type") in ("Court Date", "Deposition") else "deadline",
                "title": ev.get("title", "Event today"),
                "detail": f"{ev.get('time', '')} at {ev.get('location', 'TBD')}".strip(),
                "case_id": ev.get("case_id", ""),
                "case_name": _case_name(ev.get("case_id", "")),
                "severity": severity,
                "due_date": target,
                "action": {
                    "type": "navigate",
                    "label": "View Event",
                    "endpoint": f"/api/v1/calendar/events/{ev.get('id', '')}",
                    "method": "GET",
                    "params": {"event_id": ev.get("id", "")},
                },
                "secondary_actions": [
                    {"type": "snooze", "label": "Snooze 3 days"},
                    {"type": "dismiss", "label": "Dismiss"},
                ],
                "source": "calendar",
                "timestamp": ev.get("time", ""),
            })

        # Upcoming events in next 3 days (excluding today, already covered)
        upcoming = get_upcoming_events(days=3)
        for ev in upcoming:
            if ev.get("date", "") == target:
                continue
            sev = "medium"
            if ev.get("event_type") in ("Court Date", "Filing Deadline"):
                sev = "high"

            items.append({
                "id": _make_item_id(),
                "type": "court_date" if ev.get("event_type") == "Court Date" else "deadline",
                "title": f"Upcoming: {ev.get('title', 'Event')}",
                "detail": f"{ev.get('date', '')} {ev.get('time', '')} — {ev.get('location', '')}".strip(),
                "case_id": ev.get("case_id", ""),
                "case_name": _case_name(ev.get("case_id", "")),
                "severity": sev,
                "due_date": ev.get("date", ""),
                "action": {
                    "type": "navigate",
                    "label": "View Event",
                    "endpoint": f"/api/v1/calendar/events/{ev.get('id', '')}",
                    "method": "GET",
                    "params": {"event_id": ev.get("id", "")},
                },
                "secondary_actions": [
                    {"type": "snooze", "label": "Snooze 3 days"},
                    {"type": "dismiss", "label": "Dismiss"},
                ],
                "source": "calendar",
                "timestamp": ev.get("date", ""),
            })
    except Exception:
        logger.exception("Morning brief: calendar source failed")

    # ---- 2. Overdue tasks ----
    try:
        from core.tasks import get_overdue_tasks

        overdue = get_overdue_tasks(_dir)
        for t in overdue:
            cid = t.get("case_id", "")
            if cid and cid not in case_ids:
                continue
            if user_id and t.get("assigned_to") and t.get("assigned_to") != user_id:
                continue

            days_overdue = 0
            try:
                due_dt = date.fromisoformat(t.get("due_date", ""))
                days_overdue = (date.fromisoformat(target) - due_dt).days
            except (ValueError, TypeError):
                pass

            severity = "critical" if days_overdue > 7 else "high"

            items.append({
                "id": _make_item_id(),
                "type": "overdue_task",
                "title": f"Overdue: {t.get('title', 'Task')}",
                "detail": f"Due {t.get('due_date', '?')} ({days_overdue}d overdue) — {t.get('priority', 'medium')} priority",
                "case_id": cid,
                "case_name": _case_name(cid),
                "severity": severity,
                "due_date": t.get("due_date", ""),
                "action": {
                    "type": "navigate",
                    "label": "View Task",
                    "endpoint": f"/api/v1/cases/{cid}/tasks/{t.get('id', '')}",
                    "method": "GET",
                    "params": {"case_id": cid, "task_id": t.get("id", "")},
                },
                "secondary_actions": [
                    {"type": "snooze", "label": "Snooze 3 days"},
                    {"type": "dismiss", "label": "Dismiss"},
                ],
                "source": "tasks",
                "timestamp": t.get("due_date", ""),
            })
    except Exception:
        logger.exception("Morning brief: overdue tasks source failed")

    # ---- 3. Deadlines from case manager ----
    try:
        all_deadlines = case_mgr.get_all_deadlines()
        for dl in all_deadlines:
            days_rem = dl.get("days_remaining", 999)
            # Only include deadlines within 7 days or overdue
            if days_rem > 7:
                continue

            if days_rem < 0:
                severity = "critical"
                prefix = "OVERDUE"
            elif days_rem == 0:
                severity = "critical"
                prefix = "TODAY"
            elif days_rem <= 2:
                severity = "high"
                prefix = f"In {days_rem} day{'s' if days_rem != 1 else ''}"
            else:
                severity = "medium"
                prefix = f"In {days_rem} days"

            cid = dl.get("case_id", "")
            items.append({
                "id": _make_item_id(),
                "type": "deadline",
                "title": f"{prefix}: {dl.get('label', 'Deadline')}",
                "detail": dl.get("_case_name", "") or _case_name(cid),
                "case_id": cid,
                "case_name": dl.get("_case_name", "") or _case_name(cid),
                "severity": severity,
                "due_date": dl.get("date", ""),
                "action": {
                    "type": "navigate",
                    "label": "View Case",
                    "endpoint": f"/api/v1/cases/{cid}",
                    "method": "GET",
                    "params": {"case_id": cid},
                },
                "secondary_actions": [
                    {"type": "create_task", "label": "Create Task",
                     "endpoint": f"/api/v1/cases/{cid}/tasks",
                     "method": "POST",
                     "params": {"case_id": cid, "title": dl.get("label", "Handle deadline")}},
                    {"type": "snooze", "label": "Snooze 3 days"},
                    {"type": "dismiss", "label": "Dismiss"},
                ],
                "source": "notifications",
                "timestamp": dl.get("date", ""),
            })
    except Exception:
        logger.exception("Morning brief: deadlines source failed")

    # ---- 4. Retainer balances ----
    try:
        from core.billing import get_retainer_balance, load_retainer_history

        for cid in case_ids[:50]:  # cap to prevent slow scanning
            history = load_retainer_history(cid)
            if not history:
                continue
            balance = get_retainer_balance(cid)
            cn = _case_name(cid)

            if balance <= 0:
                items.append({
                    "id": _make_item_id(),
                    "type": "retainer_low",
                    "title": "Retainer exhausted",
                    "detail": f"Balance: $0.00 — {cn}",
                    "case_id": cid,
                    "case_name": cn,
                    "severity": "high",
                    "due_date": target,
                    "action": {
                        "type": "send_comm",
                        "label": "Send Payment Reminder",
                        "endpoint": "/api/v1/comms/queue",
                        "method": "POST",
                        "params": {"case_id": cid, "trigger_type": "payment_reminder"},
                    },
                    "secondary_actions": [
                        {"type": "navigate", "label": "View Billing",
                         "endpoint": f"/api/v1/cases/{cid}/billing", "method": "GET"},
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "billing",
                    "timestamp": "",
                })
            elif balance < 500:
                items.append({
                    "id": _make_item_id(),
                    "type": "retainer_low",
                    "title": f"Low retainer: ${balance:,.2f}",
                    "detail": cn,
                    "case_id": cid,
                    "case_name": cn,
                    "severity": "medium",
                    "due_date": "",
                    "action": {
                        "type": "send_comm",
                        "label": "Send Payment Reminder",
                        "endpoint": "/api/v1/comms/queue",
                        "method": "POST",
                        "params": {"case_id": cid, "trigger_type": "payment_reminder"},
                    },
                    "secondary_actions": [
                        {"type": "navigate", "label": "View Billing",
                         "endpoint": f"/api/v1/cases/{cid}/billing", "method": "GET"},
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "billing",
                    "timestamp": "",
                })
    except Exception:
        logger.exception("Morning brief: retainer source failed")

    # ---- 5. Pending communications ----
    try:
        from core.comms import get_queue

        pending_comms = get_queue(status_filter="pending")
        for comm in pending_comms[:20]:  # cap
            items.append({
                "id": _make_item_id(),
                "type": "comm_pending",
                "title": f"Review: {comm.get('subject', 'Communication')}",
                "detail": f"{comm.get('trigger_type', '')} — {comm.get('channel', 'email')}",
                "case_id": comm.get("case_id", ""),
                "case_name": _case_name(comm.get("case_id", "")),
                "severity": "medium" if comm.get("priority") != "critical" else "high",
                "due_date": "",
                "action": {
                    "type": "navigate",
                    "label": "Review & Approve",
                    "endpoint": f"/api/v1/comms/queue/{comm.get('id', '')}",
                    "method": "GET",
                    "params": {"comm_id": comm.get("id", "")},
                },
                "secondary_actions": [
                    {"type": "dismiss", "label": "Dismiss Comm",
                     "endpoint": f"/api/v1/comms/queue/{comm.get('id', '')}/dismiss",
                     "method": "POST"},
                ],
                "source": "comms",
                "timestamp": comm.get("created_at", ""),
            })
    except Exception:
        logger.exception("Morning brief: comms source failed")

    # ---- 6. Proactive issues ----
    try:
        proactive = _detect_proactive_issues(case_mgr, _dir)
        items.extend(proactive)
    except Exception:
        logger.exception("Morning brief: proactive detection failed")

    return items


# ===================================================================
#  COMPONENT 2: Proactive Detection
# ===================================================================

def _detect_proactive_issues(case_mgr, data_dir: str) -> List[Dict]:
    """Detect issues before they become problems.

    Checks:
        - Retainer balances that dropped >50% in last 30 days (burn rate)
        - Cases with no activity in 14+ days
        - Upcoming deadlines with no assigned tasks
        - Payment plans with health "at_risk" or "behind"
    """
    _dir = data_dir or _DATA_DIR
    issues: List[Dict] = []
    today_str = str(date.today())

    try:
        all_cases = case_mgr.list_cases(include_archived=False)
    except Exception:
        return issues

    # Helper to safely get case name
    def _case_name(cid: str) -> str:
        try:
            return case_mgr.get_case_name(cid) or cid
        except Exception:
            return cid

    # ---- Retainer burn rate ----
    try:
        from core.billing import get_retainer_balance, load_retainer_history

        for case in all_cases[:50]:
            cid = case.get("id", "")
            history = load_retainer_history(cid)
            if len(history) < 2:
                continue

            current_balance = get_retainer_balance(cid)

            # Look at deposits from 30+ days ago to estimate previous balance
            thirty_days_ago = str(date.today() - timedelta(days=30))
            old_balance = 0.0
            for entry in history:
                entry_date = entry.get("date", "")
                if entry_date and entry_date <= thirty_days_ago:
                    if entry.get("type") == "deposit":
                        old_balance += entry.get("amount", 0)
                    elif entry.get("type") == "draw":
                        old_balance -= entry.get("amount", 0)

            if old_balance > 0 and current_balance < old_balance * 0.5:
                cn = _case_name(cid)
                issues.append({
                    "id": _make_item_id(),
                    "type": "proactive",
                    "title": f"Retainer burning fast: {cn}",
                    "detail": (
                        f"Balance dropped from ~${old_balance:,.2f} to "
                        f"${current_balance:,.2f} in 30 days"
                    ),
                    "case_id": cid,
                    "case_name": cn,
                    "severity": "high",
                    "due_date": "",
                    "action": {
                        "type": "send_comm",
                        "label": "Send Retainer Replenishment Notice",
                        "endpoint": "/api/v1/comms/queue",
                        "method": "POST",
                        "params": {"case_id": cid, "trigger_type": "payment_reminder"},
                    },
                    "secondary_actions": [
                        {"type": "navigate", "label": "View Billing",
                         "endpoint": f"/api/v1/cases/{cid}/billing", "method": "GET"},
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "proactive",
                    "timestamp": "",
                })
    except Exception:
        logger.debug("Proactive: retainer burn rate check failed")

    # ---- Cases with no activity in 14+ days ----
    try:
        from core.tasks import load_tasks

        fourteen_days_ago = str(date.today() - timedelta(days=14))

        for case in all_cases:
            cid = case.get("id", "")
            # Check last task update
            tasks = load_tasks(_dir, cid)
            last_activity = case.get("updated_at", "") or case.get("created_at", "")

            for t in tasks:
                t_updated = t.get("updated_at", "") or t.get("created_at", "")
                if t_updated and t_updated > last_activity:
                    last_activity = t_updated

            if last_activity and last_activity[:10] < fourteen_days_ago:
                cn = _case_name(cid)
                days_inactive = (date.today() - date.fromisoformat(last_activity[:10])).days
                issues.append({
                    "id": _make_item_id(),
                    "type": "proactive",
                    "title": f"No activity in {days_inactive} days: {cn}",
                    "detail": f"Last activity: {last_activity[:10]}",
                    "case_id": cid,
                    "case_name": cn,
                    "severity": "medium",
                    "due_date": "",
                    "action": {
                        "type": "create_task",
                        "label": "Create Follow-up Task",
                        "endpoint": f"/api/v1/cases/{cid}/tasks",
                        "method": "POST",
                        "params": {"case_id": cid, "title": "Review case status", "priority": "medium"},
                    },
                    "secondary_actions": [
                        {"type": "navigate", "label": "Open Case",
                         "endpoint": f"/api/v1/cases/{cid}", "method": "GET"},
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "proactive",
                    "timestamp": last_activity,
                })
    except Exception:
        logger.debug("Proactive: case inactivity check failed")

    # ---- Deadlines with no assigned tasks ----
    try:
        from core.tasks import load_tasks

        all_deadlines = case_mgr.get_all_deadlines()
        for dl in all_deadlines:
            days_rem = dl.get("days_remaining", 999)
            if days_rem < 0 or days_rem > 14:
                continue

            cid = dl.get("case_id", "")
            if not cid:
                continue

            # Check if any active task references this deadline
            tasks = load_tasks(_dir, cid)
            active_tasks = [
                t for t in tasks
                if t.get("status") not in ("completed", "cancelled")
            ]

            dl_label = dl.get("label", "").lower()
            has_matching_task = any(
                dl_label in t.get("title", "").lower() or
                dl_label in t.get("description", "").lower()
                for t in active_tasks
            )

            if not has_matching_task and not active_tasks:
                cn = dl.get("_case_name", "") or _case_name(cid)
                issues.append({
                    "id": _make_item_id(),
                    "type": "proactive",
                    "title": f"Deadline with no task: {dl.get('label', 'Deadline')}",
                    "detail": f"{cn} — due in {days_rem} day{'s' if days_rem != 1 else ''}",
                    "case_id": cid,
                    "case_name": cn,
                    "severity": "high" if days_rem <= 3 else "medium",
                    "due_date": dl.get("date", ""),
                    "action": {
                        "type": "create_task",
                        "label": "Create Task for Deadline",
                        "endpoint": f"/api/v1/cases/{cid}/tasks",
                        "method": "POST",
                        "params": {
                            "case_id": cid,
                            "title": f"Handle: {dl.get('label', 'Deadline')}",
                            "due_date": dl.get("date", ""),
                            "priority": "high",
                        },
                    },
                    "secondary_actions": [
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "proactive",
                    "timestamp": dl.get("date", ""),
                })
    except Exception:
        logger.debug("Proactive: deadline-without-task check failed")

    # ---- Payment plans at risk or behind ----
    try:
        from core.billing import load_payment_plans, compute_plan_health
        from core.crm import load_clients

        clients = load_clients()
        for client in clients[:50]:
            client_id = client.get("id", "")
            if not client_id:
                continue

            plans = load_payment_plans(client_id)
            for plan in plans:
                if plan.get("status") != "active":
                    continue

                health = compute_plan_health(plan)
                if health not in ("at_risk", "behind"):
                    continue

                # Find linked case
                plan_case_id = ""
                plan_case_name = client.get("name", "Client")
                linked = client.get("linked_case_ids", [])
                if linked:
                    plan_case_id = linked[0]
                    plan_case_name = _case_name(plan_case_id)

                severity = "high" if health == "at_risk" else "medium"
                label = "At Risk" if health == "at_risk" else "Behind"

                issues.append({
                    "id": _make_item_id(),
                    "type": "payment_due",
                    "title": f"Payment plan {label}: {client.get('name', 'Client')}",
                    "detail": f"Plan ID {plan.get('id', '?')} — {plan_case_name}",
                    "case_id": plan_case_id,
                    "case_name": plan_case_name,
                    "severity": severity,
                    "due_date": "",
                    "action": {
                        "type": "send_comm",
                        "label": "Send Payment Reminder",
                        "endpoint": "/api/v1/comms/queue",
                        "method": "POST",
                        "params": {
                            "client_id": client_id,
                            "trigger_type": "payment_overdue",
                        },
                    },
                    "secondary_actions": [
                        {"type": "navigate", "label": "View Payment Plan",
                         "endpoint": f"/api/v1/clients/{client_id}/payment-plans",
                         "method": "GET"},
                        {"type": "dismiss", "label": "Dismiss"},
                    ],
                    "source": "proactive",
                    "timestamp": "",
                })
    except Exception:
        logger.debug("Proactive: payment plan health check failed")

    return issues


# ===================================================================
#  LOCATION-AWARE SUGGESTIONS
# ===================================================================

def _normalize_location(location: str) -> Tuple[str, str]:
    """Extract a county name and city name from a location string.

    Returns (county, city) with lowercased values for matching.
    E.g. "Fulton County Courthouse, 136 Pryor St" -> ("fulton county", "")
         "Cobb County Superior Court" -> ("cobb county", "")
         "Atlanta, GA" -> ("", "atlanta")
    """
    if not location:
        return ("", "")

    loc_lower = location.lower().strip()

    # Try to extract county: look for "X county" pattern
    county_match = re.search(r"(\w[\w\s]*?)\s+county", loc_lower)
    county = ""
    if county_match:
        county = county_match.group(1).strip() + " county"

    # Try to extract city: often before a comma or before "courthouse"
    city = ""
    # "City, State" pattern
    city_match = re.match(r"^([\w\s]+),", loc_lower)
    if city_match and not county:
        city = city_match.group(1).strip()

    return (county, city)


def _location_matches(loc1: str, loc2: str) -> bool:
    """Check if two location strings refer to the same general area.

    Uses fuzzy matching on county and city names.
    """
    if not loc1 or not loc2:
        return False

    county1, city1 = _normalize_location(loc1)
    county2, city2 = _normalize_location(loc2)

    # County match
    if county1 and county2 and county1 == county2:
        return True

    # City match
    if city1 and city2 and city1 == city2:
        return True

    # Substring match on the raw lowercased strings (e.g. both mention "Fulton")
    loc1_lower = loc1.lower()
    loc2_lower = loc2.lower()

    # Extract significant words (>3 chars, not common words)
    _skip = {"the", "court", "courthouse", "street", "road", "avenue",
             "drive", "blvd", "suite", "room", "floor", "building"}
    words1 = {w for w in re.findall(r"\w+", loc1_lower) if len(w) > 3 and w not in _skip}
    words2 = {w for w in re.findall(r"\w+", loc2_lower) if len(w) > 3 and w not in _skip}

    # If they share a significant word (like county name or city), consider it a match
    overlap = words1 & words2
    if overlap:
        return True

    return False


def _build_location_suggestions(
    case_mgr,
    data_dir: str,
    today_events: List[Dict],
) -> List[Dict]:
    """Build location-aware suggestions for today's scheduled events.

    For each unique location on today's calendar, searches ALL active
    cases for tasks, deadlines, or filings that could also be completed
    at that same location.

    Args:
        case_mgr: CaseManager instance.
        data_dir: Path to the data directory.
        today_events: List of today's calendar event dicts.

    Returns:
        List of location suggestion dicts, each containing the scheduled
        event and a list of additional opportunities at that location.
    """
    _dir = data_dir or _DATA_DIR
    suggestions: List[Dict] = []

    # Collect unique locations from today's events
    location_events: Dict[str, Dict] = {}  # location -> first event at that location
    for ev in today_events:
        loc = ev.get("location", "").strip()
        if not loc:
            continue
        if loc not in location_events:
            location_events[loc] = ev

    if not location_events:
        return suggestions

    # Load all active cases and their tasks/deadlines
    try:
        all_cases = case_mgr.list_cases(include_archived=False)
    except Exception:
        return suggestions

    case_ids = {c.get("id", "") for c in all_cases if c.get("id")}

    # Get event case IDs to exclude (already scheduled for that location)
    event_case_ids_at_location: Dict[str, set] = {}
    for loc, ev in location_events.items():
        event_case_ids_at_location.setdefault(loc, set())
        if ev.get("case_id"):
            event_case_ids_at_location[loc].add(ev["case_id"])

    for location, scheduled_event in location_events.items():
        opportunities: List[Dict] = []
        scheduled_case_ids = event_case_ids_at_location.get(location, set())

        # Helper to safely get case name
        def _case_name(cid: str) -> str:
            try:
                return case_mgr.get_case_name(cid) or cid
            except Exception:
                return cid

        # Search tasks across all cases
        try:
            from core.tasks import load_tasks

            for cid in case_ids:
                if cid in scheduled_case_ids:
                    continue

                tasks = load_tasks(_dir, cid)
                for t in tasks:
                    if t.get("status") in ("completed", "cancelled"):
                        continue

                    # Match on filing/court tasks or tasks with matching location in title
                    category = t.get("category", "")
                    title_lower = t.get("title", "").lower()
                    desc_lower = t.get("description", "").lower()

                    is_location_task = category in ("Filing", "Court Appearance")
                    has_location_ref = _location_matches(location, title_lower) or \
                                       _location_matches(location, desc_lower)

                    if is_location_task or has_location_ref:
                        opportunities.append({
                            "title": t.get("title", "Task"),
                            "case_id": cid,
                            "case_name": _case_name(cid),
                            "detail": f"{category} — {t.get('title', '')}",
                            "task_id": t.get("id", ""),
                            "action": {
                                "type": "navigate",
                                "label": "View Task",
                                "endpoint": f"/api/v1/cases/{cid}/tasks/{t.get('id', '')}",
                                "method": "GET",
                                "params": {"case_id": cid, "task_id": t.get("id", "")},
                            },
                        })
        except Exception:
            logger.debug("Location suggestions: task search failed")

        # Search deadlines with location-related labels
        try:
            all_deadlines = case_mgr.get_all_deadlines()
            for dl in all_deadlines:
                cid = dl.get("case_id", "")
                if cid in scheduled_case_ids:
                    continue

                days_rem = dl.get("days_remaining", 999)
                if days_rem < 0 or days_rem > 30:
                    continue

                label = dl.get("label", "")
                if _location_matches(location, label):
                    opportunities.append({
                        "title": f"Deadline: {label}",
                        "case_id": cid,
                        "case_name": dl.get("_case_name", "") or _case_name(cid),
                        "detail": f"Due in {days_rem} day{'s' if days_rem != 1 else ''}",
                        "task_id": "",
                        "action": {
                            "type": "navigate",
                            "label": "View Deadline",
                            "endpoint": f"/api/v1/cases/{cid}",
                            "method": "GET",
                            "params": {"case_id": cid},
                        },
                    })
        except Exception:
            logger.debug("Location suggestions: deadline search failed")

        # Also search case metadata for courthouse field matching location
        try:
            for case in all_cases:
                cid = case.get("id", "")
                if cid in scheduled_case_ids:
                    continue

                case_courthouse = case.get("courthouse", "") or case.get("court", "")
                if case_courthouse and _location_matches(location, case_courthouse):
                    # Check if this case has pending filings
                    from core.tasks import load_tasks as _lt
                    ctasks = _lt(_dir, cid)
                    filing_tasks = [
                        t for t in ctasks
                        if t.get("category") == "Filing"
                        and t.get("status") not in ("completed", "cancelled")
                    ]
                    for ft in filing_tasks:
                        # Avoid duplicates
                        if not any(o.get("task_id") == ft.get("id") for o in opportunities):
                            opportunities.append({
                                "title": ft.get("title", "Filing"),
                                "case_id": cid,
                                "case_name": _case_name(cid),
                                "detail": f"Same courthouse as {scheduled_event.get('title', 'event')}",
                                "task_id": ft.get("id", ""),
                                "action": {
                                    "type": "file_document",
                                    "label": "File Document",
                                    "endpoint": f"/api/v1/cases/{cid}/tasks/{ft.get('id', '')}",
                                    "method": "GET",
                                    "params": {"case_id": cid, "task_id": ft.get("id", "")},
                                },
                            })
        except Exception:
            logger.debug("Location suggestions: courthouse metadata search failed")

        if opportunities:
            suggestions.append({
                "location": location,
                "scheduled_event": {
                    "title": scheduled_event.get("title", ""),
                    "time": scheduled_event.get("time", ""),
                    "case_id": scheduled_event.get("case_id", ""),
                    "event_id": scheduled_event.get("id", ""),
                },
                "opportunities": opportunities,
            })

    return suggestions


# ===================================================================
#  COMPONENT 5: Daily Email Digest
# ===================================================================

def _format_digest_html(brief: Dict) -> str:
    """Format the morning brief as a clean HTML email body.

    Sections:
        1. Header with date and summary counts
        2. Critical items (red)
        3. High-priority items (orange)
        4. Today's schedule
        5. Location-aware opportunities
        6. Medium/low items summary

    Args:
        brief: The full morning brief dict from generate_morning_brief().

    Returns:
        HTML string suitable for email body.
    """
    summary = brief.get("summary", {})
    triage = brief.get("triage_items", [])
    schedule = brief.get("today_schedule", [])
    locations = brief.get("location_suggestions", [])
    brief_date = brief.get("date", str(date.today()))

    critical = [i for i in triage if i.get("severity") == "critical"]
    high = [i for i in triage if i.get("severity") == "high"]
    medium_low = [i for i in triage if i.get("severity") in ("medium", "low")]

    html_parts = []

    # -- Wrapper and header --
    html_parts.append("""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 640px; margin: 0 auto; padding: 20px; color: #1a1a2e;">
""")

    html_parts.append(f"""
<div style="background: linear-gradient(135deg, #4338ca, #6366f1); color: white;
            padding: 24px; border-radius: 12px; margin-bottom: 24px;">
  <h1 style="margin: 0 0 8px 0; font-size: 22px;">Morning Brief</h1>
  <p style="margin: 0; opacity: 0.9; font-size: 14px;">{brief_date}</p>
  <div style="margin-top: 16px; display: flex; gap: 16px; flex-wrap: wrap;">
    <span style="background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 6px;
                 font-size: 13px;">
      {summary.get('total_items', 0)} items
    </span>
    <span style="background: rgba(239,68,68,0.3); padding: 6px 12px; border-radius: 6px;
                 font-size: 13px;">
      {summary.get('critical_count', 0)} critical
    </span>
    <span style="background: rgba(249,115,22,0.3); padding: 6px 12px; border-radius: 6px;
                 font-size: 13px;">
      {summary.get('high_count', 0)} high
    </span>
    <span style="background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 6px;
                 font-size: 13px;">
      {summary.get('today_events_count', 0)} events today
    </span>
  </div>
</div>
""")

    # -- Critical items --
    if critical:
        html_parts.append("""
<div style="margin-bottom: 24px;">
  <h2 style="color: #dc2626; font-size: 16px; margin-bottom: 12px;
             border-bottom: 2px solid #dc2626; padding-bottom: 4px;">
    Critical Items
  </h2>
""")
        for item in critical:
            html_parts.append(f"""
  <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 12px 16px;
              margin-bottom: 8px; border-radius: 0 8px 8px 0;">
    <strong style="color: #dc2626;">{_html_escape(item.get('title', ''))}</strong>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: #555;">
      {_html_escape(item.get('detail', ''))}
      {(' &mdash; ' + _html_escape(item.get('case_name', ''))) if item.get('case_name') else ''}
    </p>
  </div>
""")
        html_parts.append("</div>")

    # -- High items --
    if high:
        html_parts.append("""
<div style="margin-bottom: 24px;">
  <h2 style="color: #ea580c; font-size: 16px; margin-bottom: 12px;
             border-bottom: 2px solid #ea580c; padding-bottom: 4px;">
    High Priority
  </h2>
""")
        for item in high:
            html_parts.append(f"""
  <div style="background: #fff7ed; border-left: 4px solid #ea580c; padding: 12px 16px;
              margin-bottom: 8px; border-radius: 0 8px 8px 0;">
    <strong>{_html_escape(item.get('title', ''))}</strong>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: #555;">
      {_html_escape(item.get('detail', ''))}
      {(' &mdash; ' + _html_escape(item.get('case_name', ''))) if item.get('case_name') else ''}
    </p>
  </div>
""")
        html_parts.append("</div>")

    # -- Today's schedule --
    if schedule:
        html_parts.append("""
<div style="margin-bottom: 24px;">
  <h2 style="color: #4338ca; font-size: 16px; margin-bottom: 12px;
             border-bottom: 2px solid #4338ca; padding-bottom: 4px;">
    Today's Schedule
  </h2>
""")
        for ev in schedule:
            html_parts.append(f"""
  <div style="background: #eef2ff; padding: 10px 16px; margin-bottom: 6px;
              border-radius: 8px; font-size: 14px;">
    <strong>{_html_escape(ev.get('time', ''))}</strong> &mdash;
    {_html_escape(ev.get('title', ''))}
    {(' @ ' + _html_escape(ev.get('location', ''))) if ev.get('location') else ''}
  </div>
""")
        html_parts.append("</div>")

    # -- Location opportunities --
    if locations:
        html_parts.append("""
<div style="margin-bottom: 24px;">
  <h2 style="color: #059669; font-size: 16px; margin-bottom: 12px;
             border-bottom: 2px solid #059669; padding-bottom: 4px;">
    While You're There...
  </h2>
""")
        for loc in locations:
            ev_title = loc.get("scheduled_event", {}).get("title", "")
            html_parts.append(f"""
  <div style="background: #ecfdf5; padding: 12px 16px; margin-bottom: 8px;
              border-radius: 8px;">
    <p style="margin: 0 0 8px 0; font-size: 13px; color: #065f46;">
      You'll be at <strong>{_html_escape(loc.get('location', ''))}</strong>
      for {_html_escape(ev_title)}:
    </p>
    <ul style="margin: 0; padding-left: 20px;">
""")
            for opp in loc.get("opportunities", []):
                html_parts.append(f"""
      <li style="font-size: 13px; margin-bottom: 4px;">
        {_html_escape(opp.get('title', ''))}
        ({_html_escape(opp.get('case_name', ''))})
      </li>
""")
            html_parts.append("    </ul>\n  </div>\n")
        html_parts.append("</div>")

    # -- Medium/low summary --
    if medium_low:
        html_parts.append(f"""
<div style="margin-bottom: 24px;">
  <h2 style="color: #6b7280; font-size: 16px; margin-bottom: 12px;
             border-bottom: 2px solid #d1d5db; padding-bottom: 4px;">
    Other Items ({len(medium_low)})
  </h2>
  <ul style="padding-left: 20px; font-size: 13px; color: #555;">
""")
        for item in medium_low[:15]:  # Cap to keep email readable
            html_parts.append(f"""
    <li style="margin-bottom: 4px;">
      {_html_escape(item.get('title', ''))}
      {(' &mdash; ' + _html_escape(item.get('case_name', ''))) if item.get('case_name') else ''}
    </li>
""")
        if len(medium_low) > 15:
            html_parts.append(f"    <li><em>...and {len(medium_low) - 15} more</em></li>\n")
        html_parts.append("  </ul>\n</div>")

    # -- Footer --
    html_parts.append(f"""
<div style="border-top: 1px solid #e5e7eb; padding-top: 16px; margin-top: 24px;
            font-size: 12px; color: #9ca3af; text-align: center;">
  Generated by Project Mushroom Cloud &bull; {brief.get('generated_at', '')[:19]}
</div>
</body>
</html>
""")

    return "".join(html_parts)


def _html_escape(text: str) -> str:
    """Minimal HTML escaping for safe embedding in email body."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ===================================================================
#  MAIN ENTRY POINT
# ===================================================================

def generate_morning_brief(
    case_mgr,
    data_dir: str = "",
    user_id: str = "",
    target_date: str = "",
) -> Dict:
    """Generate the complete Morning Brief for the attorney's day.

    Scans all active cases and produces a single prioritized action list
    with one-click actions, location-aware suggestions, and a formatted
    email digest.

    Args:
        case_mgr: CaseManager instance with access to all cases.
        data_dir: Path to the data directory (defaults to project data/).
        user_id: Filter tasks/items to this user (empty = all users).
        target_date: Date to generate the brief for, YYYY-MM-DD
                     (defaults to today).

    Returns:
        Dict with keys: date, generated_at, summary, triage_items,
        location_suggestions, today_schedule, email_html.
    """
    _dir = data_dir or _DATA_DIR
    target = target_date or str(date.today())
    generated_at = datetime.now().isoformat()

    logger.info("Generating morning brief for %s (user=%s)", target, user_id or "all")

    # 1. Collect all triage items
    raw_items = _collect_triage_items(case_mgr, _dir, user_id, target)

    # 2. Filter out dismissed and snoozed items
    suppressed = _get_suppressed_ids(_dir)
    items = [i for i in raw_items if i.get("id") not in suppressed]

    # 3. Deduplicate: if same case_id + type + due_date, keep highest severity
    seen_keys: Dict[str, Dict] = {}
    deduped: List[Dict] = []
    for item in items:
        key = f"{item.get('case_id', '')}|{item.get('type', '')}|{item.get('due_date', '')}|{item.get('title', '')}"
        if key in seen_keys:
            existing = seen_keys[key]
            if _SEVERITY_ORDER.get(item.get("severity", "low"), 3) < \
               _SEVERITY_ORDER.get(existing.get("severity", "low"), 3):
                deduped.remove(existing)
                deduped.append(item)
                seen_keys[key] = item
        else:
            seen_keys[key] = item
            deduped.append(item)

    # 4. Sort: severity -> due_date -> source priority
    deduped.sort(key=lambda x: (
        _SEVERITY_ORDER.get(x.get("severity", "low"), 3),
        x.get("due_date", "") or "9999-99-99",
        _SOURCE_PRIORITY.get(x.get("source", "proactive"), 5),
    ))

    # 5. Cap at maximum
    triage_items = deduped[:_MAX_TRIAGE_ITEMS]

    # 6. Build today's schedule
    today_schedule: List[Dict] = []
    try:
        from core.calendar_events import get_events_for_date

        today_events = get_events_for_date(target)
        today_events.sort(key=lambda e: e.get("time", "") or "99:99")
        for ev in today_events:
            today_schedule.append({
                "time": ev.get("time", ""),
                "title": ev.get("title", ""),
                "location": ev.get("location", ""),
                "case_id": ev.get("case_id", ""),
                "event_id": ev.get("id", ""),
            })
    except Exception:
        logger.debug("Morning brief: schedule build failed")
        today_events = []

    # 7. Build location-aware suggestions
    try:
        if not today_events:
            from core.calendar_events import get_events_for_date as _gef
            today_events = _gef(target)
        location_suggestions = _build_location_suggestions(case_mgr, _dir, today_events)
    except Exception:
        logger.debug("Morning brief: location suggestions failed")
        location_suggestions = []

    # 8. Compute summary
    cases_with_activity = len(set(
        i.get("case_id", "") for i in triage_items if i.get("case_id")
    ))
    summary = {
        "total_items": len(triage_items),
        "critical_count": sum(1 for i in triage_items if i.get("severity") == "critical"),
        "high_count": sum(1 for i in triage_items if i.get("severity") == "high"),
        "cases_with_activity": cases_with_activity,
        "today_events_count": len(today_schedule),
    }

    # 9. Assemble brief
    brief = {
        "date": target,
        "generated_at": generated_at,
        "summary": summary,
        "triage_items": triage_items,
        "location_suggestions": location_suggestions,
        "today_schedule": today_schedule,
    }

    # 10. Generate HTML email digest
    brief["email_html"] = _format_digest_html(brief)

    logger.info(
        "Morning brief generated: %d items (%d critical, %d high), %d locations",
        summary["total_items"],
        summary["critical_count"],
        summary["high_count"],
        len(location_suggestions),
    )

    return brief
