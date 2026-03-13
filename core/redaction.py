# ---- AI-Powered Document Redaction Engine ----------------------------------
# Scans case documents for PII, privileged content, and sensitive information.
# Supports regex-based detection (SSN, phone, email, credit card) and
# LLM-based detection (DOB, addresses, medical info, attorney-client privilege).
# Produces redacted text and discovery-compliant redaction logs.

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm, invoke_with_retry
from core.nodes._common import extract_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII Categories
# ---------------------------------------------------------------------------

REDACTION_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "ssn": {
        "label": "Social Security Numbers",
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "default": True,
    },
    "phone": {
        "label": "Phone Numbers",
        "pattern": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "default": True,
    },
    "email": {
        "label": "Email Addresses",
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "default": True,
    },
    "credit_card": {
        "label": "Credit Card Numbers",
        "pattern": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "default": True,
    },
    "dob": {
        "label": "Dates of Birth",
        "pattern": None,  # LLM-detected
        "default": True,
    },
    "address": {
        "label": "Physical Addresses",
        "pattern": None,  # LLM-detected
        "default": False,
    },
    "medical": {
        "label": "Medical Information",
        "pattern": None,  # LLM-detected
        "default": False,
    },
    "financial": {
        "label": "Financial Account Numbers",
        "pattern": r"\b(?:account|acct|routing)[\s#:]*\d{8,17}\b",
        "default": False,
    },
    "privilege": {
        "label": "Attorney-Client Privileged Content",
        "pattern": None,  # LLM-detected
        "default": False,
    },
    "work_product": {
        "label": "Attorney Work Product",
        "pattern": None,  # LLM-detected
        "default": False,
    },
}

# Categories that require LLM for detection (no regex pattern)
_LLM_CATEGORIES = {k for k, v in REDACTION_CATEGORIES.items() if v["pattern"] is None}

# Categories with regex patterns
_REGEX_CATEGORIES = {k for k, v in REDACTION_CATEGORIES.items() if v["pattern"] is not None}


# ---------------------------------------------------------------------------
# Phase 1: Regex-Based Scanning
# ---------------------------------------------------------------------------

def _regex_scan(text: str, categories: List[str]) -> List[dict]:
    """Scan text with compiled regex patterns for pattern-based categories.

    Args:
        text: The document text to scan.
        categories: List of category keys to scan for.

    Returns:
        List of finding dicts with category, text, start, end, context,
        confidence, and source fields.
    """
    findings: List[dict] = []
    regex_cats = [c for c in categories if c in _REGEX_CATEGORIES]

    for cat in regex_cats:
        pattern_str = REDACTION_CATEGORIES[cat]["pattern"]
        if not pattern_str:
            continue
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            logger.warning("Invalid regex pattern for category %s", cat)
            continue

        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            matched_text = match.group(0)

            # Build context window (50 chars on each side)
            ctx_start = max(0, start - 50)
            ctx_end = min(len(text), end + 50)
            context = text[ctx_start:ctx_end]

            findings.append({
                "category": cat,
                "text": matched_text,
                "start": start,
                "end": end,
                "context": context,
                "confidence": "high",
                "source": "regex",
            })

    return findings


# ---------------------------------------------------------------------------
# Phase 2: LLM-Based Scanning
# ---------------------------------------------------------------------------

_LLM_SCAN_PROMPT = """You are a legal document review specialist performing PII and privileged content detection.

Scan the following document text and identify ALL instances of the requested categories.

CATEGORIES TO DETECT:
{categories_desc}

DOCUMENT TEXT:
{text}

For each finding, return the EXACT text that should be redacted, the category it belongs to,
and your confidence level (high/medium/low).

Return JSON ONLY — no commentary:
{{
    "findings": [
        {{
            "category": "dob",
            "text": "born on January 15, 1985",
            "confidence": "high",
            "reason": "Explicit date of birth reference"
        }},
        {{
            "category": "privilege",
            "text": "I discussed with my attorney Sarah that we should...",
            "confidence": "medium",
            "reason": "Attorney-client communication about legal strategy"
        }}
    ]
}}

If no PII or privileged content is found for the requested categories, return:
{{"findings": []}}
"""


def _llm_scan(text: str, categories: List[str], state: Optional[dict] = None) -> List[dict]:
    """Scan text using an LLM for context-dependent categories.

    The LLM identifies DOBs, addresses, medical information,
    attorney-client privilege, and work product that regex cannot detect.

    Args:
        text: The document text to scan.
        categories: List of category keys to scan for (only LLM-type used).
        state: Optional agent state dict for LLM provider config.

    Returns:
        List of finding dicts with positional data resolved against the text.
    """
    llm_cats = [c for c in categories if c in _LLM_CATEGORIES]
    if not llm_cats:
        return []

    # Build category description for the prompt
    cat_descs = []
    for cat in llm_cats:
        info = REDACTION_CATEGORIES[cat]
        cat_descs.append(f"- {cat}: {info['label']}")
    categories_desc = "\n".join(cat_descs)

    # Truncate very long documents to fit LLM context
    max_text_len = 30000
    scan_text = text[:max_text_len]
    if len(text) > max_text_len:
        logger.info(
            "Document truncated from %d to %d chars for LLM PII scan",
            len(text), max_text_len,
        )

    provider = None
    if state:
        provider = state.get("current_model")

    llm = get_llm(provider, max_output_tokens=4096)
    if not llm:
        logger.warning("No LLM available for PII scan — skipping LLM categories")
        return []

    prompt_text = _LLM_SCAN_PROMPT.format(
        categories_desc=categories_desc,
        text=scan_text,
    )

    messages = [
        SystemMessage(
            content=(
                "You are a meticulous legal document reviewer. Your task is to "
                "identify PII and privileged content with high accuracy. "
                "Only flag content you are confident about. "
                "Do NOT flag generic legal terminology or public information."
            )
        ),
        HumanMessage(content=prompt_text),
    ]

    try:
        response = invoke_with_retry(llm, messages)
        result = extract_json(response.content)
    except Exception as exc:
        logger.exception("LLM PII scan failed: %s", exc)
        return []

    if not result or not isinstance(result, dict):
        return []

    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return []

    # Resolve positions in the original text
    findings: List[dict] = []
    for rf in raw_findings:
        if not isinstance(rf, dict):
            continue
        found_text = rf.get("text", "")
        category = rf.get("category", "")
        confidence = rf.get("confidence", "medium")

        if not found_text or category not in llm_cats:
            continue

        # Find the text in the document to get positional data
        idx = text.find(found_text)
        if idx == -1:
            # Try case-insensitive search
            idx = text.lower().find(found_text.lower())
            if idx == -1:
                # LLM may have paraphrased — record without position
                findings.append({
                    "category": category,
                    "text": found_text,
                    "start": -1,
                    "end": -1,
                    "context": found_text,
                    "confidence": confidence,
                    "source": "llm",
                })
                continue

        start = idx
        end = idx + len(found_text)

        # Build context window
        ctx_start = max(0, start - 50)
        ctx_end = min(len(text), end + 50)
        context = text[ctx_start:ctx_end]

        findings.append({
            "category": category,
            "text": found_text,
            "start": start,
            "end": end,
            "context": context,
            "confidence": confidence,
            "source": "llm",
        })

    return findings


# ---------------------------------------------------------------------------
# Main Scan Function
# ---------------------------------------------------------------------------

def scan_document_for_pii(
    text: str,
    categories: Optional[List[str]] = None,
    use_llm: bool = True,
    state: Optional[dict] = None,
) -> dict:
    """Scan document text and return found PII items.

    Phase 1: Regex scan for pattern-based categories (SSN, phone, email, etc.)
    Phase 2: LLM scan for context-dependent categories (DOB, privilege, etc.)

    Args:
        text: The full document text to scan.
        categories: List of category keys to scan for. If None, uses all
            categories marked as default=True.
        use_llm: Whether to use LLM for context-dependent detection.
            Set to False for fast regex-only scanning.
        state: Optional agent state dict (provides LLM provider preference).

    Returns:
        Dict with ``findings`` (list of finding dicts) and ``summary``
        (category -> count mapping).
    """
    if not text or not text.strip():
        return {"findings": [], "summary": {}}

    # Determine active categories
    if categories is None:
        active = [k for k, v in REDACTION_CATEGORIES.items() if v["default"]]
    else:
        active = [c for c in categories if c in REDACTION_CATEGORIES]

    if not active:
        return {"findings": [], "summary": {}}

    # Phase 1: Regex
    findings = _regex_scan(text, active)

    # Phase 2: LLM (if enabled and any LLM categories requested)
    if use_llm:
        llm_findings = _llm_scan(text, active, state)
        findings.extend(llm_findings)

    # Deduplicate overlapping findings (prefer regex over LLM for same span)
    findings = _deduplicate_findings(findings)

    # Sort by position in document
    findings.sort(key=lambda f: (f.get("start", -1), f.get("category", "")))

    # Build summary
    summary: Dict[str, int] = {}
    for f in findings:
        cat = f["category"]
        summary[cat] = summary.get(cat, 0) + 1

    return {"findings": findings, "summary": summary}


def _deduplicate_findings(findings: List[dict]) -> List[dict]:
    """Remove duplicate findings that overlap the same text span.

    When regex and LLM both find the same content, prefer the regex finding
    (higher confidence, exact match). For overlapping spans, keep the one
    with higher confidence.
    """
    if not findings:
        return []

    # Group by approximate position
    seen_spans: Dict[str, dict] = {}  # "start:end" -> finding

    deduped: List[dict] = []
    for f in findings:
        start = f.get("start", -1)
        end = f.get("end", -1)

        if start == -1 or end == -1:
            # No positional data — always keep
            deduped.append(f)
            continue

        key = f"{start}:{end}"
        if key in seen_spans:
            existing = seen_spans[key]
            # Prefer regex source (more reliable)
            if f["source"] == "regex" and existing["source"] != "regex":
                seen_spans[key] = f
            # Otherwise keep existing
        else:
            seen_spans[key] = f

    deduped.extend(seen_spans.values())
    return deduped


# ---------------------------------------------------------------------------
# Apply Redactions
# ---------------------------------------------------------------------------

_PLACEHOLDER_MAP = {
    "ssn": "XXX-XX-XXXX",
    "phone": "(XXX) XXX-XXXX",
    "email": "xxxx@xxxx.xxx",
    "credit_card": "XXXX-XXXX-XXXX-XXXX",
    "dob": "XX/XX/XXXX",
    "address": "[ADDRESS]",
    "medical": "[MEDICAL]",
    "financial": "XXXXXXXX",
    "privilege": "[PRIVILEGED]",
    "work_product": "[WORK PRODUCT]",
}


def apply_redactions(
    text: str,
    findings: List[dict],
    redaction_style: str = "blackout",
) -> str:
    """Apply redactions to text based on findings.

    Args:
        text: Original document text.
        findings: List of finding dicts from ``scan_document_for_pii``.
        redaction_style: One of:
            - ``"blackout"``: Replace with ``[REDACTED]``
            - ``"category"``: Replace with ``[REDACTED - SSN]``, etc.
            - ``"placeholder"``: Replace with ``XXX-XX-XXXX`` style placeholders

    Returns:
        Redacted text string with PII replaced.
    """
    if not findings:
        return text

    # Filter to findings with valid positions, sort by start descending
    # (process from end to preserve positions)
    positional = [
        f for f in findings
        if f.get("start", -1) >= 0 and f.get("end", -1) > 0
    ]
    positional.sort(key=lambda f: f["start"], reverse=True)

    result = text
    for f in positional:
        start = f["start"]
        end = f["end"]
        cat = f.get("category", "unknown")
        label = REDACTION_CATEGORIES.get(cat, {}).get("label", cat.upper())

        if redaction_style == "category":
            replacement = f"[REDACTED - {label}]"
        elif redaction_style == "placeholder":
            replacement = _PLACEHOLDER_MAP.get(cat, "[REDACTED]")
        else:  # blackout
            replacement = "[REDACTED]"

        result = result[:start] + replacement + result[end:]

    return result


# ---------------------------------------------------------------------------
# Redaction Log (Discovery Compliance)
# ---------------------------------------------------------------------------

_LEGAL_BASIS_MAP = {
    "ssn": "Personal privacy — Social Security Number (FRCP 5.2(a)(1))",
    "phone": "Personal privacy — Telephone number",
    "email": "Personal privacy — Email address",
    "credit_card": "Personal privacy — Financial account number (FRCP 5.2(a)(4))",
    "dob": "Personal privacy — Date of birth (FRCP 5.2(a)(2))",
    "address": "Personal privacy — Home address",
    "medical": "Protected health information (HIPAA / state health privacy law)",
    "financial": "Personal privacy — Financial account number (FRCP 5.2(a)(4))",
    "privilege": "Attorney-client privilege (Fed. R. Evid. 501)",
    "work_product": "Attorney work product doctrine (FRCP 26(b)(3))",
}


def generate_redaction_log(
    findings: List[dict],
    document_name: str,
) -> dict:
    """Create a privilege/redaction log entry for discovery compliance.

    Each redaction is documented with its legal basis and a generic
    description that does not reveal the redacted content.

    Args:
        findings: List of finding dicts from ``scan_document_for_pii``.
        document_name: The name of the document being redacted.

    Returns:
        Dict with ``document``, ``total_redactions``, ``by_category``,
        and ``entries`` (list of log entries).
    """
    by_category: Dict[str, int] = {}
    entries: List[dict] = []

    for idx, f in enumerate(findings, start=1):
        cat = f.get("category", "unknown")
        label = REDACTION_CATEGORIES.get(cat, {}).get("label", cat)
        by_category[cat] = by_category.get(cat, 0) + 1

        # Generic description that does not reveal actual content
        if cat == "ssn":
            description = "Social Security Number detected in text"
        elif cat == "phone":
            description = "Phone number detected in text"
        elif cat == "email":
            description = "Email address detected in text"
        elif cat == "credit_card":
            description = "Credit card number detected in text"
        elif cat == "dob":
            description = "Date of birth reference detected in text"
        elif cat == "address":
            description = "Physical address detected in text"
        elif cat == "medical":
            description = "Medical information detected in text"
        elif cat == "financial":
            description = "Financial account number detected in text"
        elif cat == "privilege":
            description = "Attorney-client privileged communication"
        elif cat == "work_product":
            description = "Attorney work product material"
        else:
            description = f"Sensitive content ({label}) detected in text"

        # Build approximate page reference from character offset
        start = f.get("start", -1)
        if start >= 0:
            # Rough estimate: ~3000 chars per page
            approx_page = (start // 3000) + 1
            page_ref = f"Approx. page {approx_page}"
        else:
            page_ref = "Position not determined"

        entries.append({
            "id": idx,
            "category": cat,
            "category_label": label,
            "page_reference": page_ref,
            "basis": _LEGAL_BASIS_MAP.get(cat, "Privacy protection"),
            "description": description,
            "confidence": f.get("confidence", "unknown"),
            "source": f.get("source", "unknown"),
        })

    return {
        "document": document_name,
        "total_redactions": len(findings),
        "by_category": by_category,
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Batch Scanning
# ---------------------------------------------------------------------------

def batch_scan_case_files(
    case_id: str,
    prep_id: str,
    categories: List[str],
    state: dict,
    data_dir: str,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Scan all case files for PII using OCR cache for text.

    Reads text from the OCR cache (or raw documents in state) and runs
    PII scanning on each file.

    Args:
        case_id: The case identifier.
        prep_id: The preparation identifier.
        categories: List of category keys to scan for.
        state: Agent state dict with ``raw_documents`` and model config.
        data_dir: Root data directory path.
        on_progress: Optional callback ``fn(file_name, file_index, total)``
            called as each file starts processing.

    Returns:
        Dict with ``files`` (per-file findings), ``total_findings``,
        and ``summary`` (aggregated category counts).
    """
    from core.ingest import OCRCache

    case_dir = os.path.join(data_dir, "cases", case_id)
    ocr_cache = OCRCache(case_dir)

    # Gather text sources: prefer OCR cache, fall back to raw_documents
    file_texts: Dict[str, str] = {}

    # Try OCR cache first
    manifest = ocr_cache._load_manifest()
    for file_key, meta in manifest.items():
        if meta.get("status") == "done":
            cached_text = ocr_cache.get_text(file_key)
            if cached_text:
                filename = meta.get("filename", file_key)
                file_texts[filename] = cached_text

    # Supplement from raw_documents if no OCR cache entries
    if not file_texts and state.get("raw_documents"):
        for doc in state["raw_documents"]:
            source = getattr(doc, "metadata", {}).get("source", "unknown")
            content = doc.page_content if hasattr(doc, "page_content") else str(doc)
            if content.strip():
                # Aggregate by source file
                if source in file_texts:
                    file_texts[source] += "\n" + content
                else:
                    file_texts[source] = content

    if not file_texts:
        return {
            "files": {},
            "total_findings": 0,
            "summary": {},
        }

    # Scan each file
    all_files: Dict[str, dict] = {}
    total_findings = 0
    agg_summary: Dict[str, int] = {}
    file_names = sorted(file_texts.keys())

    for idx, filename in enumerate(file_names):
        if on_progress:
            try:
                on_progress(filename, idx, len(file_names))
            except Exception:
                pass  # Progress callback errors must not abort scan

        text = file_texts[filename]
        result = scan_document_for_pii(
            text=text,
            categories=categories,
            use_llm=True,
            state=state,
        )

        all_files[filename] = result
        total_findings += len(result.get("findings", []))

        for cat, count in result.get("summary", {}).items():
            agg_summary[cat] = agg_summary.get(cat, 0) + count

    return {
        "files": all_files,
        "total_findings": total_findings,
        "summary": agg_summary,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _reports_dir(data_dir: str, case_id: str) -> Path:
    """Return the directory where redaction reports are stored."""
    return Path(data_dir) / "cases" / case_id / "redaction_reports"


def save_redaction_report(data_dir: str, case_id: str, report: dict) -> str:
    """Save a redaction report to disk.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.
        report: The full report dict to save.

    Returns:
        The report ID (filename stem).
    """
    report_id = report.get("id") or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    ) + "_" + uuid.uuid4().hex[:6]
    report["id"] = report_id
    report["saved_at"] = datetime.now(timezone.utc).isoformat()

    directory = _reports_dir(data_dir, case_id)
    os.makedirs(directory, exist_ok=True)

    path = directory / f"{report_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    logger.info("Saved redaction report %s for case %s", report_id, case_id)
    return report_id


def load_redaction_reports(data_dir: str, case_id: str) -> List[dict]:
    """Load all saved redaction reports for a case, newest first.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.

    Returns:
        List of report dicts (metadata only: id, document, total_redactions,
        by_category, saved_at).
    """
    directory = _reports_dir(data_dir, case_id)
    if not directory.exists():
        return []

    reports: List[dict] = []
    for fp in directory.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            reports.append({
                "id": data.get("id", fp.stem),
                "document": data.get("document", ""),
                "total_redactions": data.get("total_redactions", 0),
                "by_category": data.get("by_category", {}),
                "saved_at": data.get("saved_at", ""),
            })
        except Exception:
            logger.warning("Skipping corrupt redaction report file %s", fp)
            continue

    reports.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
    return reports


def load_redaction_report(data_dir: str, case_id: str, report_id: str) -> Optional[dict]:
    """Load a single redaction report by ID.

    Args:
        data_dir: Root data directory.
        case_id: The case identifier.
        report_id: The report identifier.

    Returns:
        The full report dict, or None if not found.
    """
    path = _reports_dir(data_dir, case_id) / f"{report_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("Failed to load redaction report %s", path)
        return None
