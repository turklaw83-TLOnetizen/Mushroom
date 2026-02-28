# ---- Append-Only Merge Logic -----------------------------------------------
# Extracted from case_manager.py.  Ensures re-analysis never loses data:
# existing items are always preserved, and items not reproduced by the AI
# are flagged with _ai_suggests_remove rather than deleted.

import copy
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Keys whose list values must never shrink during re-analysis
APPEND_ONLY_KEYS: List[str] = [
    "investigation_plan",
    "witnesses",
    "cross_examination_plan",
    "direct_examination_plan",
    "consistency_check",
    "legal_elements",
    "evidence_foundations",
    "timeline",
    "entities",
    "charges",
    "mock_jury_feedback",
    "legal_research_data",
    "drafted_documents",
]


def _item_signature(item: Any) -> str:
    """Produce a short signature for dedup comparison."""
    if isinstance(item, dict):
        # Use the most distinctive fields available
        for key in ("name", "action", "fact", "item", "charge", "headline", "id"):
            val = item.get(key, "")
            if val:
                return str(val).strip().lower()[:120]
        # Fallback: first 200 chars of str representation
        return str(item)[:200].lower()
    return str(item)[:200].lower()


def merge_append_only(existing_state: Dict, new_state: Dict) -> Dict:
    """
    Merge *new_state* into *existing_state* using append-only semantics
    for keys in APPEND_ONLY_KEYS.

    Rules:
    1. Every existing item is preserved (never deleted).
    2. New items that don't match an existing signature are appended.
    3. Items that existed previously but were NOT reproduced by the AI
       get tagged with ``_ai_suggests_remove: True`` so the attorney
       can review and decide.
    4. Items explicitly marked ``_user_added: True`` or
       ``_user_completed: True`` are always preserved untouched.

    Non-append-only keys are simply overwritten by new_state.

    Returns a new merged dict.  The original *existing_state* is NOT mutated
    (a deep copy is made first to prevent in-place side-effects on callers).
    """
    existing_state = copy.deepcopy(existing_state)

    for key in APPEND_ONLY_KEYS:
        old_items = existing_state.get(key, [])
        new_items = new_state.get(key, [])

        if not isinstance(old_items, list):
            old_items = []
        if not isinstance(new_items, list):
            new_items = []

        if not new_items:
            # AI returned nothing for this key - keep existing, don't touch
            continue

        # Build signature sets
        old_sigs = {_item_signature(it) for it in old_items}
        new_sigs = {_item_signature(it) for it in new_items}

        # Tag existing items not reproduced (unless user-pinned)
        for it in old_items:
            if isinstance(it, dict):
                sig = _item_signature(it)
                if sig not in new_sigs:
                    if not it.get("_user_added") and not it.get("_user_completed"):
                        it["_ai_suggests_remove"] = True
                else:
                    # Re-confirmed by AI - clear the flag
                    it.pop("_ai_suggests_remove", None)

        # Append genuinely new items
        for it in new_items:
            sig = _item_signature(it)
            if sig not in old_sigs:
                old_items.append(it)
                old_sigs.add(sig)

        existing_state[key] = old_items

    # Overwrite non-append-only keys
    for key, val in new_state.items():
        if key not in APPEND_ONLY_KEYS:
            existing_state[key] = val

    return existing_state


def safe_update_and_save(case_mgr_or_state, case_id_or_new=None,
                         prep_id=None, current_state=None,
                         new_state=None, save_fn=None) -> Dict:
    """
    Merge new analysis results using append-only semantics and persist.

    Supports two calling conventions:

    1. UI convention (5 args):
       ``safe_update_and_save(case_mgr, case_id, prep_id, agent_results, updates)``
       Merges *updates* into *agent_results* and saves via case_mgr.

    2. Functional convention (3 args):
       ``safe_update_and_save(current_state, new_state, save_fn)``
       Merges *new_state* into *current_state* and calls *save_fn(merged)*.

    Returns the merged state dict (also updates st.session_state.agent_results
    in the UI convention).
    """
    # Detect calling convention by argument types
    if prep_id is not None and current_state is not None and new_state is not None:
        # UI convention: (case_mgr, case_id, prep_id, agent_results, updates)
        cm = case_mgr_or_state
        cid = case_id_or_new
        pid = prep_id
        existing = current_state or {}
        updates = new_state

        merged = merge_append_only(existing, updates)
        try:
            cm.save_prep_state(cid, pid, merged)
        except Exception:
            logger.exception("Failed to save merged state for %s/%s", cid, pid)
            raise

        # Update session state if available
        try:
            import streamlit as st
            st.session_state.agent_results = merged
        except Exception:
            pass

        return merged
    else:
        # Functional convention: (current_state, new_state, save_fn)
        _current = case_mgr_or_state
        _new = case_id_or_new
        _save = prep_id  # 3rd positional arg

        if not isinstance(_current, dict):
            _current = {}
        if not isinstance(_new, dict):
            _new = {}

        merged = merge_append_only(_current, _new)
        if callable(_save):
            try:
                _save(merged)
            except Exception:
                logger.exception("Failed to save merged state")
                raise
        return merged
