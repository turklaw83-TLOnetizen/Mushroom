# ---- Sidebar Navigation ---------------------------------------------------
# Renders the sidebar: brand, user badge, case selector, prep selector,
# model selector, API keys, session costs, case management, exports, etc.
# Navigation group buttons removed — nav moved into case_view.py as dropdown.

import json
import logging
import os

import streamlit as st

from ui.shared import (
    get_case_manager,
    get_user_manager,
    get_model_provider,
    load_case,
    load_preparation,
    is_admin,
    get_user_case_ids,
    get_current_user,
    PROJECT_ROOT,
    ENV_PATH,
)
from core.case_manager import CaseManager

logger = logging.getLogger(__name__)


# ---- Prep-Type-Aware Navigation Groups ----

def get_nav_groups(prep_type: str = "trial", admin: bool = False) -> dict:
    """Return navigation groups filtered by preparation type."""
    if prep_type == "motion_hearing":
        groups = {
            "Core Analysis": [
                "Chat", "Summary", "Devil's Advocate",
                "Investigation Plan",
                "Notes", "Deadlines", "Readiness",
            ],
            "Evidence & Facts": [
                "Consistency Check", "Elements Map",
                "Cross-References", "Doc Compare",
            ],
            "Research & Draft": [
                "Draft Document",
                "Legal Research", "Lexis+ Assistant", "Cheat Sheet",
            ],
            "Tools": [
                "Voice-to-Brief", "Conflict Check",
            ],
            "Ethical Compliance": [
                "Dashboard", "Smart Conflicts", "Prospective Clients",
                "Communication Gaps", "Trust Account", "Fee Agreements",
                "Litigation Hold", "Withdrawal", "Supervision",
                "Ethics Reference", "Reporting", "SOL Tracker",
                "Letters", "Sentencing",
            ],
            "Billing": [
                "Time & Expense", "Invoices", "Retainer", "Payments & Aging", "Fee Agreement", "Trust Ledger",
            ],
            "Client CRM": [
                "Contacts", "Prospective", "Contact Log",
            ],
            "Calendar": [
                "Events", "Deadlines", "Reminders",
            ],
            "E-Signature": [
                "Documents", "Templates", "Status",
            ],
            "Tasks": [
                "Task Board",
            ],
            "Email": [
                "Email Queue",
            ],
            "Activity": [
                "Activity Log",
            ],
        }
    elif prep_type == "prelim_hearing":
        groups = {
            "Core Analysis": [
                "Chat", "Summary", "Network", "Devil's Advocate",
                "Investigation Plan",
                "Notes", "Deadlines", "Readiness",
            ],
            "Evidence & Facts": [
                "Evidence Foundations", "Consistency Check", "Elements Map",
                "Timeline", "Entities", "Cross-References", "Doc Compare",
            ],
            "Witnesses & Exam": [
                "Witnesses", "Cross-Exam",
                "Deposition", "Depo Outline", "Witness Prep", "Interview Planner",
            ],
            "Research & Draft": [
                "Draft Document",
                "Legal Research", "Lexis+ Assistant", "Cheat Sheet",
            ],
            "Tools": [
                "Voice-to-Brief", "Exhibit Plan", "Exhibit List", "Conflict Check",
            ],
            "Ethical Compliance": [
                "Dashboard", "Smart Conflicts", "Prospective Clients",
                "Communication Gaps", "Trust Account", "Fee Agreements",
                "Litigation Hold", "Withdrawal", "Supervision",
                "Ethics Reference", "Reporting", "SOL Tracker",
                "Letters", "Sentencing",
            ],
            "Billing": [
                "Time & Expense", "Invoices", "Retainer", "Payments & Aging", "Fee Agreement", "Trust Ledger",
            ],
            "Client CRM": [
                "Contacts", "Prospective", "Contact Log",
            ],
            "Calendar": [
                "Events", "Deadlines", "Reminders",
            ],
            "E-Signature": [
                "Documents", "Templates", "Status",
            ],
            "Tasks": [
                "Task Board",
            ],
            "Email": [
                "Email Queue",
            ],
            "Activity": [
                "Activity Log",
            ],
        }
    else:
        # Trial — full set
        groups = {
            "Core Analysis": [
                "Chat", "Summary", "Network", "Devil's Advocate",
                "Investigation Plan",
                "Notes", "Deadlines", "Readiness",
            ],
            "Evidence & Facts": [
                "Evidence Foundations", "Consistency Check", "Elements Map",
                "Timeline", "Entities", "Medical Records", "Medical Chronology",
                "Cross-References", "Doc Compare", "Missing Discovery",
            ],
            "Witnesses & Exam": [
                "Witnesses", "Cross-Exam", "Direct Exam",
                "Deposition", "Depo Outline", "Witness Prep", "Interview Planner",
            ],
            "Strategy & Jury": [
                "Voir Dire", "Mock Jury", "Simulator",
                "Client Report", "Statements", "Opponent Playbook",
                "Case Theory", "Jury Instructions",
            ],
            "Research & Draft": [
                "Draft Document", "Spreadsheet",
                "Legal Research", "Lexis+ Assistant", "Demand Letter", "Cheat Sheet",
            ],
            "Tools": [
                "Voice-to-Brief", "Exhibit Plan", "Exhibit List",
                "Quick Cards", "Conflict Check",
            ],
            "Ethical Compliance": [
                "Dashboard", "Smart Conflicts", "Prospective Clients",
                "Communication Gaps", "Trust Account", "Fee Agreements",
                "Litigation Hold", "Withdrawal", "Supervision",
                "Ethics Reference", "Reporting", "SOL Tracker",
                "Letters", "Sentencing",
            ],
            "Billing": [
                "Time & Expense", "Invoices", "Retainer", "Payments & Aging", "Fee Agreement", "Trust Ledger",
            ],
            "Client CRM": [
                "Contacts", "Prospective", "Contact Log",
            ],
            "Calendar": [
                "Events", "Deadlines", "Reminders",
            ],
            "E-Signature": [
                "Documents", "Templates", "Status",
            ],
            "Tasks": [
                "Task Board",
            ],
            "Email": [
                "Email Queue",
            ],
            "Activity": [
                "Activity Log",
            ],
        }

    if admin:
        groups["User Admin"] = ["Team", "Add User", "Assign Cases"]

    return groups


# Keep a static reference for backward compat (used by page modules)
NAV_GROUPS = get_nav_groups("trial", admin=True)


def render_sidebar():
    """Render the full sidebar navigation."""
    case_mgr = get_case_manager()
    user = get_current_user()

    with st.sidebar:
        # ---- Brand Header ----
        st.markdown(
            """
            <div style='text-align:center; padding: 8px 0 12px;'>
                <h2 style='margin:0; font-size:1.4rem;'>\u2696\ufe0f AllRise Beta</h2>
                <p style='opacity:0.5; font-size:0.75rem; margin:2px 0;'>Legal Intelligence Suite</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # ---- User Badge & Sign Out ----
        if user:
            from core.user_profiles import ROLE_LABELS

            _u_role_label = ROLE_LABELS.get(
                user.get("role", ""), user.get("role", "")
            )
            st.markdown(
                f"""<div style='padding:6px 12px; margin:4px 0 8px; border-radius:8px;
                    background:rgba(99,102,241,0.12); border:1px solid rgba(99,102,241,0.25);'>
                    <span style='font-weight:600;'>{user.get('initials', '')}</span>
                    <span style='opacity:0.7; margin-left:6px;'>{user.get('name', '')}</span><br/>
                    <span style='font-size:0.78rem; opacity:0.55;'>{_u_role_label}</span>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                "\U0001f6aa Sign Out", key="_sign_out", use_container_width=True
            ):
                _was_google = st.session_state.get("login_method") == "google"
                for key in [
                    "current_user", "login_method", "current_case_id",
                    "current_prep_id", "agent_results", "chat_history",
                ]:
                    st.session_state.pop(key, None)
                if _was_google:
                    try:
                        st.logout()
                    except Exception as _logout_err:
                        logger.debug("st.logout() unavailable, falling back to rerun: %s", _logout_err)
                        st.rerun()
                else:
                    st.rerun()

        st.divider()

        # ---- Notification Bell ----
        try:
            from core.notifications import get_notifications
            _case_mgr_notif = get_case_manager()
            _user_notif = get_current_user()
            _notif_user_id = _user_notif.get("id", "") if _user_notif else ""
            _notifications = get_notifications(_case_mgr_notif, user_id=_notif_user_id)
            _notif_count = len(_notifications)
            if _notif_count > 0:
                _notif_label = f"\U0001f514 {_notif_count} Alert{'s' if _notif_count != 1 else ''}"
                with st.popover(_notif_label, use_container_width=True):
                    st.markdown("#### \U0001f514 Notifications")
                    for _ni, _notif in enumerate(_notifications[:15]):
                        _sev = _notif.get("severity", "low")
                        _sev_icon = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f535"}.get(_sev, "\u26aa")
                        _n_title = _notif.get("title", "")
                        _n_detail = _notif.get("detail", "")
                        _n_case = _notif.get("case_name", "")
                        st.markdown(f"{_sev_icon} **{_n_title}**")
                        if _n_detail:
                            st.caption(_n_detail)
                        if _n_case and _n_case not in _n_detail:
                            st.caption(f"\U0001f4c1 {_n_case}")
                        if _ni < min(len(_notifications), 15) - 1:
                            st.divider()
                    if _notif_count > 15:
                        st.caption(f"... and {_notif_count - 15} more")
        except Exception as _notif_err:
            logger.warning("Failed to load notifications: %s", _notif_err)
            st.caption("\u26a0\ufe0f Notifications unavailable")

        # ---- Back to Cases (when inside a case) ----
        if st.session_state.get("current_case_id"):
            if st.button(
                "\u2190 Back to Cases",
                key="_back_to_cases",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.current_case_id = None
                st.session_state.current_prep_id = None
                st.session_state.agent_results = None
                st.session_state.chat_history = []
                try:
                    st.query_params.clear()
                except Exception as _qp_err:
                    logger.debug("Could not clear query params: %s", _qp_err)
                st.rerun()
            st.divider()

        # ---- Theme Selector ----
        theme_icons = {"dark": "\U0001f319 Dark", "grey": "\U0001f32b\ufe0f Slate", "light": "\u2600\ufe0f Light"}
        theme_options = ["dark", "grey", "light"]
        current_theme = st.session_state.get("theme", "dark")
        current_idx = (
            theme_options.index(current_theme) if current_theme in theme_options else 0
        )
        selected_theme = st.selectbox(
            "Theme",
            theme_options,
            index=current_idx,
            format_func=lambda x: theme_icons.get(x, x),
            key="theme_selector",
        )
        if selected_theme != current_theme:
            st.session_state.theme = selected_theme
            st.rerun()

        # ---- Encryption Management (Admin Only) ----
        if user and user.get("role") == "admin":
            _data_dir = str(PROJECT_ROOT / "data")
            from core.storage.encrypted_backend import (
                is_encryption_enabled,
                enable_encryption_marker,
                write_verification_token,
                derive_encryption_key,
                get_or_create_salt,
                encrypt_existing_data,
            )
            _enc_enabled = is_encryption_enabled(_data_dir)
            with st.expander(
                f"\U0001f512 Encryption {'(Active)' if _enc_enabled else '(Off)'}",
                expanded=False,
            ):
                if _enc_enabled:
                    st.success("Data encryption is **active**. All files are encrypted at rest.")
                    st.caption("To change your passphrase, disable encryption first, then re-enable.")
                else:
                    st.warning("Data encryption is **not enabled**.")
                    st.caption(
                        "Enable encryption to protect all case data, documents, and OCR cache at rest."
                    )
                    _enc_pass = st.text_input(
                        "Create encryption passphrase:",
                        type="password",
                        key="_enc_setup_pass",
                    )
                    _enc_confirm = st.text_input(
                        "Confirm passphrase:",
                        type="password",
                        key="_enc_setup_confirm",
                    )
                    if st.button(
                        "\U0001f512 Enable Encryption",
                        key="_enc_enable_btn",
                        type="primary",
                        use_container_width=True,
                        disabled=not (_enc_pass and _enc_confirm and _enc_pass == _enc_confirm),
                    ):
                        if len(_enc_pass) < 8:
                            st.error("Passphrase must be at least 8 characters.")
                        else:
                            _salt = get_or_create_salt(_data_dir)
                            _key = derive_encryption_key(_enc_pass, _salt)
                            with st.spinner("Encrypting existing data..."):
                                _stats = encrypt_existing_data(_data_dir, _key)
                            write_verification_token(_data_dir, _enc_pass)
                            enable_encryption_marker(_data_dir)
                            st.session_state._encryption_key = _key
                            # Force storage backend to reinitialize
                            st.session_state.pop("_storage_backend", None)
                            st.session_state.pop("_case_manager", None)
                            st.success(
                                f"Encryption enabled! "
                                f"{_stats['files_encrypted']} files encrypted, "
                                f"{_stats['files_skipped']} already encrypted."
                            )
                            if _stats["errors"] > 0:
                                st.warning(f"{_stats['errors']} files had errors during encryption.")
                            st.rerun()

        st.divider()

        # ---- Logo (if exists) ----
        logo_path = str(PROJECT_ROOT / "assets" / "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)

        # ---- Model Selector ----
        providers = [
            "claude-opus-4.6", "claude-sonnet-4.6", "claude-sonnet-4.5",
            "xai", "gemini",
        ]
        provider_labels = {
            "claude-opus-4.6": "Claude Opus 4.6",
            "claude-sonnet-4.6": "Claude Sonnet 4.6",
            "claude-sonnet-4.5": "Claude Sonnet 4.5",
            "xai": "Grok (xAI)",
            "gemini": "Gemini Pro",
        }
        current_provider = get_model_provider()
        provider_idx = (
            providers.index(current_provider) if current_provider in providers else 0
        )
        selected_provider = st.selectbox(
            "AI Model",
            providers,
            index=provider_idx,
            key="_nav_model",
            format_func=lambda p: provider_labels.get(p, p),
            help="Select a model. Gemini Pro has 1M context. Sonnet 4.6 & Opus 4.6 support 1M.",
        )
        if selected_provider != st.session_state.get("model_provider"):
            st.session_state.model_provider = selected_provider

        # ---- Max Context Toggle ----
        if "_max_context_mode" not in st.session_state:
            st.session_state._max_context_mode = True
        _mcx = st.toggle(
            "\U0001f4d0 Max Context",
            value=st.session_state.get("_max_context_mode", True),
            key="_sidebar_max_ctx",
            help="Sends ALL document text without truncation. Slower & more expensive.",
        )
        st.session_state._max_context_mode = _mcx

        st.divider()

        # ---- API Keys ----
        st.subheader("\U0001f511 API Keys")
        _render_api_key("Grok (XAI) API Key", "XAI_API_KEY", "xai_key_input")
        _render_api_key("Anthropic API Key", "ANTHROPIC_API_KEY", "anthropic_key_input")
        _render_api_key("Google (Gemini) API Key", "GOOGLE_API_KEY", "google_key_input")
        _render_api_key("OpenAI API Key (Audio)", "OPENAI_API_KEY", "openai_key_input")

        st.markdown("---")

        # ---- Session Cost Tracker ----
        session_costs = st.session_state.get("session_costs", {})
        if session_costs.get("total_cost", 0) > 0 or session_costs.get("calls"):
            st.caption("\U0001f4b0 Session Costs")
            sc1, sc2 = st.columns(2)
            sc1.metric("Cost", f"${session_costs.get('total_cost', 0):.4f}")
            sc2.metric("Tokens", f"{session_costs.get('total_tokens', 0):,}")
            calls = session_costs.get("calls", [])
            if calls:
                with st.expander(f"\U0001f4cb {len(calls)} API calls"):
                    for call in reversed(calls[-5:]):
                        st.caption(
                            f"{call.get('action', 'Analysis')} \u2014 "
                            f"${call.get('cost', 0):.4f} ({call.get('tokens', 0):,} tokens)"
                        )
            st.markdown("---")

        # ---- Deadline Badges ----
        try:
            _all_reminders = case_mgr.get_active_reminders()
            if _all_reminders:
                _overdue = sum(
                    1 for d in _all_reminders if d.get("days_remaining", 999) < 0
                )
                _today = sum(
                    1 for d in _all_reminders if d.get("days_remaining", 999) == 0
                )
                _soon = len(_all_reminders) - _overdue - _today
                if _overdue > 0:
                    st.error(
                        f"\U0001f6a8 {_overdue} OVERDUE deadline{'s' if _overdue != 1 else ''}!"
                    )
                if _today > 0:
                    st.warning(
                        f"\U0001f534 {_today} deadline{'s' if _today != 1 else ''} TODAY"
                    )
                if _soon > 0:
                    st.info(
                        f"\U0001f4c5 {_soon} upcoming deadline{'s' if _soon != 1 else ''}"
                    )
                st.markdown("---")
        except Exception as _dl_err:
            logger.warning("Failed to load deadline badges: %s", _dl_err)
            st.caption("\u26a0\ufe0f Deadline badges unavailable")

        # ---- Case-Specific Sidebar (when case is open) ----
        current_case_id = st.session_state.get("current_case_id")
        if current_case_id:
            st.info(f"\U0001f4c1 Active Case: {case_mgr.get_case_name(current_case_id)}")

            # Rename case
            new_name_input = st.text_input(
                "Rename Case",
                value=case_mgr.get_case_name(current_case_id),
                key="_rename_case",
            )
            if st.button("Update Name", key="_update_name"):
                case_mgr.rename_case(current_case_id, new_name_input)
                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                st.success("Renamed!")
                st.rerun()

            # Phase Management / Clone
            _cur_phase, _cur_sub = case_mgr.get_phase(current_case_id)

            if _cur_phase == "active":
                phase_col, clone_col = st.columns(2)
                with phase_col:
                    if st.button("📋 Close Case", use_container_width=True,
                                 help="Mark as resolved. Files remain accessible. "
                                      "Auto-archives after 21 days."):
                        case_mgr.set_phase(current_case_id, "closed")
                        st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        st.success("Case closed!")
                        st.rerun()
                with clone_col:
                    with st.popover("\U0001f4cb Clone Case", use_container_width=True):
                        _clone_name = st.text_input(
                            "Name for cloned case",
                            value=f"{case_mgr.get_case_name(current_case_id)} (Copy)",
                            key="_clone_name",
                        )
                        if st.button(
                            "Clone", key="_clone_btn", type="primary", use_container_width=True
                        ):
                            new_id = case_mgr.clone_case(current_case_id, _clone_name)
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                            st.success(f"Cloned as '{_clone_name}'!")
                            load_case(new_id)
            elif _cur_phase == "closed":
                _c1, _c2, _c3 = st.columns(3)
                with _c1:
                    if st.button("🔓 Reopen", use_container_width=True):
                        case_mgr.set_phase(current_case_id, "active")
                        st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        st.success("Case reopened!")
                        st.rerun()
                with _c2:
                    if st.button("📦 Archive", use_container_width=True):
                        case_mgr.set_phase(current_case_id, "archived")
                        st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        st.session_state.current_case_id = None
                        st.session_state.agent_results = None
                        st.success("Case archived!")
                        st.rerun()
                with _c3:
                    with st.popover("\U0001f4cb Clone", use_container_width=True):
                        _clone_name = st.text_input(
                            "Name for cloned case",
                            value=f"{case_mgr.get_case_name(current_case_id)} (Copy)",
                            key="_clone_name",
                        )
                        if st.button(
                            "Clone", key="_clone_btn", type="primary", use_container_width=True
                        ):
                            new_id = case_mgr.clone_case(current_case_id, _clone_name)
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                            st.success(f"Cloned as '{_clone_name}'!")
                            load_case(new_id)
            elif _cur_phase == "archived":
                _purged = case_mgr.storage.get_case_metadata(current_case_id).get("purged", False)
                _ac1, _ac2 = st.columns(2)
                with _ac1:
                    if st.button("🔓 Unarchive", use_container_width=True):
                        case_mgr.set_phase(current_case_id, "active")
                        st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        st.success("Case unarchived!")
                        st.rerun()
                with _ac2:
                    with st.popover("\U0001f4cb Clone", use_container_width=True):
                        _clone_name = st.text_input(
                            "Name for cloned case",
                            value=f"{case_mgr.get_case_name(current_case_id)} (Copy)",
                            key="_clone_name",
                        )
                        if st.button(
                            "Clone", key="_clone_btn", type="primary", use_container_width=True
                        ):
                            new_id = case_mgr.clone_case(current_case_id, _clone_name)
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                            st.success(f"Cloned as '{_clone_name}'!")
                            load_case(new_id)
                # Purge section (full width, below buttons)
                if not _purged:
                    st.caption("⚠️ Purging permanently deletes source documents from the app.")
                    if st.button("🗑️ Purge Source Files", use_container_width=True):
                        st.session_state["_confirm_purge"] = True
                    if st.session_state.get("_confirm_purge"):
                        _p_files = case_mgr.get_case_files(current_case_id)
                        st.warning(f"This will delete **{len(_p_files)} file(s)** from this case. "
                                   "OCR text and analysis results will be preserved. "
                                   "Make sure originals are backed up in Dropbox.")
                        _pc1, _pc2 = st.columns(2)
                        with _pc1:
                            if st.button("✅ Confirm Purge", type="primary", use_container_width=True):
                                _purge_count = case_mgr.purge_source_docs(current_case_id)
                                st.session_state["_confirm_purge"] = False
                                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                                st.success(f"Purged {_purge_count} file(s).")
                                st.rerun()
                        with _pc2:
                            if st.button("❌ Cancel", use_container_width=True):
                                st.session_state["_confirm_purge"] = False
                                st.rerun()
                else:
                    st.caption("✓ Source files already purged")

            # Case Journal
            st.markdown("---")
            with st.expander("\U0001f4d3 **Case Journal**", expanded=False):
                _jnl_entries = case_mgr.load_journal(current_case_id)

                _jnl_text = st.text_area(
                    "Quick note",
                    key="_jnl_new_text",
                    height=60,
                    placeholder="Type a note about this case...",
                )
                _jnl_cats = [
                    "General", "Strategy", "Witness", "Evidence",
                    "To-Do", "Hearing", "Negotiation",
                ]
                _jnl_cat = st.selectbox("Category", _jnl_cats, key="_jnl_cat")
                if st.button(
                    "\u2795 Add Entry",
                    key="_jnl_add",
                    use_container_width=True,
                    disabled=not _jnl_text,
                ):
                    case_mgr.add_journal_entry(current_case_id, _jnl_text, _jnl_cat)
                    st.success("Note added!")
                    st.rerun()

                if _jnl_entries:
                    st.caption(f"{len(_jnl_entries)} entries")
                    for _je in _jnl_entries[:20]:
                        _ts = _je.get("timestamp", "")[:16].replace("T", " ")
                        _cat_icon = {
                            "Strategy": "\u265f\ufe0f",
                            "Witness": "\U0001f464",
                            "Evidence": "\U0001f4ce",
                            "To-Do": "\u2611\ufe0f",
                            "Hearing": "\U0001f3db\ufe0f",
                        }.get(_je.get("category", ""), "\U0001f4dd")
                        with st.container(border=True):
                            st.caption(
                                f"{_cat_icon} {_je.get('category', 'General')} \u00b7 {_ts}"
                            )
                            st.markdown(_je.get("text", ""))
                            if st.button(
                                "\U0001f5d1\ufe0f",
                                key=f"_jdel_{_je.get('id', '')}",
                                help="Delete",
                            ):
                                case_mgr.delete_journal_entry(
                                    current_case_id, _je.get("id", "")
                                )
                                st.rerun()
                else:
                    st.caption("No journal entries yet.")

            # Negotiations Tracker
            st.markdown("---")
            with st.expander("\U0001f91d **Negotiations Tracker**", expanded=False):
                _neg_prep = st.session_state.get("current_prep_id", "")
                if _neg_prep:
                    _neg_notes = case_mgr.load_module_notes(
                        current_case_id, _neg_prep, "negotiations"
                    )
                    _new_neg_notes = st.text_area(
                        "Negotiation notes:",
                        value=_neg_notes,
                        height=250,
                        key=f"_notes_negotiations_{_neg_prep}",
                        placeholder="Track offers, counteroffers, and negotiation history...",
                    )
                    if _new_neg_notes != _neg_notes:
                        case_mgr.save_module_notes(
                            current_case_id, _neg_prep, "negotiations", _new_neg_notes
                        )
                        st.toast("\U0001f91d Negotiation notes saved", icon="\u2705")
                else:
                    st.caption("Select a preparation to track negotiations.")

            # Phase Configuration
            with st.expander("⚙️ **Customize Case Phases**", expanded=False):
                _phase_cfg = case_mgr.get_phase_config()
                _cfg_types = list(_phase_cfg.keys())
                _cfg_sel = st.selectbox("Case Type", _cfg_types, key="_phase_cfg_type")
                _cfg_current = _phase_cfg.get(_cfg_sel, [])
                _cfg_edited = st.text_area(
                    "Sub-Phases (one per line)",
                    value="\n".join(_cfg_current),
                    height=200,
                    key=f"_phase_cfg_edit_{_cfg_sel}",
                )
                _cfg_new = [p.strip() for p in _cfg_edited.split("\n") if p.strip()]
                if _cfg_new != _cfg_current:
                    if st.button("💾 Save Phase Config", key="_phase_cfg_save"):
                        _phase_cfg[_cfg_sel] = _cfg_new
                        case_mgr.save_phase_config(_phase_cfg)
                        st.success(f"Updated phases for {_cfg_sel}!")
                        st.rerun()
                with st.form("_add_case_type_form"):
                    _new_ct = st.text_input("New Case Type ID (e.g. 'family')")
                    if st.form_submit_button("Add Case Type"):
                        if _new_ct and _new_ct not in _phase_cfg:
                            _phase_cfg[_new_ct] = ["Intake"]
                            case_mgr.save_phase_config(_phase_cfg)
                            st.success(f"Added case type: {_new_ct}")
                            st.rerun()

            # Delete Case (danger zone)
            st.markdown("---")
            st.caption("Danger Zone")
            delete_confirm = st.text_input(
                "Type 'delete' to confirm", placeholder="delete", key="_delete_confirm"
            )
            if st.button(
                "\U0001f5d1\ufe0f Delete Case",
                type="primary",
                disabled=(delete_confirm != "delete"),
            ):
                case_mgr.delete_case(current_case_id)
                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                st.session_state.current_case_id = None
                st.session_state.agent_results = None
                st.rerun()

            # ---- Major Document Drafter ----
            st.markdown("---")
            if st.button("\U0001f4c4 Major Document Drafter", key="_launch_major_docs", use_container_width=True, type="secondary"):
                st.session_state._md_active = True
                st.rerun()

            # Exports
            if st.session_state.get("agent_results"):
                st.markdown("### \U0001f4e5 Exports")
                _cid = current_case_id
                _pid = st.session_state.get("current_prep_id")
                _pmeta = case_mgr.get_preparation(_cid, _pid) if _pid else None
                _pname = _pmeta["name"] if _pmeta else "Analysis"
                _export_title = f"{_cid} \u2014 {_pname}"
                _safe_fname = _pname.replace(" ", "_").replace("/", "-")[:40]
                _binder_prep_type = _pmeta["type"] if _pmeta else "trial"

                # --- Export All as ZIP ---
                if st.button("\U0001f4e6 Download All Exports", key="_export_all"):
                    import zipfile, io as _io
                    _zip_buf = _io.BytesIO()
                    _zip_errors = []
                    _results = st.session_state.agent_results
                    with zipfile.ZipFile(_zip_buf, 'w', zipfile.ZIP_DEFLATED) as _zf:
                        try:
                            from core.export.word_export import generate_word_report as _gwr
                            _zf.writestr(f"{_safe_fname}_Report.docx", _gwr(_results, _export_title))
                        except Exception as _e:
                            logger.warning("ZIP export - Word report failed: %s", _e)
                            _zip_errors.append(f"Word: {_e}")
                        try:
                            from core.export.pdf_export import generate_pdf_report as _gpr
                            _zf.writestr(f"{_safe_fname}_Report.pdf", _gpr(_results, _export_title))
                        except Exception as _e:
                            logger.warning("ZIP export - PDF report failed: %s", _e)
                            _zip_errors.append(f"PDF: {_e}")
                        try:
                            from core.export.word_export import generate_brief_outline as _gbo
                            _zf.writestr(f"IRAC_Brief_{_safe_fname}.docx", _gbo(_results, _export_title))
                        except Exception as _e:
                            logger.warning("ZIP export - IRAC brief failed: %s", _e)
                            _zip_errors.append(f"Brief: {_e}")
                        try:
                            from core.export.word_export import generate_trial_binder as _gtb
                            _zf.writestr(
                                f"Trial_Binder_{_safe_fname}.docx",
                                _gtb(_results, _export_title, prep_type=_binder_prep_type, prep_name=_pname),
                            )
                        except Exception as _e:
                            logger.warning("ZIP export - Trial binder failed: %s", _e)
                            _zip_errors.append(f"Binder: {_e}")
                    _zip_buf.seek(0)
                    st.download_button(
                        "\u2b07\ufe0f Download ZIP",
                        data=_zip_buf.getvalue(),
                        file_name=f"AllExports_{_safe_fname}_{_cid}.zip",
                        mime="application/zip",
                        key="_export_all_download",
                    )
                    for _ze in _zip_errors:
                        st.warning(_ze)

                try:
                    from core.export.word_export import generate_word_report

                    docx_file = generate_word_report(
                        st.session_state.agent_results, _export_title
                    )
                    st.download_button(
                        label=f"\U0001f4e5 Word ({_pname})",
                        data=docx_file,
                        file_name=f"{_safe_fname}_{_cid}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except ImportError:
                    st.caption("Word export not available (missing dependency)")
                except Exception as _we:
                    logger.warning("Word export failed: %s", _we)
                    st.error(f"Word export failed: {_we}")

                try:
                    from core.export.pdf_export import generate_pdf_report

                    pdf_file = generate_pdf_report(
                        st.session_state.agent_results, _export_title
                    )
                    st.download_button(
                        label=f"\U0001f4e5 PDF ({_pname})",
                        data=pdf_file,
                        file_name=f"{_safe_fname}_{_cid}.pdf",
                        mime="application/pdf",
                    )
                except ImportError:
                    st.caption("PDF export not available (missing dependency)")
                except Exception as _pe:
                    logger.warning("PDF export failed: %s", _pe)
                    st.error(f"PDF export failed: {_pe}")

                try:
                    from core.export.word_export import generate_brief_outline

                    brief_data = generate_brief_outline(
                        st.session_state.agent_results, _export_title
                    )
                    st.download_button(
                        label=f"\U0001f4c4 IRAC Brief ({_pname})",
                        data=brief_data,
                        file_name=f"IRAC_Brief_{_safe_fname}_{_cid}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except ImportError:
                    st.caption("Brief export not available (missing dependency)")
                except Exception as _be:
                    logger.warning("Brief export failed: %s", _be)
                    st.error(f"IRAC Brief export failed: {_be}")

                try:
                    from core.export.word_export import generate_trial_binder

                    binder_data = generate_trial_binder(
                        st.session_state.agent_results,
                        _export_title,
                        prep_type=_binder_prep_type,
                        prep_name=_pname,
                    )
                    st.download_button(
                        label=f"\U0001f4d2 Trial Binder ({_pname})",
                        data=binder_data,
                        file_name=f"Trial_Binder_{_safe_fname}_{_cid}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except ImportError:
                    st.caption("Trial Binder export not available (missing dependency)")
                except Exception as _te:
                    logger.warning("Trial Binder export failed: %s", _te)
                    st.error(f"Trial Binder export failed: {_te}")

            # Version History
            _vh_pid = st.session_state.get("current_prep_id")
            if _vh_pid:
                st.markdown("---")
                st.caption("\U0001f4dc Version History")
                snapshots = case_mgr.list_snapshots(current_case_id, _vh_pid)
                if snapshots:
                    for snap in snapshots[:10]:
                        snap_label = snap.get("label", snap["id"])
                        snap_size = snap.get("size_kb", 0)
                        snap_col1, snap_col2, snap_col3 = st.columns([3, 0.6, 0.6])
                        with snap_col1:
                            st.caption(f"\U0001f550 {snap_label} ({snap_size}KB)")
                        with snap_col2:
                            if st.button(
                                "\u21a9\ufe0f",
                                key=f"_restore_{snap['id']}",
                                help=f"Restore {snap_label}",
                            ):
                                restored = case_mgr.restore_snapshot(
                                    current_case_id, _vh_pid, snap["id"]
                                )
                                if restored:
                                    st.session_state.agent_results = restored
                                    st.success(f"Restored: {snap_label}")
                                    st.rerun()
                        with snap_col3:
                            if st.button(
                                "\U0001f50d",
                                key=f"_compare_{snap['id']}",
                                help=f"Compare with current",
                            ):
                                st.session_state["_compare_snapshot_id"] = snap["id"]
                                st.session_state["_compare_snapshot_label"] = snap_label

                    # Snapshot comparison viewer
                    _cmp_snap_id = st.session_state.get("_compare_snapshot_id")
                    _cmp_snap_label = st.session_state.get("_compare_snapshot_label", "")
                    if _cmp_snap_id:
                        _snap_state = case_mgr.load_snapshot(
                            current_case_id, _vh_pid, _cmp_snap_id
                        )
                        _current_state = st.session_state.get("agent_results", {}) or {}
                        if _snap_state:
                            with st.expander(
                                f"\U0001f50d Comparing: **{_cmp_snap_label}** vs Current",
                                expanded=True,
                            ):
                                _compare_keys = [
                                    "case_summary", "strategy_notes", "witnesses",
                                    "cross_examination_plan", "direct_examination_plan",
                                    "timeline", "evidence_foundations", "consistency_check",
                                    "legal_elements", "investigation_plan", "entities",
                                    "devils_advocate_notes", "voir_dire", "mock_jury_feedback",
                                ]
                                _changes_found = False
                                for _ck in _compare_keys:
                                    _snap_val = _snap_state.get(_ck)
                                    _cur_val = _current_state.get(_ck)
                                    _snap_exists = bool(_snap_val)
                                    _cur_exists = bool(_cur_val)

                                    if _snap_exists != _cur_exists:
                                        _changes_found = True
                                        if _cur_exists and not _snap_exists:
                                            st.markdown(f"**{_ck}**: \U0001f7e2 Added (new)")
                                        else:
                                            st.markdown(f"**{_ck}**: \U0001f534 Removed")
                                    elif _snap_exists and _cur_exists:
                                        _snap_str = str(_snap_val)
                                        _cur_str = str(_cur_val)
                                        if _snap_str != _cur_str:
                                            _changes_found = True
                                            _snap_len = len(_snap_str)
                                            _cur_len = len(_cur_str)
                                            _delta = _cur_len - _snap_len
                                            _delta_str = (
                                                f"+{_delta}" if _delta > 0
                                                else str(_delta)
                                            )
                                            st.markdown(
                                                f"**{_ck}**: \U0001f7e1 Modified "
                                                f"({_delta_str} chars)"
                                            )

                                if not _changes_found:
                                    st.success("No differences found between snapshot and current state.")

                                if st.button("Close comparison", key="_close_compare"):
                                    st.session_state.pop("_compare_snapshot_id", None)
                                    st.session_state.pop("_compare_snapshot_label", None)
                                    st.rerun()
                else:
                    st.caption(
                        "No snapshots yet. Snapshots are created automatically before each analysis."
                    )

        else:
            st.info("No case selected.")


def _render_api_key(label: str, env_var: str, key: str):
    """Render an API key input that persists to .env."""
    val = st.text_input(
        label,
        value=os.environ.get(env_var, ""),
        type="password",
        key=key,
    )
    if val and val != os.environ.get(env_var, ""):
        os.environ[env_var] = val
        try:
            from dotenv import set_key

            set_key(ENV_PATH, env_var, val)
        except ImportError:
            pass
