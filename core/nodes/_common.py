# ---- Common Node Utilities ------------------------------------------------
# Shared by all analysis node modules.
# Ported from backend/nodes/_common.py with import path fixes.

import json
import logging
import os
import re
import time
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.config import CONFIG
from core.state import AgentState, get_case_context, get_stream_callback
from core.llm import get_llm, invoke_with_retry, invoke_with_retry_streaming
from core.citations import CITATION_INSTRUCTION, format_docs_with_sources, filter_docs_by_relevance

logger = logging.getLogger(__name__)


# ---- Robust JSON Extraction ----------------------------------------------

def extract_json(text: str, expect_list: bool = False):
    """Extract the first balanced JSON object or array from LLM output.

    Uses bracket-counting instead of greedy regex to avoid matching
    from the first '{' to the last '}' across unrelated text.
    Also strips ```json fences before parsing.

    Args:
        text: Raw LLM output that may contain JSON embedded in prose.
        expect_list: If True, look for '[...]' first; otherwise '{...}' first.

    Returns:
        Parsed Python object (dict or list), or None if extraction failed.
    """
    if not text:
        return None

    # Strip markdown code fences
    cleaned = text.replace("```json", "").replace("```", "").strip()

    # Try direct parse first (common case: LLM returned pure JSON)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Bracket-counting extraction
    openers = ('[', '{') if expect_list else ('{', '[')
    for open_char in openers:
        close_char = ']' if open_char == '[' else '}'
        start = cleaned.find(open_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        break  # Found balanced brackets but invalid JSON
    return None
