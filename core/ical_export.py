"""iCal export — generate .ics files for case calendars."""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def generate_ics(events: list[dict], calendar_name: str = "Case Calendar") -> str:
    """Generate an .ics file string from a list of events.

    Each event: {id, title, description, start, end, location, all_day, event_type}
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Project Mushroom Cloud//Legal Calendar//EN",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for event in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{event.get('id', '')}@mushroom-cloud")
        lines.append(f"SUMMARY:{_escape(event.get('title', 'Untitled'))}")

        if event.get("description"):
            lines.append(f"DESCRIPTION:{_escape(event['description'])}")

        if event.get("location"):
            lines.append(f"LOCATION:{_escape(event['location'])}")

        # Handle dates
        start = _parse_dt(event.get("start"))
        end = _parse_dt(event.get("end"))

        if event.get("all_day"):
            lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
            if end:
                lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART:{_format_dt(start)}")
            if end:
                lines.append(f"DTEND:{_format_dt(end)}")
            else:
                lines.append(f"DTEND:{_format_dt(start + timedelta(hours=1))}")

        # Category from event type
        etype = event.get("event_type", "meeting")
        lines.append(f"CATEGORIES:{etype.upper()}")

        # Color hint
        colors = {
            "hearing": "red", "deadline": "orange", "meeting": "blue",
            "deposition": "purple", "filing": "green",
        }
        if etype in colors:
            lines.append(f"COLOR:{colors[etype]}")

        lines.append(f"DTSTAMP:{_format_dt(datetime.utcnow())}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _escape(text: str) -> str:
    """Escape special characters for iCal."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _format_dt(dt: datetime) -> str:
    """Format datetime for iCal (UTC)."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _parse_dt(value) -> datetime:
    """Parse a datetime from various formats."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return datetime.utcnow()
