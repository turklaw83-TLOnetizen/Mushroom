# ---- Document Relevance Scoring -------------------------------------------
# Computes per-file relevance scores from citation frequency in analysis outputs.
# Zero additional API cost -- all data comes from existing analysis results.

import json
import logging
import os
import re
from collections import Counter
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex matching [[source: filename.pdf, p.X]] citations
_CITATION_RE = re.compile(r"\[\[source:\s*(.+?)(?:,\s*p\.?\s*(\d+))?\s*\]\]")

# All analysis state keys that contain citation-bearing text (strings)
CITATION_FIELDS = [
    "case_summary",
    "strategy_notes",
    "devils_advocate_notes",
    "research_summary",
    "deposition_analysis",
]

# Fields that are lists of dicts -- stringify each item to find citations
CITATION_LIST_FIELDS = [
    "witnesses",
    "timeline",
    "evidence_foundations",
    "consistency_check",
    "legal_elements",
    "investigation_plan",
    "cross_examination_plan",
    "direct_examination_plan",
    "entities",
    "relationships",
    "mock_jury_feedback",
    "legal_research_data",
]

# Fields that are dicts -- stringify the whole dict
CITATION_DICT_FIELDS = [
    "voir_dire",
]

# Tag-based boost by case type: {case_type: {tag: boost_points}}
TAG_BOOSTS = {
    "criminal": {
        "Police Report": 15,
        "Witness Statement": 10,
        "Deposition": 8,
        "Medical Records": 5,
        "Photos/Video": 5,
        "Expert Report": 5,
        "Discovery": 3,
    },
    "criminal-juvenile": {
        "Police Report": 15,
        "Witness Statement": 10,
        "Medical Records": 8,
        "Expert Report": 5,
    },
    "civil-plaintiff": {
        "Medical Records": 15,
        "Contract/Agreement": 12,
        "Financial Records": 10,
        "Expert Report": 8,
        "Deposition": 8,
        "Correspondence": 5,
    },
    "civil-defendant": {
        "Contract/Agreement": 12,
        "Correspondence": 10,
        "Financial Records": 8,
        "Deposition": 8,
        "Expert Report": 5,
    },
    "civil-juvenile": {
        "Medical Records": 12,
        "Expert Report": 10,
        "Correspondence": 8,
    },
}


def extract_citations_from_state(state: dict) -> Counter:
    """
    Scan all analysis output fields for [[source: ...]] citations.
    Returns a Counter of {filename: citation_count}.
    """
    counts: Counter = Counter()

    # String fields
    for field in CITATION_FIELDS:
        text = state.get(field, "")
        if isinstance(text, str) and text:
            for match in _CITATION_RE.finditer(text):
                counts[match.group(1).strip()] += 1

    # List-of-dict fields
    for field in CITATION_LIST_FIELDS:
        items = state.get(field, [])
        if isinstance(items, list):
            for item in items:
                text = json.dumps(item) if isinstance(item, dict) else str(item)
                for match in _CITATION_RE.finditer(text):
                    counts[match.group(1).strip()] += 1

    # Dict fields
    for field in CITATION_DICT_FIELDS:
        item = state.get(field, {})
        if isinstance(item, dict) and item:
            text = json.dumps(item)
            for match in _CITATION_RE.finditer(text):
                counts[match.group(1).strip()] += 1

    return counts


def compute_relevance_scores(
    state: dict,
    file_tags: Dict[str, List[str]],
    case_type: str = "criminal",
) -> Dict[str, dict]:
    """
    Compute per-file relevance scores from citation frequency + tag boosts.

    Returns:
        {filename: {"score": 0-100, "citations": N, "boost": N}}
    """
    citation_counts = extract_citations_from_state(state)

    if not citation_counts:
        return {}

    max_count = max(citation_counts.values())
    boosts = TAG_BOOSTS.get(case_type, TAG_BOOSTS.get("criminal", {}))

    scores: Dict[str, dict] = {}
    for filename, count in citation_counts.items():
        # Normalize citation count to 0-85 range
        base_score = int((count / max(max_count, 1)) * 85)

        # Tag boost: up to 15 points
        tags = file_tags.get(filename, [])
        tag_boost = 0
        for tag in tags:
            tag_boost = max(tag_boost, boosts.get(tag, 0))

        final_score = min(100, base_score + tag_boost)
        scores[filename] = {
            "score": final_score,
            "citations": count,
            "boost": tag_boost,
        }

    return scores


# ---- Per-Node Citation Mapping (for Incremental Analysis) ------------------

# Maps analysis node names to the state keys they produce
_NODE_OUTPUT_KEYS = {
    "analyzer": ["case_summary"],
    "strategist": ["strategy_notes"],
    "elements_mapper": ["legal_elements"],
    "investigation_planner": ["investigation_plan"],
    "consistency_checker": ["consistency_check"],
    "legal_researcher": ["research_summary", "legal_research_data"],
    "devils_advocate": ["devils_advocate_notes"],
    "entity_extractor": ["entities", "relationships"],
    "cross_examiner": ["cross_examination_plan"],
    "direct_examiner": ["direct_examination_plan"],
    "timeline_generator": ["timeline"],
    "foundations_agent": ["evidence_foundations"],
    "voir_dire_agent": ["voir_dire"],
    "mock_jury": ["mock_jury_feedback"],
}


def extract_per_node_citations(state: dict) -> Dict[str, set]:
    """
    Extract citations per analysis node.
    Returns {node_name: set_of_filenames_cited}.
    """
    result: Dict[str, set] = {}

    for node_name, keys in _NODE_OUTPUT_KEYS.items():
        filenames: set = set()
        for key in keys:
            val = state.get(key)
            if not val:
                continue
            if isinstance(val, str):
                text = val
            elif isinstance(val, list):
                text = json.dumps(val)
            elif isinstance(val, dict):
                text = json.dumps(val)
            else:
                continue
            for match in _CITATION_RE.finditer(text):
                filenames.add(match.group(1).strip())
        if filenames:
            result[node_name] = filenames

    return result


def files_to_nodes(per_node_citations: Dict[str, set]) -> Dict[str, set]:
    """
    Invert per-node citations to get {filename: set_of_nodes_that_cite_it}.
    """
    result: Dict[str, set] = {}
    for node_name, filenames in per_node_citations.items():
        for fn in filenames:
            result.setdefault(fn, set()).add(node_name)
    return result


def compute_affected_nodes(
    changed_files: set,
    state: dict,
) -> set:
    """
    Given a set of changed filenames, compute which analysis nodes need re-running.
    Always includes 'analyzer' and 'strategist' (core nodes).
    """
    per_node = extract_per_node_citations(state)
    file_node_map = files_to_nodes(per_node)

    affected = {"analyzer", "strategist"}  # Always re-run core nodes
    for fn in changed_files:
        nodes = file_node_map.get(fn, set())
        affected.update(nodes)

    return affected


def save_relevance_scores(
    data_dir: str, case_id: str, prep_id: str, scores: dict,
) -> None:
    """Save relevance scores to file_relevance.json in the prep directory."""
    prep_dir = os.path.join(data_dir, "cases", case_id, "preparations", prep_id)
    os.makedirs(prep_dir, exist_ok=True)
    path = os.path.join(prep_dir, "file_relevance.json")
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("Error saving relevance scores: %s", e)


def load_relevance_scores(
    data_dir: str, case_id: str, prep_id: str,
) -> Dict[str, dict]:
    """Load relevance scores from file_relevance.json. Returns empty dict if none."""
    path = os.path.join(
        data_dir, "cases", case_id, "preparations", prep_id, "file_relevance.json",
    )
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
