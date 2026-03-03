"""Canonical list of analysis module names.

This is the single source of truth used by both the core analysis pipeline
and the API layer.  Import from here — never define this list elsewhere.
"""

MODULE_NAMES: list[str] = [
    "case_summary",
    "charges",
    "timeline",
    "witnesses",
    "evidence_foundations",
    "legal_elements",
    "consistency_check",
    "investigation_plan",
    "cross_examination_plan",
    "direct_examination_plan",
    "strategy_notes",
    "devils_advocate_notes",
    "entities",
    "voir_dire",
    "mock_jury_feedback",
]
