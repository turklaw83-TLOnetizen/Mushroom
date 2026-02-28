# ---- Draft Quality Score ---------------------------------------------------
# Computes a 0-100% quality score for a major document draft, modeled after
# core/readiness.py.  Evaluates outline completeness, section depth, citation
# coverage, placeholder elimination, structural balance, and review status.

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Weights for each criterion (out of 100 total)
_DRAFT_WEIGHTS: List[Tuple[str, str, float]] = [
    # (check_key, label, weight)
    ("outline_complete", "Outline Approved (3+ sections)", 10),
    ("all_sections_drafted", "All Sections Drafted", 20),
    ("no_placeholders", "No Placeholders Remaining", 15),
    ("citation_library_built", "Citation Library (3+ entries)", 10),
    ("citations_used", "Citations Used in Text", 10),
    ("section_balance", "Balanced Section Lengths", 5),
    ("min_section_length", "Section Depth (>500 chars each)", 10),
    ("table_of_authorities", "Table of Authorities Ready", 5),
    ("attorney_info_complete", "Attorney Info Complete", 5),
    ("review_completed", "AI Review Completed", 10),
]


def _check(draft: Dict, key: str) -> bool:
    """Evaluate a single quality criterion."""
    outline = draft.get("outline", [])
    sections = draft.get("sections", [])
    citations = draft.get("citation_library", [])

    if key == "outline_complete":
        return len(outline) >= 3

    if key == "all_sections_drafted":
        if not outline:
            return False
        drafted_nums = {s.get("section_num") for s in sections}
        return all(o.get("section_num") in drafted_nums for o in outline)

    if key == "no_placeholders":
        if not sections:
            return False
        all_text = " ".join(s.get("content", "") for s in sections)
        return not re.search(r'\[([A-Z][A-Z\s]+)\]', all_text)

    if key == "citation_library_built":
        return len(citations) >= 3

    if key == "citations_used":
        if not sections or not citations:
            return False
        cite_names = [c.get("case_name", "").lower() for c in citations if c.get("case_name")]
        sections_with_cites = 0
        for s in sections:
            content_lower = s.get("content", "").lower()
            if any(cn in content_lower for cn in cite_names):
                sections_with_cites += 1
        return sections_with_cites >= len(sections) * 0.5

    if key == "section_balance":
        if len(sections) < 2:
            return False
        lengths = [len(s.get("content", "")) for s in sections]
        min_len = min(lengths) if lengths else 0
        max_len = max(lengths) if lengths else 0
        if min_len == 0:
            return False
        return max_len <= min_len * 3

    if key == "min_section_length":
        if not sections:
            return False
        return all(len(s.get("content", "")) >= 500 for s in sections)

    if key == "table_of_authorities":
        # Can we generate a TOA? Need citations found in section text.
        if not citations or not sections:
            return False
        all_text = " ".join(s.get("content", "") for s in sections).lower()
        return any(
            c.get("case_name", "").lower() in all_text
            for c in citations if c.get("case_name")
        )

    if key == "attorney_info_complete":
        atty = draft.get("attorney_info", {})
        return bool(atty.get("name")) and bool(atty.get("bar_number"))

    if key == "review_completed":
        return bool(draft.get("review_results"))

    return False


def compute_draft_quality_score(draft: Dict) -> Tuple[int, str, Dict[str, bool]]:
    """Compute draft quality score, letter grade, and per-criterion breakdown.

    Returns:
        (score, grade, breakdown) where:
            score: int 0-100
            grade: str letter grade (A+/A/B/C/D/F)
            breakdown: {label: bool} per criterion
    """
    completed_weight = 0.0
    total_weight = sum(w for _, _, w in _DRAFT_WEIGHTS)
    breakdown: Dict[str, bool] = {}

    for key, label, weight in _DRAFT_WEIGHTS:
        passed = _check(draft, key)
        if passed:
            completed_weight += weight
        breakdown[label] = passed

    score = int((completed_weight / total_weight * 100) if total_weight else 0)

    if score >= 95:
        grade = "A+"
    elif score >= 85:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return score, grade, breakdown


def quality_color(score: int) -> str:
    """Return a CSS color for the quality score."""
    if score >= 80:
        return "#28a745"
    if score >= 50:
        return "#ffc107"
    return "#dc3545"
