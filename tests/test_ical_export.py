"""Tests for iCal export (Phase 17)."""
import pytest
from datetime import datetime, date


class TestICalExport:
    def test_import(self):
        from core.ical_export import generate_ics
        assert generate_ics is not None

    def test_generate_single_event(self):
        from core.ical_export import generate_ics
        events = [
            {
                "title": "Court Hearing",
                "start": datetime(2026, 4, 15, 9, 0),
                "end": datetime(2026, 4, 15, 11, 0),
                "description": "Motion hearing for Smith v. Johnson",
                "location": "Federal Courthouse, Room 4B",
            }
        ]
        ics = generate_ics(events, calendar_name="Test Calendar")
        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "Court Hearing" in ics
        assert "END:VCALENDAR" in ics

    def test_generate_empty(self):
        from core.ical_export import generate_ics
        ics = generate_ics([], calendar_name="Empty")
        assert "BEGIN:VCALENDAR" in ics
        assert "END:VCALENDAR" in ics

    def test_generate_all_day_event(self):
        from core.ical_export import generate_ics
        events = [
            {
                "title": "SOL Deadline",
                "start": date(2026, 6, 1),
                "all_day": True,
                "description": "Statute of limitations expires",
            }
        ]
        ics = generate_ics(events)
        assert "SOL Deadline" in ics

    def test_multiple_events(self):
        from core.ical_export import generate_ics
        events = [
            {"title": f"Event {i}", "start": datetime(2026, 3, i + 1, 10, 0)}
            for i in range(5)
        ]
        ics = generate_ics(events)
        assert ics.count("BEGIN:VEVENT") == 5
