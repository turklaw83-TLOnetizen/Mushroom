"""
evidence_custody.py -- Chain of Custody Tracking for Evidence
Records who handled evidence, when, and how.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data")


def _custody_path(case_id: str) -> str:
    d = os.path.join(_DATA_DIR, "cases", case_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "evidence_custody.json")


def _load_custody(case_id: str) -> List[Dict]:
    path = _custody_path(case_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_custody(case_id: str, entries: List[Dict]):
    path = _custody_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def add_custody_entry(
    case_id: str,
    evidence_id: str,
    action: str,
    from_party: str = "",
    to_party: str = "",
    date: str = "",
    location: str = "",
    notes: str = "",
    recorded_by: str = "",
) -> str:
    """Add a chain-of-custody entry for an evidence item.
    Actions: received, transferred, stored, presented, returned, photographed, analyzed
    """
    entries = _load_custody(case_id)
    entry_id = f"coc_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": entry_id,
        "evidence_id": evidence_id,
        "action": action,
        "from_party": from_party,
        "to_party": to_party,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "location": location,
        "notes": notes,
        "recorded_by": recorded_by,
        "recorded_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    _save_custody(case_id, entries)
    logger.info("Added custody entry %s for evidence %s in case %s", entry_id, evidence_id, case_id)
    return entry_id


def get_custody_chain(case_id: str, evidence_id: str) -> List[Dict]:
    """Get the chain of custody for a specific evidence item, sorted by date."""
    entries = _load_custody(case_id)
    chain = [e for e in entries if e.get("evidence_id") == evidence_id]
    chain.sort(key=lambda e: (e.get("date", ""), e.get("recorded_at", "")))
    return chain


def get_all_custody(case_id: str) -> List[Dict]:
    """Get all custody entries for a case."""
    entries = _load_custody(case_id)
    entries.sort(key=lambda e: e.get("recorded_at", ""), reverse=True)
    return entries


def delete_custody_entry(case_id: str, entry_id: str) -> bool:
    """Delete a custody entry."""
    entries = _load_custody(case_id)
    before = len(entries)
    entries = [e for e in entries if e.get("id") != entry_id]
    if len(entries) < before:
        _save_custody(case_id, entries)
        return True
    return False
