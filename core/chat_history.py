"""
chat_history.py -- AI Chat History Persistence
Stores chat messages per case/prep for continuity across sessions.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data")


def _chat_path(case_id: str) -> str:
    d = os.path.join(_DATA_DIR, "cases", case_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "chat_history.json")


def _load_history(case_id: str) -> List[Dict]:
    path = _chat_path(case_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_history(case_id: str, history: List[Dict]):
    path = _chat_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def save_message(
    case_id: str,
    role: str,
    content: str,
    prep_id: str = "",
    context_module: str = "",
) -> None:
    """Save a single chat message."""
    history = _load_history(case_id)
    history.append({
        "role": role,
        "content": content,
        "prep_id": prep_id,
        "context_module": context_module,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only last 200 messages per case
    if len(history) > 200:
        history = history[-200:]
    _save_history(case_id, history)


def load_history(
    case_id: str,
    prep_id: str = "",
    limit: int = 50,
) -> List[Dict]:
    """Load chat history, optionally filtered by prep_id."""
    history = _load_history(case_id)
    if prep_id:
        history = [m for m in history if m.get("prep_id", "") == prep_id]
    return history[-limit:]


def clear_history(case_id: str, prep_id: str = "") -> int:
    """Clear chat history. If prep_id given, only clear that prep's messages."""
    history = _load_history(case_id)
    if prep_id:
        before = len(history)
        history = [m for m in history if m.get("prep_id", "") != prep_id]
        _save_history(case_id, history)
        return before - len(history)
    else:
        _save_history(case_id, [])
        return len(history)
