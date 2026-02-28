# ---- Pydantic Models for Structured Data ---------------------------------
# All structured data previously represented as untyped dicts.
# All fields have defaults so existing JSON with missing keys deserializes safely.

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- Case Metadata -------------------------------------------------------

class CaseMetadata(BaseModel):
    """Metadata for a case stored in config.json."""
    id: str = ""
    name: str = ""
    description: str = ""
    status: str = "active"
    phase: str = ""                     # "active" | "closed" | "archived" (empty = derive from status)
    sub_phase: str = ""                 # Active sub-phase e.g. "Discovery" (empty when closed/archived)
    purged: bool = False                # True after source docs have been purged
    case_type: str = "criminal"
    case_category: str = ""
    case_subcategory: str = ""
    client_name: str = ""
    assigned_to: List[str] = Field(default_factory=list)
    created_at: str = ""
    last_updated: str = ""
    jurisdiction: str = ""
    client_id: str = ""
    client_phone: str = ""
    client_email: str = ""
    client_address: str = ""


class PreparationMeta(BaseModel):
    """Metadata for a preparation within a case."""
    id: str
    type: str = "trial"  # trial | prelim_hearing | motion_hearing
    name: str = ""
    created_at: str = ""
    last_updated: str = ""


# ---- Analysis Result Models ----------------------------------------------

class Witness(BaseModel):
    """A witness identified during case analysis."""
    name: str = ""
    type: str = ""       # State | Defense | Swing | Victim | Expert
    goal: str = ""
    contact_info: str = ""
    key_testimony: str = ""
    credibility: str = ""
    impeachment: str = ""
    role: str = ""
    alignment: str = ""
    description: str = ""
    notes: str = ""
    source_ref: str = ""
    _ai_suggests_remove: Optional[bool] = None

    class Config:
        extra = "allow"


class TimelineEvent(BaseModel):
    """A chronological event in the case timeline."""
    year: str = ""
    month: str = ""
    day: str = ""
    date: str = ""
    time: str = ""
    headline: str = ""
    text: str = ""
    event: str = ""
    description: str = ""
    source: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


class LegalElement(BaseModel):
    """A legal element mapped to evidence."""
    charge: str = ""
    element: str = ""
    evidence: str = ""
    strength: str = ""   # Met | Not Met | Weak | Disputed
    status: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


class Charge(BaseModel):
    """A criminal charge or civil claim."""
    name: str = ""
    charge: str = ""
    claim: str = ""
    statute_number: str = ""
    level: str = ""
    class_: str = Field(default="", alias="class")
    statute_text: str = ""
    jury_instructions: str = ""
    text: str = ""
    instructions: str = ""

    class Config:
        extra = "allow"
        populate_by_name = True


class InvestigationTask(BaseModel):
    """An item in the investigation plan."""
    action: str = ""
    task: str = ""
    description: str = ""
    reason: str = ""
    priority: str = ""   # High | Medium | Low
    status: str = "pending"
    category: str = ""
    notes: str = ""
    _user_completed: Optional[bool] = None
    _user_added: Optional[bool] = None

    class Config:
        extra = "allow"


class ConsistencyItem(BaseModel):
    """A consistency check finding (contradiction or inconsistency)."""
    fact: str = ""
    issue: str = ""
    contradiction: str = ""
    conflict: str = ""
    source_a: str = ""
    source_b: str = ""
    notes: str = ""
    details: str = ""
    description: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


class EvidenceFoundation(BaseModel):
    """An evidence item with admissibility analysis."""
    item: str = ""
    exhibit: str = ""
    evidence: str = ""
    name: str = ""
    admissibility: str = ""
    foundation: str = ""
    foundation_type: str = ""
    attack: str = ""
    objections: str = ""
    ruling: str = ""
    description: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


class Entity(BaseModel):
    """A named entity extracted from case documents."""
    id: str = ""
    name: str = ""
    type: str = "PERSON"  # PERSON | ORGANIZATION | PLACE
    context: str = ""
    role: str = ""
    description: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


class Relationship(BaseModel):
    """A relationship between two entities."""
    source: str = ""
    target: str = ""
    relation: str = ""
    source_ref: str = ""

    class Config:
        extra = "allow"


# ---- Operational Models --------------------------------------------------

class AttorneyDirective(BaseModel):
    """An attorney directive that overrides AI analysis."""
    id: str = ""
    text: str = ""
    category: str = "instruction"  # fact | strategy | instruction
    created_at: str = ""


class CostEntry(BaseModel):
    """A cost tracking entry for an analysis run."""
    action: str = ""
    tokens: int = 0
    cost: float = 0.0
    model: str = ""
    timestamp: str = ""
    node: str = ""


class DeadlineEntry(BaseModel):
    """A court deadline or filing date."""
    id: str = ""
    date: str = ""
    time: str = ""
    label: str = ""
    category: str = "Custom"  # Court Date | Filing Deadline | Statute of Limitations | Discovery | Custom
    reminder_days: List[int] = Field(default_factory=lambda: [7, 3, 1, 0])
    dismissed_reminders: List[int] = Field(default_factory=list)
    created_at: str = ""
    notes: str = ""


class ContactLogEntry(BaseModel):
    """A contact log entry for a case."""
    id: str = ""
    contact_type: str = ""  # Phone Call | In-Person | Zoom/Video | Email | Text/Message | Court Appearance | Other
    person: str = ""
    subject: str = ""
    notes: str = ""
    contact_date: str = ""
    contact_time: str = ""
    duration_mins: int = 0
    created_at: str = ""


class JournalEntry(BaseModel):
    """A case journal entry."""
    id: str = ""
    text: str = ""
    category: str = "General"
    timestamp: str = ""
