# ---- Smart Token Budgeting: Chunking & Merging ----------------------------
# Ported from backend/workflow.py with logging fixes.
# Handles document chunking when case files exceed model context limits,
# runs nodes per-chunk, and merges results with deduplication.

import logging
from typing import Any, Callable, Dict, List, Optional

from core.cost_tracker import MODEL_CONTEXT_LIMITS

logger = logging.getLogger(__name__)


def estimate_tokens(text) -> int:
    """Fast token estimate (~4 chars per token)."""
    if not text:
        return 0
    return len(str(text)) // 4


def chunk_documents(docs, max_tokens_per_chunk: int, overlap: int = 2) -> List[list]:
    """
    Splits a list of documents into chunks that each fit within max_tokens_per_chunk.
    Each chunk shares *overlap* documents with the next for context continuity.

    Returns: list of document lists.
    """
    if not docs:
        return [docs]

    chunks: List[list] = []
    current_chunk: list = []
    current_tokens = 0

    for doc in docs:
        doc_tokens = estimate_tokens(
            doc.page_content if hasattr(doc, "page_content") else str(doc)
        )

        # Single doc exceeds limit -> include it alone
        if doc_tokens >= max_tokens_per_chunk:
            if current_chunk:
                chunks.append(current_chunk)
            chunks.append([doc])
            current_chunk = []
            current_tokens = 0
            continue

        if current_tokens + doc_tokens > max_tokens_per_chunk:
            chunks.append(current_chunk)
            overlap_docs = current_chunk[-overlap:] if overlap > 0 else []
            current_chunk = list(overlap_docs)
            current_tokens = sum(
                estimate_tokens(d.page_content if hasattr(d, "page_content") else str(d))
                for d in current_chunk
            )

        current_chunk.append(doc)
        current_tokens += doc_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [docs]


def merge_analysis_results(chunk_results: List[Dict]) -> Dict:
    """
    Merges results from multiple chunked analysis runs.
    - Text fields: concatenated with separators
    - List fields: union with deduplication
    - Dict fields: deep-merged
    """
    if not chunk_results:
        return {}
    if len(chunk_results) == 1:
        return chunk_results[0]

    merged: Dict = {}

    # Text fields -- concatenate with chunk markers
    text_keys = [
        "case_summary", "strategy_notes", "devils_advocate_notes",
        "investigation_plan", "deposition_analysis", "research_summary",
    ]

    # List fields -- union/deduplicate
    list_keys = [
        "charges", "witnesses", "cross_examination_questions",
        "direct_examination_questions", "timeline", "evidence_foundations",
        "consistency_check", "legal_elements", "entities",
        "voir_dire_strategy", "mock_jury_result", "drafted_documents",
        "legal_research_data",
    ]

    for key in text_keys:
        parts = []
        for i, result in enumerate(chunk_results):
            val = result.get(key, "")
            if val and val.strip():
                if len(chunk_results) > 1:
                    parts.append(f"--- Chunk {i + 1}/{len(chunk_results)} ---\n{val}")
                else:
                    parts.append(val)
        if parts:
            merged[key] = "\n\n".join(parts)

    for key in list_keys:
        combined: list = []
        seen_sigs: set = set()
        for result in chunk_results:
            items = result.get(key, [])
            if isinstance(items, list):
                for item in items:
                    sig = str(item)[:200]
                    if sig not in seen_sigs:
                        seen_sigs.add(sig)
                        combined.append(item)
        if combined:
            merged[key] = combined

    # Carry forward any other keys from the first result
    for key in chunk_results[0]:
        if key not in merged:
            merged[key] = chunk_results[0][key]

    return merged


def run_node_chunked(
    node_fn: Callable,
    state: Dict,
    model_provider: Optional[str] = None,
) -> Dict:
    """
    Runs a single node function.  If documents exceed 80% of the context limit,
    automatically chunks them, runs the node per-chunk, and merges results.
    Returns the merged result dict.
    """
    docs = state.get("raw_documents", [])
    doc_tokens = sum(
        estimate_tokens(d.page_content if hasattr(d, "page_content") else str(d))
        for d in docs
    )

    provider = model_provider or state.get("current_model", "anthropic")
    ctx_limit = MODEL_CONTEXT_LIMITS.get(provider, 200_000)

    # Reserve 20% for system prompts + output
    safe_limit = int(ctx_limit * 0.80)

    if doc_tokens <= safe_limit or not docs:
        return node_fn(state)

    # Chunk and run
    chunks = chunk_documents(docs, safe_limit)
    chunk_results: List[Dict] = []

    for i, chunk_docs in enumerate(chunks):
        chunk_state = state.copy()
        chunk_state["raw_documents"] = chunk_docs
        chunk_token_est = sum(
            estimate_tokens(d.page_content if hasattr(d, "page_content") else str(d))
            for d in chunk_docs
        )
        logger.info(
            "Running chunk %d/%d (%d docs, ~%s tokens)",
            i + 1, len(chunks), len(chunk_docs), f"{chunk_token_est:,}",
        )
        result = node_fn(chunk_state)
        chunk_results.append(result)

    return merge_analysis_results(chunk_results)
