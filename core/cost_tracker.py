# ---- Real Cost Tracking with tiktoken ------------------------------------
# Replaces the hardcoded estimate_cost() placeholder with actual token
# counting and per-model pricing tables.

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (input / output) - updated Feb 2026
COST_PER_MILLION_INPUT = {
    "xai": 5.00,
    "gemini": 1.25,
    "anthropic": 3.00,
    "claude-sonnet-4.5": 3.00,
    "claude-sonnet-4": 3.00,
    "claude-sonnet-4.6": 5.00,
    "claude-opus-4.6": 15.00,
}

COST_PER_MILLION_OUTPUT = {
    "xai": 15.00,
    "gemini": 5.00,
    "anthropic": 15.00,
    "claude-sonnet-4.5": 15.00,
    "claude-sonnet-4": 15.00,
    "claude-sonnet-4.6": 25.00,
    "claude-opus-4.6": 75.00,
}

# Model context window limits (tokens)
MODEL_CONTEXT_LIMITS = {
    "xai": 131_072,
    "gemini": 1_000_000,
    "anthropic": 200_000,
    "claude-sonnet-4.5": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-sonnet-4.6": 200_000,
    "claude-opus-4.6": 1_000_000,
}

# Cached tiktoken encoder
_encoder = None


def _get_encoder():
    """Lazy-load tiktoken encoder with fallback."""
    global _encoder
    if _encoder is not None:
        return _encoder
    try:
        import tiktoken
        _encoder = tiktoken.get_encoding("cl100k_base")
        return _encoder
    except ImportError:
        logger.debug("tiktoken not installed - using char/4 estimate")
        return None
    except Exception as exc:
        logger.debug("tiktoken init failed: %s - using char/4 estimate", exc)
        return None


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken. Falls back to char/4 estimate."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost from token counts and model name."""
    in_rate = COST_PER_MILLION_INPUT.get(model, 3.00)
    out_rate = COST_PER_MILLION_OUTPUT.get(model, 15.00)
    return (input_tokens / 1_000_000 * in_rate) + (output_tokens / 1_000_000 * out_rate)


def estimate_analysis_cost(doc_text: str, model: str, node_count: int = 14) -> dict:
    """
    Estimate the cost of a full analysis run.

    Returns dict with: input_tokens, output_tokens_est, total_cost_est,
    context_limit, needs_chunking, chunk_count.
    """
    doc_tokens = count_tokens(doc_text)
    per_node_overhead = 1000  # system prompt, instructions, etc.
    input_tokens = (doc_tokens * node_count) + (per_node_overhead * node_count)
    output_tokens_est = 2000 * node_count  # ~2K output per node average

    context_limit = MODEL_CONTEXT_LIMITS.get(model, 200_000)
    needs_chunking = doc_tokens > int(context_limit * 0.8)
    chunk_count = 1
    if needs_chunking:
        chunk_size = int(context_limit * 0.6)
        chunk_count = max(1, (doc_tokens // chunk_size) + 1)
        input_tokens *= chunk_count

    total_cost = estimate_cost(input_tokens, output_tokens_est, model)

    return {
        "doc_tokens": doc_tokens,
        "input_tokens": input_tokens,
        "output_tokens_est": output_tokens_est,
        "total_cost_est": total_cost,
        "context_limit": context_limit,
        "needs_chunking": needs_chunking,
        "chunk_count": chunk_count,
        "node_count": node_count,
        "model": model,
    }


def estimate_per_node_costs(doc_tokens: int, model: str = "", node_count: int = 14) -> Dict[str, float]:
    """Estimate cost per analysis node.
    Returns {node_name: estimated_cost_dollars}.
    """
    if not model:
        model = "xai"

    # Typical output ratios per node (some nodes produce more output)
    NODE_OUTPUT_RATIOS = {
        "analyzer": 1.5,
        "strategist": 1.2,
        "elements_mapper": 1.0,
        "investigation_planner": 0.8,
        "consistency_checker": 0.8,
        "legal_researcher": 1.0,
        "devils_advocate": 1.0,
        "entity_extractor": 0.6,
        "cross_examiner": 1.5,
        "direct_examiner": 1.5,
        "timeline_generator": 0.8,
        "foundations_agent": 0.8,
        "voir_dire_agent": 0.8,
        "mock_jury": 1.0,
    }

    costs = {}
    for node, ratio in NODE_OUTPUT_RATIOS.items():
        input_tokens = doc_tokens  # Each node gets full docs
        output_tokens = int(2000 * ratio)  # Base output ~2000 tokens
        cost = estimate_cost(input_tokens, output_tokens, model)
        costs[node] = round(cost, 4)

    return costs


def format_cost_badge(text: str, model: str) -> str:
    """Format a cost estimate as a display string for UI buttons."""
    est = estimate_analysis_cost(text, model)
    cost = est["total_cost_est"]
    if cost < 0.01:
        return "(< $0.01)"
    return f"(~${cost:.2f})"
