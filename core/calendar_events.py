"""
calendar_events.py -- Firm-Wide Calendar & Events Module
Centralized event system with CRUD, calendar views, iCal export,
and deadline merging.
Storage: data/calendar/events.json
"""

import os
import json
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import calendar as _cal

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CAL_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "calendar")
_EVENTS_FILE = os.path.join(_CAL_DIR, "events.json")

EVENT_TYPES = [
    "Court Date",
    "Filing Deadline",
    "Client Meeting",
    "Deposition",
    "Mediation",
    "Consultation",
    "Internal",
    "Other",
]

EVENT_STATUSES = ["scheduled", "completed", "cancelled", "rescheduled"]

EVENT_TYPE_COLORS = {
    "Court Date": "#ef4444",
    "Filing Deadline": "#f97316",
    "Client Meeting": "#3b82f6",
    "Deposition": "#8b5cf6",
    "Mediation": "#06b6d4",
    "Consultation": "#22c55e",
    "Internal": "#64748b",
    "Other": "#a855f7",
}


def _ensure_dir():
    os.makedirs(_CAL_DIR, exist_ok=True)


def _load_all() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_EVENTS_FILE):
        try:
            with open(_EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_all(events: List[Dict]):
    _ensure_dir()
    with open(_EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, default=str)


# -- CRUD --

def add_event(
    title: str,
    event_type: str = "Other",
    event_date: str = "",
    time: str = "",
    end_time: str = "",
    location: str = "",
    case_id: str = "",
    client_id: str = "",
    description: str = "",
    reminder_days: List[int] = None,
    recurring: bool = False,
    assigned_to: List[str] = None,
) -> str:
    """Add a new event. Returns event ID."""
    events = _load_all()
    eid = uuid.uuid4().hex[:8]
    event = {
        "id": eid,
        "title": title,
        "event_type": event_type,
        "date": event_date or str(date.today()),
        "time": time,
        "end_time": end_time,
        "location": location,
        "case_id": case_id,
        "client_id": client_id,
        "description": description,
        "reminder_days": reminder_days if reminder_days else [7, 1, 0],
        "status": "scheduled",
        "recurring": recurring,
        "google_event_id": "",
        "assigned_to": assigned_to if assigned_to else [],
        "created_at": datetime.now().isoformat(),
    }
    events.append(event)
    _save_all(events)
    return eid


def load_events() -> List[Dict]:
    """Load all events."""
    return _load_all()


def get_event(event_id: str) -> Optional[Dict]:
    """Get a single event by ID."""
    for e in _load_all():
        if e.get("id") == event_id:
            return e
    return None


def update_event(event_id: str, updates: Dict) -> bool:
    """Update fields on an event. Returns True if found."""
    events = _load_all()
    for e in events:
        if e.get("id") == event_id:
            e.update(updates)
            _save_all(events)
            return True
    return False


def delete_event(event_id: str) -> bool:
    """Delete an event. Returns True if found."""
    events = _load_all()
    filtered = [e for e in events if e.get("id") != event_id]
    if len(filtered) < len(events):
        _save_all(filtered)
        return True
    return False


# -- Queries --

def get_events_for_date(target_date: str) -> List[Dict]:
    """Get all events for a specific date (YYYY-MM-DD)."""
    return [e for e in _load_all() if e.get("date") == target_date and e.get("status") != "cancelled"]


def get_events_for_range(start_date: str, end_date: str) -> List[Dict]:
    """Get events within a date range (inclusive)."""
    events = _load_all()
    result = []
    for e in events:
        d = e.get("date", "")
        if d and start_date <= d <= end_date and e.get("status") != "cancelled":
            result.append(e)
    return sorted(result, key=lambda x: (x.get("date", ""), x.get("time", "")))


def get_events_for_case(case_id: str) -> List[Dict]:
    """Get all events linked to a case."""
    return [e for e in _load_all() if e.get("case_id") == case_id]


def get_upcoming_events(days: int = 14) -> List[Dict]:
    """Get upcoming events within N days."""
    today = date.today()
    end = today + timedelta(days=days)
    events = get_events_for_range(str(today), str(end))
    # Add days_until for convenience
    for e in events:
        try:
            ed = datetime.strptime(e["date"], "%Y-%m-%d").date()
            e["days_until"] = (ed - today).days
        except (ValueError, KeyError):
            e["days_until"] = 999
    return events


# -- Calendar View --

def get_month_calendar(year: int, month: int) -> Dict:
    """
    Returns a dict for rendering a month calendar:
    {
        "year": 2026, "month": 2, "month_name": "February",
        "weeks": [[None,None,..., {"day": 1, "events": [...]}], ...],
        "total_events": 5
    }
    """
    cal = _cal.Calendar(firstweekday=6)  # Sunday start
    month_name = _cal.month_name[month]

    # Get events for this month
    first_day = f"{year:04d}-{month:02d}-01"
    last_day_num = _cal.monthrange(year, month)[1]
    last_day = f"{year:04d}-{month:02d}-{last_day_num:02d}"
    month_events = get_events_for_range(first_day, last_day)

    # Build events-by-date lookup
    events_by_date = {}
    for e in month_events:
        d = e.get("date", "")
        events_by_date.setdefault(d, []).append(e)

    # Build weeks grid
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        week_data = []
        for day_num in week:
            if day_num == 0:
                week_data.append(None)
            else:
                day_str = f"{year:04d}-{month:02d}-{day_num:02d}"
                week_data.append({
                    "day": day_num,
                    "date": day_str,
                    "events": events_by_date.get(day_str, []),
                    "is_today": day_str == str(date.today()),
                })
        weeks.append(week_data)

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "weeks": weeks,
        "total_events": len(month_events),
    }


# -- iCal Export --

def export_ical(events: List[Dict] = None, case_id: str = "") -> str:
    """Generate .ics file content for calendar sync."""
    if events is None:
        if case_id:
            events = get_events_for_case(case_id)
        else:
            events = _load_all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AllRise Beta//Legal Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for e in events:
        if e.get("status") == "cancelled":
            continue
        uid = e.get("id", uuid.uuid4().hex[:8])
        summary = e.get("title", "Event")
        d = e.get("date", "").replace("-", "")
        t = e.get("time", "").replace(":", "")
        et = e.get("end_time", "").replace(":", "")
        location = e.get("location", "")
        desc = e.get("description", "")
        created = e.get("created_at", datetime.now().isoformat())

        # Format dates
        if t:
            dtstart = f"{d}T{t}00"
        else:
            dtstart = d

        if et:
            dtend = f"{d}T{et}00"
        elif t:
            # Default 1 hour duration
            dtend = f"{d}T{t}00"
        else:
            dtend = d

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}@tlo-allrise")
        lines.append(f"DTSTART:{dtstart}")
        lines.append(f"DTEND:{dtend}")
        lines.append(f"SUMMARY:{_ical_escape(summary)}")
        if location:
            lines.append(f"LOCATION:{_ical_escape(location)}")
        if desc:
            lines.append(f"DESCRIPTION:{_ical_escape(desc)}")
        lines.append(f"STATUS:{_ical_status(e.get('status', 'scheduled'))}")

        # Alarms
        for rd in e.get("reminder_days", []):
            lines.append("BEGIN:VALARM")
            lines.append("ACTION:DISPLAY")
            lines.append(f"DESCRIPTION:Reminder: {summary}")
            if rd == 0:
                lines.append("TRIGGER:PT0M")
            else:
                lines.append(f"TRIGGER:-P{rd}D")
            lines.append("END:VALARM")

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _ical_escape(text: str) -> str:
    """Escape special characters for iCal format."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _ical_status(status: str) -> str:
    """Map internal status to iCal status."""
    return {
        "scheduled": "CONFIRMED",
        "completed": "CONFIRMED",
        "cancelled": "CANCELLED",
        "rescheduled": "TENTATIVE",
    }.get(status, "CONFIRMED")


# -- Merge with Deadlines --

def merge_deadlines_and_events(case_mgr, days: int = 30) -> List[Dict]:
    """
    Combines existing case deadlines with calendar events into a
    unified, sorted timeline.
    """
    today = date.today()
    end = today + timedelta(days=days)
    merged = []

    # Calendar events
    upcoming = get_events_for_range(str(today), str(end))
    for e in upcoming:
        merged.append({
            "type": "event",
            "title": e.get("title", "Event"),
            "date": e.get("date", ""),
            "time": e.get("time", ""),
            "event_type": e.get("event_type", "Other"),
            "case_id": e.get("case_id", ""),
            "status": e.get("status", "scheduled"),
            "location": e.get("location", ""),
            "source": "calendar",
            "id": e.get("id", ""),
        })

    # Case deadlines
    try:
        all_deadlines = case_mgr.get_all_deadlines()
        for dl in all_deadlines:
            days_rem = dl.get("days_remaining", 999)
            if 0 <= days_rem <= days:
                merged.append({
                    "type": "deadline",
                    "title": dl.get("label", "Deadline"),
                    "date": dl.get("date", ""),
                    "time": "",
                    "event_type": dl.get("category", "Filing Deadline"),
                    "case_id": dl.get("case_id", ""),
                    "case_name": dl.get("case_name", ""),
                    "status": "overdue" if days_rem < 0 else "upcoming",
                    "days_remaining": days_rem,
                    "source": "deadline",
                    "id": dl.get("id", ""),
                })
    except Exception:
        pass

    # Sort by date then time
    merged.sort(key=lambda x: (x.get("date", "9999"), x.get("time", "99:99")))
    return merged


# -- Stats --

def get_calendar_stats() -> Dict:
    """Aggregate calendar statistics for dashboard display."""
    events = _load_all()
    today = str(date.today())
    this_week_end = str(date.today() + timedelta(days=7))

    active = [e for e in events if e.get("status") not in ("cancelled",)]
    upcoming = [e for e in active if e.get("date", "") >= today]
    this_week = [e for e in active if today <= e.get("date", "") <= this_week_end]
    past_due = [e for e in active if e.get("date", "") < today and e.get("status") == "scheduled"]

    # Type breakdown
    type_counts = {}
    for e in active:
        et = e.get("event_type", "Other")
        type_counts[et] = type_counts.get(et, 0) + 1

    return {
        "total_events": len(events),
        "active_events": len(active),
        "upcoming": len(upcoming),
        "this_week": len(this_week),
        "past_due": len(past_due),
        "completed": sum(1 for e in events if e.get("status") == "completed"),
        "cancelled": sum(1 for e in events if e.get("status") == "cancelled"),
        "type_breakdown": type_counts,
    }
