# ---- Readiness Score Computation ------------------------------------------
# Extracted from app.py.  Computes a 0-100% "trial readiness" score based on
# which analysis modules have produced data.

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Weights for each module (out of 100 total)
_MODULE_WEIGHTS: List[Tuple[str, str, float]] = [
    # (state_key, label, weight)
    ("case_summary", "Case Summary", 10),
    ("charges", "Charges / Claims", 10),
    ("timeline", "Timeline", 8),
    ("witnesses", "Witnesses", 8),
    ("evidence_foundations", "Evidence Foundations", 8),
    ("legal_elements", "Legal Elements", 8),
    ("strategy_notes", "Strategy", 8),
    ("devils_advocate_notes", "Devil's Advocate", 5),
    ("consistency_check", "Consistency Check", 6),
    ("investigation_plan", "Investigation Plan", 5),
    ("cross_examination_plan", "Cross-Examination", 6),
    ("direct_examination_plan", "Direct Examination", 6),
    ("entities", "Entities", 4),
    ("voir_dire", "Voir Dire", 4),
    ("mock_jury_feedback", "Mock Jury", 4),
]

# Action suggestions for missing modules
_MODULE_ACTIONS: Dict[str, str] = {
    "case_summary": "Run analysis to generate a case summary",
    "charges": "Add charges or claims to the case",
    "timeline": "Run analysis to generate a timeline of events",
    "witnesses": "Add at least one witness to the case",
    "evidence_foundations": "Run analysis to map evidence foundations",
    "legal_elements": "Run analysis to identify legal elements",
    "strategy_notes": "Run the strategist module for strategy recommendations",
    "devils_advocate_notes": "Run devil's advocate analysis for risk assessment",
    "consistency_check": "Run consistency checker to identify contradictions",
    "investigation_plan": "Run investigation planner for next steps",
    "cross_examination_plan": "Run cross-examiner for witness questioning plans",
    "direct_examination_plan": "Run direct-examiner for witness presentation plans",
    "entities": "Run entity extractor to identify key people and organizations",
    "voir_dire": "Run voir dire agent for jury selection insights",
    "mock_jury_feedback": "Run mock jury simulation for verdict predictions",
}


def _has_data(state: Dict, key: str) -> bool:
    """Check whether a state key has meaningful data."""
    val = state.get(key)
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, list):
        return len(val) > 0
    if isinstance(val, dict):
        return len(val) > 0
    return bool(val)


def compute_readiness_score(state: Dict) -> Tuple[int, str, Dict[str, bool], List[Dict[str, Any]]]:
    """
    Compute the readiness score, letter grade, per-module breakdown, and missing checklist.

    Returns:
        (score, grade, breakdown, missing) where:
            score: int 0-100
            grade: str letter grade (A/B/C/D/F)
            breakdown: {label: bool} for each module
            missing: list of dicts with module, label, action, weight for incomplete modules
    """
    completed_weight = 0.0
    total_weight = sum(w for _, _, w in _MODULE_WEIGHTS)
    breakdown: Dict[str, bool] = {}
    missing: List[Dict[str, Any]] = []

    for key, label, weight in _MODULE_WEIGHTS:
        complete = _has_data(state, key)
        if complete:
            completed_weight += weight
        else:
            missing.append({
                "module": key,
                "label": label,
                "action": _MODULE_ACTIONS.get(key, f"Complete {label} to improve score"),
                "weight": weight,
            })
        breakdown[label] = complete

    score = int((completed_weight / total_weight * 100) if total_weight else 0)

    # Letter grade
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    return score, grade, breakdown, missing


def readiness_color(score: float) -> str:
    """Return a CSS color for the readiness gauge."""
    if score >= 80:
        return "#28a745"  # green
    if score >= 50:
        return "#ffc107"  # amber
    return "#dc3545"  # red


def readiness_label(score: float) -> str:
    """Return a human-readable label for readiness."""
    if score >= 90:
        return "Trial Ready"
    if score >= 70:
        return "Substantially Prepared"
    if score >= 50:
        return "In Progress"
    if score >= 25:
        return "Early Stage"
    return "Not Started"
