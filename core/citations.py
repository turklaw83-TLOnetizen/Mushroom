# ---- Source Citation System ------------------------------------------------
# Extracted from backend/nodes/_common.py for standalone reuse.
# Provides CITATION_INSTRUCTION prompt text and format_docs_with_sources().

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# -- Citation instruction injected into every analysis prompt --
CITATION_INSTRUCTION = """
CITATION RULE (MANDATORY): For every factual claim, conclusion, or reference to case materials,
you MUST cite the source using this exact format: [[source: filename.pdf, p.X]]
- Use the exact filename from the [SOURCE: ...] headers in the documents provided.
- If a page number is available, include it. If not, use [[source: filename.pdf]].
- Place citations inline, immediately after the claim they support.
- Multiple sources for one claim: [[source: file1.pdf, p.3]] [[source: file2.pdf, p.7]]
- Do NOT fabricate sources. Only cite files that appear in the provided documents.
"""


def format_docs_with_sources(
    docs,
    max_docs: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> str:
    """
    Formats a list of LangChain Documents with source headers so the LLM can cite them.
    Each chunk gets a [SOURCE: filename | Page X] header.

    Args:
        docs: List of LangChain Document objects with metadata
        max_docs: Optional limit on number of docs to include
        max_chars: Optional character limit on total output

    Returns:
        Formatted string with source-attributed document text
    """
    if not docs:
        return "(No documents provided)"

    if max_docs:
        docs = docs[:max_docs]

    parts: List[str] = []
    total_chars = 0

    for doc in docs:
        content = doc.page_content if hasattr(doc, "page_content") else str(doc)
        meta = doc.metadata if hasattr(doc, "metadata") else {}

        source = meta.get("source", "Unknown")
        page = meta.get("page", None)
        section = meta.get("section_title", None)
        tag = meta.get("file_tag", None)

        # Build source header
        header_parts = [f"SOURCE: {source}"]
        if tag:
            header_parts.append(f"({tag})")
        if page:
            header_parts.append(f"| Page {page}")
        if section:
            header_parts.append(f"| Section: {section}")

        header = "[" + " ".join(header_parts) + "]"
        chunk = f"{header}\n{content}"

        if max_chars and total_chars + len(chunk) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 200:
                parts.append(chunk[:remaining] + "\n... [TRUNCATED]")
            break

        parts.append(chunk)
        total_chars += len(chunk)

    return "\n\n".join(parts)


# -- Citation rendering helpers for the UI --

_CITATION_RE = re.compile(r"\[\[source:\s*(.+?)(?:,\s*p\.?\s*(\d+))?\s*\]\]")


# -- Node-level document filtering -----------------------------------------
# Maps node names to the file-tag categories most useful for that node.
# Documents with matching tags are placed FIRST so they fill the context window
# before less-relevant docs when max_chars truncation is applied.

_NODE_TAG_PREFERENCES = {
    "foundations_agent": [
        "Police Report", "Photos/Video", "Medical Records",
        "Expert Report", "Deposition", "Discovery",
    ],
    "consistency_checker": [
        "Witness Statement", "Deposition", "Police Report",
    ],
}

_MIN_FILTERED_DOCS = 5


def filter_docs_by_relevance(
    docs: list,
    node_name: str,
    file_tags: dict,
) -> list:
    """
    Reorder documents so that tag-relevant docs come first for a given node.

    Does NOT exclude any documents — just reorders so that when max_chars
    truncation is applied by format_docs_with_sources(), the most relevant
    docs fill the context window first.

    Args:
        docs: List of LangChain Document objects
        node_name: Analysis node name (e.g. "foundations_agent")
        file_tags: Dict of {filename: [tag1, tag2, ...]}

    Returns:
        Reordered list of documents (preferred tags first)
    """
    preferred_tags = _NODE_TAG_PREFERENCES.get(node_name)
    if not preferred_tags or not file_tags or not docs:
        return docs

    preferred_set = set(preferred_tags)

    def _is_preferred(doc) -> bool:
        meta = doc.metadata if hasattr(doc, "metadata") else {}
        source = meta.get("source", "")
        doc_tags = set(file_tags.get(source, []))
        return bool(doc_tags & preferred_set)

    preferred_docs = [d for d in docs if _is_preferred(d)]
    other_docs = [d for d in docs if not _is_preferred(d)]

    return preferred_docs + other_docs


def render_with_references(text: str) -> str:
    """
    Converts [[source: file.pdf, p.3]] citations into numbered Markdown footnotes.
    Returns (rendered_text, footnotes_block).
    """
    if not text:
        return text

    sources_seen: dict = {}  # source_key -> footnote number
    counter = 0

    def _replace(match):
        nonlocal counter
        filename = match.group(1).strip()
        page = match.group(2)
        key = f"{filename}|{page}" if page else filename
        if key not in sources_seen:
            counter += 1
            sources_seen[key] = counter
        num = sources_seen[key]
        label = f"{filename}, p.{page}" if page else filename
        return f"[^{num}]"

    rendered = _CITATION_RE.sub(_replace, text)

    if sources_seen:
        footnotes = []
        for key, num in sources_seen.items():
            if "|" in key:
                fn, pg = key.split("|", 1)
                footnotes.append(f"[^{num}]: {fn}, p.{pg}")
            else:
                footnotes.append(f"[^{num}]: {key}")
        rendered += "\n\n---\n" + "\n".join(footnotes)

    return rendered
