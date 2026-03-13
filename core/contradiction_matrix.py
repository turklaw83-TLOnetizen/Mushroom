# ---- Cross-Document Contradiction Matrix ---------------------------------
# Systematically compares all meaningful document pairs in a case to find
# contradictions, inconsistencies, timeline discrepancies, and omissions.
#
# Three phases:
#   1. Document Inventory & Classification  (1 LLM call per document)
#   2. Smart Pair Selection                 (pure logic, no LLM)
#   3. Pairwise Deep Comparison             (1 LLM call per pair)
#
# Storage: data/cases/{case_id}/contradiction_matrix/{prep_id}.json

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm, invoke_with_retry
from core.nodes._common import extract_json
from core.citations import CITATION_INSTRUCTION, format_docs_with_sources
from core.state import get_case_context
from core.ingest import auto_classify_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Document types that should always be compared against each other when both
# appear in a case.  Keys and values are auto_classify_file tag strings.
_HIGH_PRIORITY_PAIRS = {
    ("Police Report", "Witness Statement"),
    ("Police Report", "Deposition"),
    ("Witness Statement", "Deposition"),
    ("Witness Statement", "Witness Statement"),
    ("Police Report", "Medical Records"),
    ("Deposition", "Medical Records"),
    ("Expert Report", "Medical Records"),
    ("Expert Report", "Police Report"),
    ("Court Filing", "Deposition"),
}

# Types that are unlikely to contradict each other and can be skipped.
_SKIP_PAIR_TYPES = {
    ("Photos/Video", "Photos/Video"),
    ("Photos/Video", "Financial Records"),
    ("Financial Records", "Financial Records"),
}

# Maximum number of comparison pairs to avoid runaway LLM costs.
MAX_PAIRS = 120

# Character budget per document sent to the LLM for key-claims extraction.
_CLAIMS_DOC_CHAR_LIMIT = 6000

# Character budget per document in pairwise comparison.
_PAIR_DOC_CHAR_LIMIT = 8000


# ---------------------------------------------------------------------------
# Phase 1 -- Document Inventory & Classification
# ---------------------------------------------------------------------------

def _collect_documents_by_source(raw_documents: list) -> Dict[str, dict]:
    """Group raw LangChain Document objects by source filename.

    Returns a dict keyed by basename:
        {filename: {"content": str, "page_count": int, "sources": [str]}}
    Merges all chunks from the same source file into a single content string.
    """
    by_source: Dict[str, dict] = {}

    for doc in raw_documents:
        meta = doc.metadata if hasattr(doc, "metadata") else {}
        source = meta.get("source", "Unknown")
        basename = os.path.basename(source) if source else "Unknown"
        content = doc.page_content if hasattr(doc, "page_content") else str(doc)
        page = meta.get("page")

        if basename not in by_source:
            by_source[basename] = {
                "content": "",
                "pages": set(),
                "full_source": source,
            }

        by_source[basename]["content"] += content + "\n"
        if page is not None:
            by_source[basename]["pages"].add(page)

    return by_source


def _extract_key_claims(
    llm,
    filename: str,
    content: str,
    doc_tag: Optional[str],
) -> dict:
    """Use a SHORT LLM call to extract 3-5 key factual claims and entities.

    Returns:
        {"claims": [...], "people": [...], "dates": [...], "locations": [...]}
    Falls back to empty lists on parse failure.
    """
    truncated = content[:_CLAIMS_DOC_CHAR_LIMIT]

    tag_hint = f" (classified as: {doc_tag})" if doc_tag else ""
    prompt = f"""Extract the key factual claims from this document.

Document: {filename}{tag_hint}

{truncated}

Return a JSON object:
{{
    "claims": ["3 to 5 most important factual assertions in this document"],
    "people": ["every person name mentioned"],
    "dates": ["every date or time reference mentioned"],
    "locations": ["every location or address mentioned"]
}}

Be precise. Only include information explicitly stated in the document.
Return ONLY the JSON object."""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        parsed = extract_json(response.content)
        if isinstance(parsed, dict):
            return {
                "claims": parsed.get("claims", [])[:7],
                "people": parsed.get("people", []),
                "dates": parsed.get("dates", []),
                "locations": parsed.get("locations", []),
            }
    except Exception as exc:
        logger.warning("Key-claims extraction failed for %s: %s", filename, exc)

    return {"claims": [], "people": [], "dates": [], "locations": []}


def build_document_inventory(
    state: dict,
    on_progress: Optional[Callable] = None,
) -> List[dict]:
    """Phase 1: Build a classified inventory of all case documents.

    For each unique document in ``state['raw_documents']``:
      - Classifies it via ``auto_classify_file``
      - Extracts key factual claims, people, dates, locations via one LLM call

    Args:
        state: The analysis state dict (needs ``raw_documents``, ``current_model``).
        on_progress: Optional ``(phase, current, total, detail)`` callback.

    Returns:
        List of inventory dicts, one per unique source file::

            [{
                "index": 0,
                "filename": "police_report.pdf",
                "auto_tag": "Police Report",
                "word_count": 2345,
                "page_count": 4,
                "key_claims": [...],
                "people": [...],
                "dates": [...],
                "locations": [...],
            }, ...]
    """
    raw_docs = state.get("raw_documents", [])
    if not raw_docs:
        logger.warning("No raw_documents in state -- inventory is empty")
        return []

    llm = get_llm(state.get("current_model"), max_output_tokens=2048)
    if not llm:
        logger.error("Cannot build inventory: LLM unavailable")
        return []

    docs_by_source = _collect_documents_by_source(raw_docs)
    total = len(docs_by_source)
    inventory: List[dict] = []

    for idx, (filename, info) in enumerate(docs_by_source.items()):
        if on_progress:
            on_progress("inventory", idx + 1, total, filename)

        content = info["content"]
        first_page_text = content[:500]
        auto_tag = auto_classify_file(filename, first_page_text)
        word_count = len(content.split())

        # Extract key claims via LLM
        claims_data = _extract_key_claims(llm, filename, content, auto_tag)

        inventory.append({
            "index": idx,
            "filename": filename,
            "auto_tag": auto_tag,
            "word_count": word_count,
            "page_count": len(info["pages"]) or 1,
            "key_claims": claims_data.get("claims", []),
            "people": claims_data.get("people", []),
            "dates": claims_data.get("dates", []),
            "locations": claims_data.get("locations", []),
        })

    logger.info(
        "Document inventory built: %d documents, %d total claims",
        len(inventory),
        sum(len(d["key_claims"]) for d in inventory),
    )
    return inventory


# ---------------------------------------------------------------------------
# Phase 2 -- Smart Pair Selection
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse inner spaces."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _entity_overlap(doc_a: dict, doc_b: dict) -> bool:
    """Return True if two documents share at least one person entity."""
    people_a = {_normalize_name(p) for p in doc_a.get("people", []) if len(p) > 2}
    people_b = {_normalize_name(p) for p in doc_b.get("people", []) if len(p) > 2}
    return bool(people_a & people_b)


def _date_overlap(doc_a: dict, doc_b: dict) -> bool:
    """Return True if two documents reference any of the same dates."""
    dates_a = {_normalize_name(d) for d in doc_a.get("dates", []) if len(d) > 3}
    dates_b = {_normalize_name(d) for d in doc_b.get("dates", []) if len(d) > 3}
    return bool(dates_a & dates_b)


def _tag_pair(tag_a: Optional[str], tag_b: Optional[str]) -> Tuple[str, str]:
    """Return a canonical sorted tag pair for lookup."""
    a = tag_a or "Unknown"
    b = tag_b or "Unknown"
    return (min(a, b), max(a, b))


def select_comparison_pairs(inventory: List[dict]) -> List[Tuple[int, int]]:
    """Phase 2: Select which document pairs to compare.

    Selection strategy (NOT brute force):
      - Always compare high-priority tag pairs (police reports vs witness
        statements, depositions vs everything, etc.)
      - Always compare documents that mention the same person
      - Always compare documents that reference the same dates
      - Skip photo-vs-photo and similar low-value pairs
      - Cap total pairs at ``MAX_PAIRS`` to control cost

    Args:
        inventory: Output of ``build_document_inventory()``.

    Returns:
        List of ``(index_a, index_b)`` tuples referencing inventory indices.
    """
    if len(inventory) < 2:
        return []

    selected: set = set()
    n = len(inventory)

    for i in range(n):
        for j in range(i + 1, n):
            doc_a = inventory[i]
            doc_b = inventory[j]

            tag_a = doc_a.get("auto_tag")
            tag_b = doc_b.get("auto_tag")
            pair_tags = _tag_pair(tag_a, tag_b)

            # Skip known low-value type combinations
            if pair_tags in _SKIP_PAIR_TYPES:
                continue

            should_compare = False

            # Rule 1: High-priority tag pair
            if pair_tags in _HIGH_PRIORITY_PAIRS:
                should_compare = True

            # Rule 2: Depositions compared against everything
            if tag_a == "Deposition" or tag_b == "Deposition":
                should_compare = True

            # Rule 3: Shared person entities
            if _entity_overlap(doc_a, doc_b):
                should_compare = True

            # Rule 4: Shared date references
            if _date_overlap(doc_a, doc_b):
                should_compare = True

            # Rule 5: Both are witness statements (different witnesses)
            if tag_a == "Witness Statement" and tag_b == "Witness Statement":
                should_compare = True

            # Rule 6: Police report vs any substantive document
            if tag_a == "Police Report" or tag_b == "Police Report":
                other_tag = tag_b if tag_a == "Police Report" else tag_a
                if other_tag not in ("Photos/Video", "Financial Records"):
                    should_compare = True

            if should_compare:
                selected.add((i, j))

            if len(selected) >= MAX_PAIRS:
                break
        if len(selected) >= MAX_PAIRS:
            break

    # If very few pairs selected and we have room, add remaining non-skip pairs
    if len(selected) < 10 and n > 2:
        for i in range(n):
            for j in range(i + 1, n):
                if (i, j) in selected:
                    continue
                tag_a = inventory[i].get("auto_tag")
                tag_b = inventory[j].get("auto_tag")
                if _tag_pair(tag_a, tag_b) not in _SKIP_PAIR_TYPES:
                    selected.add((i, j))
                if len(selected) >= MAX_PAIRS:
                    break
            if len(selected) >= MAX_PAIRS:
                break

    pairs = sorted(selected)
    logger.info(
        "Pair selection: %d pairs from %d documents (brute force would be %d)",
        len(pairs), n, n * (n - 1) // 2,
    )
    return pairs


# ---------------------------------------------------------------------------
# Phase 3 -- Pairwise Deep Comparison
# ---------------------------------------------------------------------------

def compare_document_pair(
    state: dict,
    doc_a: dict,
    doc_b: dict,
    doc_a_content: str,
    doc_b_content: str,
) -> dict:
    """Phase 3: Deep comparison of two documents.

    Uses one LLM call to find contradictions, timeline discrepancies,
    omissions, and corroborations between the two documents.

    Args:
        state: Analysis state dict (for ``current_model``, case context).
        doc_a: Inventory entry for document A.
        doc_b: Inventory entry for document B.
        doc_a_content: Full text of document A (pre-truncated).
        doc_b_content: Full text of document B (pre-truncated).

    Returns:
        Comparison result dict with keys: ``doc_a``, ``doc_b``,
        ``relationship``, ``contradictions``, ``timeline_discrepancies``,
        ``omissions``, ``corroborations``.
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return _empty_comparison(doc_a["filename"], doc_b["filename"], "LLM unavailable")

    ctx = get_case_context(state)
    case_summary = state.get("case_summary", "")

    doc_a_name = doc_a["filename"]
    doc_b_name = doc_b["filename"]
    tag_a = doc_a.get("auto_tag") or "unclassified"
    tag_b = doc_b.get("auto_tag") or "unclassified"

    prompt = f"""You are a meticulous {ctx['role']} performing a DEEP DOCUMENT COMPARISON.

Your task is to compare these two documents and identify EVERY contradiction, inconsistency,
discrepancy, and omission between them. This is critical for impeachment and trial preparation.

{ctx['directives_block']}

{CITATION_INSTRUCTION}

=== DOCUMENT A: {doc_a_name} ({tag_a}) ===
{doc_a_content[:_PAIR_DOC_CHAR_LIMIT]}

=== DOCUMENT B: {doc_b_name} ({tag_b}) ===
{doc_b_content[:_PAIR_DOC_CHAR_LIMIT]}

CASE CONTEXT:
{str(case_summary)[:2000]}

Return a JSON object:
{{
    "doc_a": "{doc_a_name}",
    "doc_b": "{doc_b_name}",
    "relationship": "contradicts | supports | supplements | mixed",
    "contradictions": [
        {{
            "id": 1,
            "category": "factual | temporal | identity | quantity | sequence | omission",
            "doc_a_says": "What Document A states (include page reference if available)",
            "doc_b_says": "What Document B states (include page reference if available)",
            "severity": "critical | significant | minor",
            "impeachment_value": "high | medium | low",
            "explanation": "Why this matters and how it could be used at trial",
            "suggested_question": "A question to ask about this contradiction in cross-exam"
        }}
    ],
    "timeline_discrepancies": [
        {{
            "event": "What event has a timeline issue",
            "doc_a_time": "Time/date per Document A",
            "doc_b_time": "Time/date per Document B",
            "gap": "Duration of discrepancy",
            "significance": "Why this matters"
        }}
    ],
    "omissions": [
        {{
            "present_in": "doc_a or doc_b",
            "missing_from": "doc_a or doc_b",
            "detail": "What information is present in one but absent from the other",
            "significance": "Why this omission matters"
        }}
    ],
    "corroborations": [
        {{
            "fact": "What fact both documents agree on",
            "significance": "Why this agreement matters"
        }}
    ]
}}

RULES:
- Be EXTREMELY thorough -- check dates, times, names, quantities, sequences
- Even small discrepancies can be valuable for impeachment
- Note when one document OMITS something present in the other
- Identify which contradictions are most useful for {ctx['our_side']}
- Include specific page or line references where possible
- If NO contradictions exist, return an empty contradictions array
- Suggest specific cross-examination questions for key contradictions

Return ONLY the JSON object, no markdown fences."""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        parsed = extract_json(response.content)
        if isinstance(parsed, dict):
            # Ensure required fields
            parsed.setdefault("doc_a", doc_a_name)
            parsed.setdefault("doc_b", doc_b_name)
            parsed.setdefault("relationship", "mixed")
            parsed.setdefault("contradictions", [])
            parsed.setdefault("timeline_discrepancies", [])
            parsed.setdefault("omissions", [])
            parsed.setdefault("corroborations", [])
            return parsed
        else:
            logger.warning(
                "Failed to parse comparison JSON for %s vs %s",
                doc_a_name, doc_b_name,
            )
            return _empty_comparison(
                doc_a_name, doc_b_name,
                "JSON parse failed",
                raw_output=response.content,
            )
    except Exception as exc:
        logger.error(
            "LLM comparison failed for %s vs %s: %s",
            doc_a_name, doc_b_name, exc,
        )
        return _empty_comparison(doc_a_name, doc_b_name, str(exc))


def _empty_comparison(
    doc_a_name: str,
    doc_b_name: str,
    error: str,
    raw_output: str = "",
) -> dict:
    """Return a stub comparison result when an error occurs."""
    result = {
        "doc_a": doc_a_name,
        "doc_b": doc_b_name,
        "relationship": "unknown",
        "contradictions": [],
        "timeline_discrepancies": [],
        "omissions": [],
        "corroborations": [],
        "error": error,
    }
    if raw_output:
        result["_raw_output"] = raw_output
    return result


# ---------------------------------------------------------------------------
# Aggregation Helpers
# ---------------------------------------------------------------------------

def _aggregate_by_severity(matrix: List[dict]) -> Dict[str, list]:
    """Group all contradictions across all pairs by severity level."""
    by_severity: Dict[str, list] = {"critical": [], "significant": [], "minor": []}
    for pair in matrix:
        doc_a = pair.get("doc_a", "?")
        doc_b = pair.get("doc_b", "?")
        for c in pair.get("contradictions", []):
            severity = c.get("severity", "minor")
            entry = {**c, "doc_a": doc_a, "doc_b": doc_b}
            bucket = by_severity.get(severity, by_severity["minor"])
            bucket.append(entry)
    return by_severity


def _aggregate_by_document(matrix: List[dict]) -> Dict[str, dict]:
    """Per-document stats: how many contradictions, who contradicts it most."""
    doc_stats: Dict[str, dict] = {}

    for pair in matrix:
        doc_a = pair.get("doc_a", "?")
        doc_b = pair.get("doc_b", "?")
        n_contradictions = len(pair.get("contradictions", []))
        relationship = pair.get("relationship", "unknown")

        for name, other in [(doc_a, doc_b), (doc_b, doc_a)]:
            if name not in doc_stats:
                doc_stats[name] = {
                    "contradictions_found": 0,
                    "comparisons": 0,
                    "contradiction_partners": {},
                    "relationships": [],
                }
            doc_stats[name]["comparisons"] += 1
            doc_stats[name]["contradictions_found"] += n_contradictions
            doc_stats[name]["relationships"].append(
                {"with": other, "relationship": relationship}
            )
            if n_contradictions > 0:
                doc_stats[name]["contradiction_partners"][other] = (
                    doc_stats[name]["contradiction_partners"].get(other, 0)
                    + n_contradictions
                )

    # Compute most_contradicted_by for each document
    for name, stats in doc_stats.items():
        partners = stats["contradiction_partners"]
        if partners:
            stats["most_contradicted_by"] = max(partners, key=partners.get)
        else:
            stats["most_contradicted_by"] = None

    return doc_stats


def _aggregate_by_entity(matrix: List[dict]) -> Dict[str, list]:
    """Group contradictions by people mentioned in them.

    Scans contradiction text for names that appear in the inventory and
    groups findings by person.
    """
    by_entity: Dict[str, list] = {}

    for pair in matrix:
        doc_a = pair.get("doc_a", "?")
        doc_b = pair.get("doc_b", "?")
        for c in pair.get("contradictions", []):
            # Combine all text fields for entity detection
            haystack = " ".join([
                c.get("doc_a_says", ""),
                c.get("doc_b_says", ""),
                c.get("explanation", ""),
            ]).lower()

            # Try to find referenced names (simple heuristic: capitalized
            # multi-word sequences that look like names)
            names = re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", " ".join([
                c.get("doc_a_says", ""),
                c.get("doc_b_says", ""),
                c.get("explanation", ""),
            ]))
            if not names:
                names = ["(unattributed)"]

            for name in set(names):
                by_entity.setdefault(name, []).append({
                    "doc_a": doc_a,
                    "doc_b": doc_b,
                    "what_they_disagree_on": c.get("explanation", ""),
                    "severity": c.get("severity", "minor"),
                    "category": c.get("category", "factual"),
                })

    return by_entity


# ---------------------------------------------------------------------------
# Executive Summary & Impeachment Priorities (LLM Synthesis)
# ---------------------------------------------------------------------------

def _generate_executive_summary(
    state: dict,
    by_severity: Dict[str, list],
    by_document: Dict[str, dict],
    total_contradictions: int,
    pairs_compared: int,
    document_count: int,
) -> dict:
    """Use one LLM call to synthesize an executive summary, impeachment
    priorities, and investigation leads from the aggregated contradiction data.

    Returns:
        {"executive_summary": str, "impeachment_priorities": [...],
         "investigation_leads": [...]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {
            "executive_summary": (
                f"Analyzed {document_count} documents across {pairs_compared} comparisons. "
                f"Found {total_contradictions} contradictions."
            ),
            "impeachment_priorities": [],
            "investigation_leads": [],
        }

    ctx = get_case_context(state)

    # Build a compact summary of critical + significant contradictions
    findings_text = ""
    for severity in ("critical", "significant"):
        items = by_severity.get(severity, [])
        if items:
            findings_text += f"\n--- {severity.upper()} CONTRADICTIONS ({len(items)}) ---\n"
            for item in items[:15]:  # Cap to avoid token overflow
                findings_text += (
                    f"- [{item.get('category', '?')}] {item['doc_a']} vs {item['doc_b']}: "
                    f"{item.get('explanation', 'N/A')}\n"
                )

    # Build per-document contradiction counts
    doc_summary = ""
    for name, stats in sorted(
        by_document.items(),
        key=lambda x: x[1]["contradictions_found"],
        reverse=True,
    )[:10]:
        most_by = stats.get("most_contradicted_by") or "N/A"
        doc_summary += (
            f"- {name}: {stats['contradictions_found']} contradictions "
            f"(most with: {most_by})\n"
        )

    prompt = f"""You are a {ctx['role']} reviewing a Cross-Document Contradiction Matrix.

{ctx['directives_block']}

CASE SUMMARY:
{state.get('case_summary', 'N/A')[:2000]}

ANALYSIS SCOPE: {document_count} documents, {pairs_compared} pairs compared, {total_contradictions} contradictions found.

{findings_text}

DOCUMENT CONTRADICTION PROFILE:
{doc_summary}

Produce a JSON object:
{{
    "executive_summary": "3-5 sentence overview of the case's internal consistency. Note the most damaging contradictions and overall credibility assessment.",
    "impeachment_priorities": [
        {{
            "rank": 1,
            "target_document": "filename of the document to impeach with",
            "against_document": "filename of the contradicting document",
            "why": "Specific explanation of the impeachment opportunity"
        }}
    ],
    "investigation_leads": [
        {{
            "lead": "What to investigate further",
            "based_on": "Which contradiction or omission prompted this",
            "priority": "high | medium | low"
        }}
    ]
}}

Focus on actionable insights for {ctx['our_side']}. Rank impeachment priorities by trial impact.
Return ONLY the JSON object."""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        parsed = extract_json(response.content)
        if isinstance(parsed, dict):
            return {
                "executive_summary": parsed.get("executive_summary", ""),
                "impeachment_priorities": parsed.get("impeachment_priorities", []),
                "investigation_leads": parsed.get("investigation_leads", []),
            }
    except Exception as exc:
        logger.warning("Executive summary generation failed: %s", exc)

    return {
        "executive_summary": (
            f"Analyzed {document_count} documents across {pairs_compared} comparisons. "
            f"Found {total_contradictions} contradictions "
            f"({len(by_severity.get('critical', []))} critical)."
        ),
        "impeachment_priorities": [],
        "investigation_leads": [],
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_contradiction_matrix(
    state: dict,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Run the full 3-phase contradiction matrix analysis.

    1. Build document inventory (1 LLM call per document)
    2. Select smart comparison pairs (no LLM)
    3. Deep-compare each pair (1 LLM call per pair)
    4. Aggregate and synthesize (1 final LLM call)

    Args:
        state: The analysis state dict. Must contain ``raw_documents`` and
            ``current_model``.  Should also contain ``case_summary``,
            ``case_type``, ``attorney_directives``, etc.
        on_progress: Optional callback with signature
            ``(phase: str, current: int, total: int, detail: str) -> None``.

    Returns:
        Full matrix result dict::

            {
                "generated_at": "ISO timestamp",
                "document_count": int,
                "pairs_compared": int,
                "total_contradictions": int,
                "critical_findings": int,
                "inventory": [...],
                "matrix": [...],
                "by_severity": {...},
                "by_document": {...},
                "by_entity": {...},
                "executive_summary": str,
                "impeachment_priorities": [...],
                "investigation_leads": [...],
            }
    """
    started_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Phase 1: Document inventory
    # ------------------------------------------------------------------
    logger.info("Contradiction matrix -- Phase 1: Document Inventory")
    inventory = build_document_inventory(state, on_progress=on_progress)
    if not inventory:
        return _empty_matrix_result("No documents found in case")

    # Pre-collect full content by filename for Phase 3
    docs_by_source = _collect_documents_by_source(state.get("raw_documents", []))

    # ------------------------------------------------------------------
    # Phase 2: Smart pair selection
    # ------------------------------------------------------------------
    logger.info("Contradiction matrix -- Phase 2: Pair Selection")
    if on_progress:
        on_progress("pair_selection", 0, 1, "Selecting comparison pairs...")

    pairs = select_comparison_pairs(inventory)

    if on_progress:
        on_progress("pair_selection", 1, 1, f"{len(pairs)} pairs selected")

    if not pairs:
        return _empty_matrix_result("No meaningful document pairs to compare")

    # ------------------------------------------------------------------
    # Phase 3: Pairwise deep comparison
    # ------------------------------------------------------------------
    logger.info(
        "Contradiction matrix -- Phase 3: Comparing %d pairs", len(pairs)
    )
    matrix: List[dict] = []
    total_pairs = len(pairs)

    for pair_idx, (idx_a, idx_b) in enumerate(pairs):
        doc_a = inventory[idx_a]
        doc_b = inventory[idx_b]
        name_a = doc_a["filename"]
        name_b = doc_b["filename"]

        if on_progress:
            on_progress(
                "comparison",
                pair_idx + 1,
                total_pairs,
                f"{name_a} vs {name_b}",
            )

        content_a = docs_by_source.get(name_a, {}).get("content", "")
        content_b = docs_by_source.get(name_b, {}).get("content", "")

        if not content_a or not content_b:
            logger.warning(
                "Skipping pair %s vs %s -- missing content", name_a, name_b
            )
            continue

        comparison = compare_document_pair(
            state, doc_a, doc_b, content_a, content_b,
        )

        # Attach pair metadata
        comparison["pair_index"] = pair_idx
        comparison["contradiction_count"] = len(
            comparison.get("contradictions", [])
        )
        matrix.append(comparison)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    logger.info("Contradiction matrix -- Aggregating results")
    total_contradictions = sum(
        len(p.get("contradictions", [])) for p in matrix
    )
    by_severity = _aggregate_by_severity(matrix)
    by_document = _aggregate_by_document(matrix)
    by_entity = _aggregate_by_entity(matrix)

    critical_count = len(by_severity.get("critical", []))

    # ------------------------------------------------------------------
    # Executive summary (1 final LLM call)
    # ------------------------------------------------------------------
    logger.info("Contradiction matrix -- Generating executive summary")
    if on_progress:
        on_progress("synthesis", 1, 1, "Generating executive summary...")

    synthesis = _generate_executive_summary(
        state,
        by_severity,
        by_document,
        total_contradictions,
        len(matrix),
        len(inventory),
    )

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info(
        "Contradiction matrix complete: %d docs, %d pairs, %d contradictions "
        "(%d critical) in %.1fs",
        len(inventory), len(matrix), total_contradictions, critical_count,
        elapsed,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "document_count": len(inventory),
        "pairs_compared": len(matrix),
        "total_contradictions": total_contradictions,
        "critical_findings": critical_count,
        "inventory": inventory,
        "matrix": matrix,
        "by_severity": by_severity,
        "by_document": by_document,
        "by_entity": by_entity,
        "executive_summary": synthesis.get("executive_summary", ""),
        "impeachment_priorities": synthesis.get("impeachment_priorities", []),
        "investigation_leads": synthesis.get("investigation_leads", []),
    }


def _empty_matrix_result(reason: str) -> dict:
    """Return a minimal matrix result when analysis cannot proceed."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": 0,
        "document_count": 0,
        "pairs_compared": 0,
        "total_contradictions": 0,
        "critical_findings": 0,
        "inventory": [],
        "matrix": [],
        "by_severity": {"critical": [], "significant": [], "minor": []},
        "by_document": {},
        "by_entity": {},
        "executive_summary": reason,
        "impeachment_priorities": [],
        "investigation_leads": [],
        "error": reason,
    }


# ---------------------------------------------------------------------------
# Session Persistence
# ---------------------------------------------------------------------------

def _matrix_dir(data_dir: str, case_id: str) -> Path:
    """Return the directory where contradiction matrix files are stored."""
    return Path(data_dir) / "cases" / case_id / "contradiction_matrix"


def save_contradiction_matrix(
    data_dir: str,
    case_id: str,
    prep_id: str,
    matrix: dict,
) -> None:
    """Persist a contradiction matrix result to disk.

    Storage path: ``data/cases/{case_id}/contradiction_matrix/{prep_id}.json``

    Args:
        data_dir: Root data directory (e.g. ``"data"``).
        case_id: The case identifier.
        prep_id: The preparation identifier (analysis run).
        matrix: The full matrix result dict from ``run_contradiction_matrix()``.
    """
    directory = _matrix_dir(data_dir, case_id)
    os.makedirs(directory, exist_ok=True)

    path = directory / f"{prep_id}.json"
    matrix["saved_at"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(matrix, fh, indent=2, default=str)
        logger.info("Contradiction matrix saved: %s", path)
    except Exception:
        logger.exception("Failed to save contradiction matrix to %s", path)
        raise


def load_contradiction_matrix(
    data_dir: str,
    case_id: str,
    prep_id: str,
) -> Optional[dict]:
    """Load a previously saved contradiction matrix from disk.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.
        prep_id: The preparation identifier.

    Returns:
        The matrix result dict, or ``None`` if not found or corrupt.
    """
    path = _matrix_dir(data_dir, case_id) / f"{prep_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("Failed to load contradiction matrix from %s", path)
        return None


def list_contradiction_matrices(
    data_dir: str,
    case_id: str,
) -> List[dict]:
    """Return metadata for all saved matrices for a case, newest first.

    Returns:
        List of dicts with keys: ``prep_id``, ``generated_at``,
        ``document_count``, ``pairs_compared``, ``total_contradictions``,
        ``critical_findings``.
    """
    directory = _matrix_dir(data_dir, case_id)
    if not directory.exists():
        return []

    index: List[dict] = []
    for fp in directory.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            index.append({
                "prep_id": fp.stem,
                "generated_at": data.get("generated_at", ""),
                "document_count": data.get("document_count", 0),
                "pairs_compared": data.get("pairs_compared", 0),
                "total_contradictions": data.get("total_contradictions", 0),
                "critical_findings": data.get("critical_findings", 0),
            })
        except Exception:
            logger.warning("Skipping corrupt contradiction matrix file %s", fp)

    index.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return index


def delete_contradiction_matrix(
    data_dir: str,
    case_id: str,
    prep_id: str,
) -> bool:
    """Delete a saved contradiction matrix.

    Returns:
        ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    path = _matrix_dir(data_dir, case_id) / f"{prep_id}.json"
    if path.exists():
        try:
            os.remove(path)
            logger.info("Deleted contradiction matrix: %s", path)
            return True
        except Exception:
            logger.exception("Failed to delete contradiction matrix %s", path)
            raise
    return False
