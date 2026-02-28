# ---- Shared UI Utilities --------------------------------------------------
# This module replaces the _app_proxy hack from the original app.py.
# UI page modules import from here instead of `from app import ...`.

import logging
import os
import threading
from pathlib import Path

import streamlit as st

from core.case_manager import CaseManager
from core.config import CONFIG
from core.cost_tracker import format_cost_badge, estimate_analysis_cost
from core.readiness import compute_readiness_score, readiness_color, readiness_label
from core.citations import render_with_references
from core.llm import get_llm, invoke_with_retry, invoke_with_retry_streaming
from core.state import AgentState, get_case_context
from core.storage.json_backend import JSONStorageBackend
from core.storage.encrypted_backend import (
    EncryptedStorageBackend,
    is_encryption_enabled,
    derive_encryption_key,
    get_or_create_salt,
)
from core.append_only import APPEND_ONLY_KEYS, merge_append_only, safe_update_and_save
from core.user_profiles import UserManager, ROLE_LABELS

logger = logging.getLogger(__name__)

# ---- Project Paths -------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = str(PROJECT_ROOT / "data" / "cases")
ENV_PATH = str(PROJECT_ROOT / ".env")

# ---- Singleton Managers --------------------------------------------------
# Lazy-initialized singletons stored in session state.


def get_storage():
    """Return the shared storage backend instance (encrypted or plain)."""
    if "_storage_backend" not in st.session_state:
        data_dir = str(PROJECT_ROOT / "data")
        if is_encryption_enabled(data_dir) and "_encryption_key" in st.session_state:
            st.session_state._storage_backend = EncryptedStorageBackend(
                data_dir, st.session_state._encryption_key
            )
        else:
            st.session_state._storage_backend = JSONStorageBackend(data_dir)
    return st.session_state._storage_backend


def get_case_manager() -> CaseManager:
    """Return the shared CaseManager instance."""
    if "_case_manager" not in st.session_state:
        st.session_state._case_manager = CaseManager(get_storage())
    return st.session_state._case_manager


def get_user_manager() -> UserManager:
    """Return the shared UserManager instance."""
    if "_user_manager" not in st.session_state:
        st.session_state._user_manager = UserManager()
    return st.session_state._user_manager


# ---- Session State Helpers -----------------------------------------------

def init_session_state():
    """Initialize all session state keys with defaults."""
    defaults = {
        "current_case_id": None,
        "current_prep_id": None,
        "agent_results": None,
        "chat_history": [],
        "current_user": None,
        "login_method": None,
        "theme": "dark",
        "session_costs": {"total_tokens": 0, "total_cost": 0.0, "calls": []},
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_current_user():
    """Return the current logged-in user dict, or None."""
    return st.session_state.get("current_user")


def is_admin() -> bool:
    """Return True if the current user has admin role."""
    user = get_current_user()
    return user is not None and user.get("role") == "admin"


def get_user_case_ids():
    """Return the list of case IDs the current user is allowed to access, or None for all."""
    user = get_current_user()
    if user is None:
        return None
    return get_user_manager().get_cases_for_user(user["id"])


# ---- Case Loading --------------------------------------------------------

def load_case(case_id: str):
    """Load a case into session state. Handles legacy migration."""
    case_mgr = get_case_manager()
    st.session_state.current_case_id = case_id
    st.session_state.chat_history = []

    # Auto-migrate legacy cases
    if case_mgr.is_legacy_case(case_id):
        case_mgr.migrate_legacy_case(case_id)

    # Load first preparation if available
    preps = case_mgr.list_preparations(case_id)
    if preps:
        prep_id = preps[0]["id"]
        st.session_state.current_prep_id = prep_id
        st.session_state.agent_results = case_mgr.load_prep_state(case_id, prep_id)
    else:
        st.session_state.current_prep_id = None
        st.session_state.agent_results = None

    st.rerun()


def load_preparation(case_id: str, prep_id: str):
    """Switch to a different preparation within the same case."""
    case_mgr = get_case_manager()
    st.session_state.current_prep_id = prep_id
    st.session_state.agent_results = case_mgr.load_prep_state(case_id, prep_id)
    st.session_state.chat_history = []
    st.rerun()


def save_current_state():
    """Save the current agent_results back to the active preparation."""
    case_id = st.session_state.get("current_case_id")
    prep_id = st.session_state.get("current_prep_id")
    results = st.session_state.get("agent_results")
    if case_id and prep_id and results:
        get_case_manager().save_prep_state(case_id, prep_id, results)


# ---- Model Provider Helper -----------------------------------------------

def get_model_provider() -> str:
    """Return the currently selected model provider from session state or config."""
    return st.session_state.get("model_provider",
                                CONFIG.get("llm", {}).get("default_provider", "xai"))


# ---- User-Friendly Error Messages ----------------------------------------

_ERROR_PATTERNS = [
    # API key / auth issues
    ("api_key", "No API key configured. Please add your API key in the sidebar settings."),
    ("invalid_api_key", "Your API key appears to be invalid. Check the key in sidebar settings."),
    ("authentication", "Authentication failed. Verify your API key is correct and active."),
    ("unauthorized", "Authentication failed. Verify your API key is correct and active."),
    ("401", "Authentication failed. Verify your API key is correct and active."),
    # Rate limits / quota
    ("rate_limit", "API rate limit reached. Wait a moment and try again."),
    ("429", "API rate limit reached. Wait a moment and try again."),
    ("insufficient_quota", "API quota exhausted. Check your billing at your API provider's dashboard."),
    ("quota", "API quota exhausted. Check your billing at your API provider's dashboard."),
    # Connection issues
    ("connection", "Could not connect to the AI service. Check your internet connection."),
    ("timeout", "The AI service took too long to respond. Try again or use a different model."),
    ("timed out", "The AI service took too long to respond. Try again or use a different model."),
    # Model issues
    ("model_not_found", "The selected AI model is not available. Try switching models in the sidebar."),
    ("context_length", "The case data is too large for this model. Try selecting fewer documents or a model with a larger context window."),
    ("maximum context length", "The case data is too large for this model. Try selecting fewer documents or a model with a larger context window."),
    ("token", "The input is too large for this model. Try reducing the amount of case data."),
    # File issues
    ("filenotfounderror", "A required file was not found. Try re-uploading your documents."),
    ("permission denied", "File access denied. Check that the data directory is writable."),
    ("no such file", "A required file was not found. Try re-uploading your documents."),
    # JSON / parsing
    ("json", "The AI returned an unexpected format. Try regenerating this module."),
    ("decode", "Data parsing error. Try regenerating this module."),
    # Generic
    ("openai", "OpenAI API error. Check your API key and billing status."),
    ("anthropic", "Anthropic API error. Check your API key and billing status."),
    ("xai", "xAI API error. Check your API key and billing status."),
]


def friendly_error(exc: Exception) -> str:
    """Translate a raw exception into a user-friendly message."""
    raw = str(exc).lower()
    for pattern, message in _ERROR_PATTERNS:
        if pattern in raw:
            return message
    # Fallback: show a cleaned-up version
    short = str(exc)
    if len(short) > 200:
        short = short[:200] + "..."
    return f"An unexpected error occurred: {short}"


def render_module_notes(case_mgr, case_id, prep_id, module_key, label=None):
    """Render an attorney notes expander for a specific module."""
    if not case_id or not prep_id:
        return
    _label = label or module_key.replace("_", " ").title()
    with st.expander(f"**Attorney Notes -- {_label}**", expanded=False):
        _notes = case_mgr.load_module_notes(case_id, prep_id, module_key)
        _new = st.text_area(
            f"Your notes on {_label.lower()}:",
            value=_notes, height=120,
            key=f"_notes_{module_key}_{prep_id}",
        )
        if _new != _notes:
            case_mgr.save_module_notes(case_id, prep_id, module_key, _new)
            st.toast("Notes saved", icon="Done")


def render_quick_ask(module_key, module_label, results, case_id, prep_id, case_mgr, model_provider):
    """Render a contextual AI quick-ask expander for a specific analysis module."""
    with st.expander(f"\U0001f4ac Ask AI about {module_label}", expanded=False):
        # Chat history in session state
        _chat_key = f"_quick_ask_{module_key}"
        if _chat_key not in st.session_state:
            st.session_state[_chat_key] = []

        # Display previous messages
        for _msg in st.session_state[_chat_key]:
            if _msg["role"] == "user":
                st.markdown(f"**You:** {_msg['content']}")
            else:
                st.markdown(f"**AI:** {_msg['content']}")

        # Input
        _qa_input = st.text_input(
            f"Ask about {module_label}...",
            key=f"_qa_input_{module_key}",
            placeholder=f"Ask a question about {module_label}...",
            label_visibility="collapsed",
        )

        _qa_col1, _qa_col2 = st.columns([1, 1])
        with _qa_col1:
            _qa_send = st.button("Send", key=f"_qa_send_{module_key}", type="primary")
        with _qa_col2:
            if st.button("Clear", key=f"_qa_clear_{module_key}"):
                st.session_state[_chat_key] = []
                st.rerun()

        if _qa_send and _qa_input and len(_qa_input.strip()) >= 2:
            # Build context from module output
            _module_data = results.get(module_key, "")
            if isinstance(_module_data, (list, dict)):
                import json as _json_mod
                _module_context = _json_mod.dumps(_module_data, default=str)[:8000]
            else:
                _module_context = str(_module_data)[:8000]

            _case_summary = results.get("case_summary", "")[:3000]

            _system_prompt = (
                f"You are a legal AI assistant analyzing the {module_label} output for a case. "
                f"Answer questions concisely and accurately based on the analysis data provided. "
                f"Reference specific findings when possible.\n\n"
                f"Case Summary:\n{_case_summary}\n\n"
                f"{module_label} Data:\n{_module_context}"
            )

            _messages = [{"role": "system", "content": _system_prompt}]
            # Add history
            for _prev in st.session_state[_chat_key][-6:]:
                _messages.append({"role": _prev["role"], "content": _prev["content"]})
            _messages.append({"role": "user", "content": _qa_input.strip()})

            try:
                llm = get_llm(model_provider)
                _response_chunks = []
                _placeholder = st.empty()
                for chunk_type, chunk_text in invoke_with_retry_streaming(llm, _messages):
                    if chunk_type == "token":
                        _response_chunks.append(chunk_text)
                        _placeholder.markdown("**AI:** " + "".join(_response_chunks))

                _full_response = "".join(_response_chunks)
                if _full_response:
                    st.session_state[_chat_key].append({"role": "user", "content": _qa_input.strip()})
                    st.session_state[_chat_key].append({"role": "assistant", "content": _full_response})
                    # Keep last 10 messages
                    if len(st.session_state[_chat_key]) > 10:
                        st.session_state[_chat_key] = st.session_state[_chat_key][-10:]
            except Exception as e:
                st.error(f"AI error: {e}")


def run_single_node(node_fn, label, state, case_mgr, case_id, prep_id,
                    model_provider, agent_results):
    """Run a single analysis node with streaming AI output, save results, show friendly errors."""
    import queue
    from core.state import set_stream_callback, clear_stream_callback

    token_q = queue.Queue()
    _result = [None]
    _error = [None]

    def _worker():
        try:
            _result[0] = node_fn(state)
        except Exception as exc:
            _error[0] = exc
        finally:
            token_q.put(None)  # Sentinel: done

    # Set stream callback so invoke_with_retry uses llm.stream()
    set_stream_callback(lambda tok: token_q.put(tok))

    worker_thread = threading.Thread(target=_worker, daemon=True)

    try:
        with st.status(f"**{label}**", expanded=True) as status_container:
            stream_placeholder = st.empty()
            worker_thread.start()

            accumulated = []
            while True:
                try:
                    tok = token_q.get(timeout=0.3)
                except queue.Empty:
                    # Update display with what we have so far
                    if accumulated:
                        stream_placeholder.markdown("".join(accumulated))
                    continue
                if tok is None:
                    break  # Worker finished
                accumulated.append(tok)
                # Update display periodically (every ~20 tokens to reduce overhead)
                if len(accumulated) % 20 == 0:
                    stream_placeholder.markdown("".join(accumulated))

            # Final display update
            if accumulated:
                stream_placeholder.markdown("".join(accumulated))

            worker_thread.join(timeout=5)

            if _error[0]:
                raise _error[0]

            updates = _result[0]
            if updates:
                safe_update_and_save(case_mgr, case_id, prep_id, agent_results, updates)
                status_container.update(label=f"**{label}** -- Complete", state="complete")
            else:
                status_container.update(label=f"**{label}** -- No updates", state="complete")
            return updates

    except Exception as exc:
        logger.warning("Node %s failed: %s", label, exc)
        user_msg = friendly_error(exc)
        st.error(f"**{label} failed:** {user_msg}")
        with st.expander("Technical details", expanded=False):
            st.code(str(exc))
        return None
    finally:
        clear_stream_callback()
