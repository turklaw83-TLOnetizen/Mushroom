# ---- Readiness Score Computation ------------------------------------------
# Extracted from app.py.  Computes a 0-100% "trial readiness" score based on
# which analysis modules have produced data.

import logging
from typing import Dict, List, Optional, Tuple

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


def compute_readiness_score(state: Dict) -> Tuple[int, str, Dict[str, bool]]:
    """
    Compute the readiness score, letter grade, and per-module breakdown.

    Returns:
        (score, grade, breakdown) where:
            score: int 0-100
            grade: str letter grade (A/B/C/D/F)
            breakdown: {label: bool} for each module
    """
    completed_weight = 0.0
    total_weight = sum(w for _, _, w in _MODULE_WEIGHTS)
    breakdown: Dict[str, bool] = {}

    for key, label, weight in _MODULE_WEIGHTS:
        complete = _has_data(state, key)
        if complete:
            completed_weight += weight
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

    return score, grade, breakdown


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
