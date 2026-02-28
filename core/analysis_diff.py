"""
analysis_diff.py -- Analysis State Comparison & Diff
Compare two analysis snapshots and generate structured diffs with HTML rendering.
"""

import difflib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Keys to compare across analysis states
COMPARE_KEYS = [
    "case_summary", "strategy_notes", "devils_advocate_notes",
    "research_summary", "deposition_analysis",
]

COMPARE_LIST_KEYS = [
    "witnesses", "timeline", "evidence_foundations", "consistency_check",
    "legal_elements", "investigation_plan", "cross_examination_plan",
    "direct_examination_plan", "entities", "relationships",
    "mock_jury_feedback", "legal_research_data",
]

COMPARE_DICT_KEYS = [
    "voir_dire",
]

# Human-readable labels
KEY_LABELS = {
    "case_summary": "Case Summary",
    "strategy_notes": "Strategy Notes",
    "devils_advocate_notes": "Devil's Advocate",
    "research_summary": "Research Summary",
    "deposition_analysis": "Deposition Analysis",
    "witnesses": "Witnesses",
    "timeline": "Timeline",
    "evidence_foundations": "Evidence Foundations",
    "consistency_check": "Consistency Check",
    "legal_elements": "Legal Elements",
    "investigation_plan": "Investigation Plan",
    "cross_examination_plan": "Cross-Examination Plan",
    "direct_examination_plan": "Direct Examination Plan",
    "entities": "Entities",
    "relationships": "Relationships",
    "mock_jury_feedback": "Mock Jury Feedback",
    "legal_research_data": "Legal Research",
    "voir_dire": "Voir Dire",
}


def diff_analysis_states(old_state: Dict, new_state: Dict) -> Dict[str, Dict]:
    """
    Compare two analysis states and return structured diff.
    
    Returns:
        {key: {"status": "added"|"removed"|"modified"|"unchanged",
               "old": old_value, "new": new_value,
               "old_len": int, "new_len": int, "delta": int,
               "diff_lines": [unified diff lines]}}
    """
    changes = {}
    all_keys = COMPARE_KEYS + COMPARE_LIST_KEYS + COMPARE_DICT_KEYS
    
    for key in all_keys:
        old_val = old_state.get(key)
        new_val = new_state.get(key)
        old_exists = bool(old_val)
        new_exists = bool(new_val)
        
        if not old_exists and not new_exists:
            continue
        
        old_str = _stringify(old_val)
        new_str = _stringify(new_val)
        
        if not old_exists and new_exists:
            changes[key] = {
                "status": "added",
                "old": None,
                "new": new_val,
                "old_len": 0,
                "new_len": len(new_str),
                "delta": len(new_str),
                "diff_lines": [],
            }
        elif old_exists and not new_exists:
            changes[key] = {
                "status": "removed",
                "old": old_val,
                "new": None,
                "old_len": len(old_str),
                "new_len": 0,
                "delta": -len(old_str),
                "diff_lines": [],
            }
        elif old_str != new_str:
            diff_lines = list(difflib.unified_diff(
                old_str.splitlines(keepends=True),
                new_str.splitlines(keepends=True),
                fromfile="Previous",
                tofile="Current",
                lineterm="",
            ))
            changes[key] = {
                "status": "modified",
                "old": old_val,
                "new": new_val,
                "old_len": len(old_str),
                "new_len": len(new_str),
                "delta": len(new_str) - len(old_str),
                "diff_lines": diff_lines,
            }
    
    return changes


def generate_diff_summary(changes: Dict[str, Dict]) -> Dict:
    """Generate a summary of all changes."""
    added = [k for k, v in changes.items() if v["status"] == "added"]
    removed = [k for k, v in changes.items() if v["status"] == "removed"]
    modified = [k for k, v in changes.items() if v["status"] == "modified"]
    
    total_added_chars = sum(v["new_len"] for v in changes.values() if v["status"] == "added")
    total_delta = sum(v["delta"] for v in changes.values())
    
    return {
        "total_changes": len(changes),
        "added": added,
        "removed": removed,
        "modified": modified,
        "total_added_chars": total_added_chars,
        "total_delta": total_delta,
    }


def generate_html_diff(old_text: str, new_text: str, context_lines: int = 3) -> str:
    """Generate an HTML diff with color coding."""
    differ = difflib.HtmlDiff(wrapcolumn=80)
    try:
        return differ.make_table(
            old_text.splitlines(),
            new_text.splitlines(),
            fromdesc="Previous Version",
            todesc="Current Version",
            context=True,
            numlines=context_lines,
        )
    except Exception:
        # Fallback to unified diff
        lines = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            lineterm="",
        )
        return "\n".join(lines)


def count_new_citations(old_state: Dict, new_state: Dict) -> Tuple[int, int]:
    """Count citations added and removed between two states."""
    from core.relevance import extract_citations_from_state
    
    old_citations = extract_citations_from_state(old_state)
    new_citations = extract_citations_from_state(new_state)
    
    added = sum((new_citations - old_citations).values())
    removed = sum((old_citations - new_citations).values())
    
    return added, removed


def _stringify(value: Any) -> str:
    """Convert any value to a string for comparison."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, dict):
        return str(value)
    return str(value)
