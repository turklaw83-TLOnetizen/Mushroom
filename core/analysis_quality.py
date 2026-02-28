# ---- Analysis Quality / Confidence Scoring --------------------------------
# Heuristic scoring of analysis module outputs to help attorneys
# gauge where human review is most needed.

import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex for [[source: filename.pdf, p.X]] citations
_CITATION_RE = re.compile(r"\[\[source:\s*(.+?)(?:,\s*p\.?\s*(\d+))?\s*\]\]")

# Module keys mapped to their output state keys
MODULE_OUTPUT_KEYS = {
    "case_summary": "case_summary",
    "strategy_notes": "strategy_notes",
    "legal_elements": "legal_elements",
    "investigation_plan": "investigation_plan",
    "consistency_check": "consistency_check",
    "research_summary": "research_summary",
    "devils_advocate_notes": "devils_advocate_notes",
    "entities": "entities",
    "cross_examination_plan": "cross_examination_plan",
    "direct_examination_plan": "direct_examination_plan",
    "timeline": "timeline",
    "evidence_foundations": "evidence_foundations",
    "voir_dire": "voir_dire",
    "mock_jury_feedback": "mock_jury_feedback",
}

MODULE_LABELS = {
    "case_summary": "Case Summary",
    "strategy_notes": "Strategy",
    "legal_elements": "Legal Elements",
    "investigation_plan": "Investigation Plan",
    "consistency_check": "Consistency Check",
    "research_summary": "Legal Research",
    "devils_advocate_notes": "Devil's Advocate",
    "entities": "Entities",
    "cross_examination_plan": "Cross-Examination",
    "direct_examination_plan": "Direct Examination",
    "timeline": "Timeline",
    "evidence_foundations": "Evidence Foundations",
    "voir_dire": "Voir Dire",
    "mock_jury_feedback": "Mock Jury",
}


def _stringify(val) -> str:
    """Convert any value to string for analysis."""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, dict)):
        return json.dumps(val, default=str)
    return str(val) if val else ""


def score_module_confidence(
    module_key: str,
    state: dict,
    case_files: Optional[List[str]] = None,
) -> Dict:
    """
    Score a single module's output quality (0-100).

    Factors:
        - Text length (0-30): Penalize very short outputs
        - Citation density (0-30): Citations relative to output length
        - Document coverage (0-20): % of case files cited
        - Structure (0-20): Headers, bullets, numbered lists

    Returns:
        {"score": 0-100, "label": "Strong|Moderate|Weak",
         "factors": {"length": N, "citations": N, "coverage": N, "structure": N}}
    """
    output_key = MODULE_OUTPUT_KEYS.get(module_key, module_key)
    raw_val = state.get(output_key)

    if not raw_val:
        return {
            "score": 0, "label": "Missing", "color": "red",
            "factors": {"length": 0, "citations": 0, "coverage": 0, "structure": 0},
        }

    text = _stringify(raw_val)
    text_len = len(text)

    # ---- Factor 1: Text Length (0-30) ----
    if text_len < 100:
        length_score = 0
    elif text_len < 300:
        length_score = 5
    elif text_len < 800:
        length_score = 15
    elif text_len < 2000:
        length_score = 25
    else:
        length_score = 30

    # ---- Factor 2: Citation Density (0-30) ----
    citations = _CITATION_RE.findall(text)
    n_citations = len(citations)
    if n_citations == 0:
        citation_score = 0
    elif n_citations <= 2:
        citation_score = 10
    elif n_citations <= 5:
        citation_score = 20
    else:
        citation_score = 30

    # ---- Factor 3: Document Coverage (0-20) ----
    cited_files = set(c[0].strip() for c in citations)
    if case_files and len(case_files) > 0:
        coverage_pct = len(cited_files) / len(case_files)
        coverage_score = int(min(coverage_pct * 40, 20))  # 50% coverage = full score
    else:
        coverage_score = 10 if n_citations > 0 else 0

    # ---- Factor 4: Structure (0-20) ----
    structure_score = 0
    # Check for headers (##, **Bold**)
    if re.search(r"(^|\n)#{1,3}\s", text) or re.search(r"\*\*.+?\*\*", text):
        structure_score += 7
    # Check for bullet points or numbered lists
    if re.search(r"(^|\n)\s*[-•*]\s", text) or re.search(r"(^|\n)\s*\d+[.)]\s", text):
        structure_score += 7
    # Check for multiple paragraphs/sections
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        structure_score += 6

    # ---- Final Score ----
    total = min(100, length_score + citation_score + coverage_score + structure_score)

    if total >= 70:
        label = "Strong"
        color = "green"
    elif total >= 40:
        label = "Moderate"
        color = "yellow"
    else:
        label = "Weak"
        color = "red"

    return {
        "score": total,
        "label": label,
        "color": color,
        "factors": {
            "length": length_score,
            "citations": citation_score,
            "coverage": coverage_score,
            "structure": structure_score,
        },
    }


def score_all_modules(
    state: dict,
    case_files: Optional[List[str]] = None,
) -> Dict[str, Dict]:
    """
    Score all analysis modules.

    Returns:
        {module_key: {"score": N, "label": "Strong|Moderate|Weak", ...}}
    """
    scores = {}
    for key in MODULE_OUTPUT_KEYS:
        if state.get(MODULE_OUTPUT_KEYS[key]):
            scores[key] = score_module_confidence(key, state, case_files)
    return scores


def get_weak_modules(state: dict, case_files=None, threshold: int = 40) -> List[str]:
    """Return list of module keys with scores below threshold."""
    scores = score_all_modules(state, case_files)
    return [k for k, v in scores.items() if v["score"] < threshold]
