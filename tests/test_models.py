# ---- Tests for core/models.py ---------------------------------------------

import pytest
from core.models import (
    CaseMetadata, PreparationMeta, Witness, TimelineEvent,
    LegalElement, Charge, InvestigationTask, ConsistencyItem,
    EvidenceFoundation, Entity, Relationship, AttorneyDirective,
    CostEntry, DeadlineEntry, ContactLogEntry, JournalEntry,
)


class TestCaseMetadata:
    def test_defaults(self):
        meta = CaseMetadata()
        assert meta.id == ""
        assert meta.name == ""
        assert meta.status == "active"
        assert meta.case_type == "criminal"
        assert meta.assigned_to == []

    def test_from_dict(self):
        data = {"id": "case1", "name": "State v. Smith", "case_type": "civil-plaintiff"}
        meta = CaseMetadata(**data)
        assert meta.id == "case1"
        assert meta.case_type == "civil-plaintiff"

    def test_extra_fields_preserved(self):
        """CaseMetadata doesn't have extra='allow', but fields with defaults are fine."""
        data = {"id": "case1", "name": "Test", "jurisdiction": "TN"}
        meta = CaseMetadata(**data)
        assert meta.jurisdiction == "TN"


class TestWitness:
    def test_defaults(self):
        w = Witness()
        assert w.name == ""
        assert w.type == ""

    def test_full_witness(self):
        w = Witness(
            name="Officer Smith",
            type="State",
            goal="Testify about arrest",
            credibility="High",
        )
        assert w.name == "Officer Smith"
        assert w.type == "State"

    def test_extra_fields(self):
        w = Witness(name="Test", custom_field="custom_value")
        assert w.name == "Test"
        # Extra fields allowed
        assert w.custom_field == "custom_value"

    def test_dict_roundtrip(self):
        data = {"name": "Jane", "type": "Defense", "goal": "Alibi"}
        w = Witness(**data)
        d = w.model_dump()
        assert d["name"] == "Jane"
        assert d["goal"] == "Alibi"


class TestCharge:
    def test_class_alias(self):
        """The 'class' field must work via the 'class_' alias."""
        c = Charge(name="Assault", level="Misdemeanor", **{"class": "A"})
        assert c.class_ == "A"

    def test_populate_by_name(self):
        c = Charge(name="Theft", class_="B")
        assert c.class_ == "B"

    def test_dict_output_uses_alias(self):
        c = Charge(name="DUI", class_="A")
        d = c.model_dump(by_alias=True)
        assert "class" in d
        assert d["class"] == "A"


class TestTimelineEvent:
    def test_defaults(self):
        t = TimelineEvent()
        assert t.year == ""
        assert t.headline == ""

    def test_from_dict(self):
        data = {"year": "2025", "month": "06", "day": "15", "headline": "Arrest"}
        t = TimelineEvent(**data)
        assert t.year == "2025"
        assert t.headline == "Arrest"


class TestLegalElement:
    def test_defaults(self):
        e = LegalElement()
        assert e.charge == ""
        assert e.strength == ""

    def test_full(self):
        e = LegalElement(
            charge="Assault", element="Physical contact",
            evidence="Witness testimony", strength="Met",
        )
        assert e.strength == "Met"


class TestInvestigationTask:
    def test_defaults(self):
        t = InvestigationTask()
        assert t.status == "pending"
        assert t.priority == ""

    def test_full(self):
        t = InvestigationTask(
            action="Subpoena records", priority="High", status="completed",
        )
        assert t.status == "completed"


class TestDeadlineEntry:
    def test_defaults(self):
        d = DeadlineEntry()
        assert d.category == "Custom"
        assert d.reminder_days == [7, 3, 1, 0]
        assert d.dismissed_reminders == []

    def test_custom_reminders(self):
        d = DeadlineEntry(reminder_days=[14, 7, 1])
        assert d.reminder_days == [14, 7, 1]


class TestModelsBackwardCompat:
    """Ensure models handle missing fields gracefully (backward compat)."""

    def test_witness_missing_fields(self):
        # Old data might only have name and type
        w = Witness(name="Bob")
        assert w.goal == ""
        assert w.credibility == ""

    def test_entity_missing_fields(self):
        e = Entity(id="e1", name="Corp Inc")
        assert e.type == "PERSON"  # default
        assert e.context == ""

    def test_cost_entry_defaults(self):
        c = CostEntry()
        assert c.tokens == 0
        assert c.cost == 0.0

    def test_journal_entry(self):
        j = JournalEntry(text="Test note")
        assert j.category == "General"

    def test_contact_log_entry(self):
        c = ContactLogEntry(person="John", contact_type="Phone Call")
        assert c.duration_mins == 0
