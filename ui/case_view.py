# ---- Case View (War Room) -------------------------------------------------
# Renders the case-level view when a case IS selected.
# Contains: war room header, directives, contact log, prep selector,
# war room metrics, file management, analysis engine, nav group dispatch.
# Ported from original app.py lines 2156-4831.

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from ui.shared import (
    get_case_manager,
    get_user_manager,
    get_model_provider,
    load_case,
    load_preparation,
    save_current_state,
    is_admin,
    PROJECT_ROOT,
    DATA_DIR,
)
from core.case_manager import CaseManager
from core.readiness import compute_readiness_score
from core.cost_tracker import estimate_analysis_cost, format_cost_badge
from ui.navigation import get_nav_groups

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: Inline add-client form (used by CRM dropdown slots)
# ---------------------------------------------------------------------------
def _render_add_client_form(slot_idx, case_id, case_mgr, sync_fn):
    """Show a compact inline form to quick-create a CRM client and link to case."""
    from core.crm import add_client, link_client_to_case, CLIENT_TYPES

    with st.container(border=True):
        st.markdown("**\u2795 Quick-Add Client**")
        with st.form(f"_cv_add_client_form_{slot_idx}", clear_on_submit=True):
            _nc1, _nc2 = st.columns(2)
            with _nc1:
                _nc_first = st.text_input("First Name *", key=f"_cv_nc_first_{slot_idx}")
                _nc_last = st.text_input("Last Name *", key=f"_cv_nc_last_{slot_idx}")
                _nc_phone = st.text_input("\U0001f4f1 Phone", key=f"_cv_nc_phone_{slot_idx}")
            with _nc2:
                _nc_type = st.selectbox("Client Type", CLIENT_TYPES, key=f"_cv_nc_type_{slot_idx}")
                _nc_email = st.text_input("\U0001f4e7 Email", key=f"_cv_nc_email_{slot_idx}")

            _nc_save_col, _nc_cancel_col = st.columns(2)
            with _nc_save_col:
                _nc_submit = st.form_submit_button(
                    "\U0001f4be Save & Link", type="primary", use_container_width=True,
                )
            with _nc_cancel_col:
                _nc_cancel = st.form_submit_button("Cancel", use_container_width=True)

            if _nc_submit and (_nc_first.strip() or _nc_last.strip()):
                _new_id = add_client(
                    first_name=_nc_first.strip(),
                    last_name=_nc_last.strip(),
                    client_type=_nc_type,
                    phone=_nc_phone.strip(),
                    email=_nc_email.strip(),
                    intake_status="active",
                )
                link_client_to_case(_new_id, case_id)
                sync_fn()
                st.session_state[f"_cv_adding_client_{slot_idx}"] = False
                _display = f"{_nc_first.strip()} {_nc_last.strip()}".strip()
                st.toast(f"\u2705 Client created & linked: {_display}")
                st.rerun()

            if _nc_cancel:
                st.session_state[f"_cv_adding_client_{slot_idx}"] = False
                st.rerun()


# ---------------------------------------------------------------------------
# Helper: Assigned Staff section
# ---------------------------------------------------------------------------
def _render_assigned_staff(case_id, case_mgr):
    """Render the assigned-staff dropdown(s) with multi-staff support."""
    user_mgr = get_user_manager()
    all_users = user_mgr.list_users()  # active users only
    assigned_ids = case_mgr.get_assigned_staff(case_id)

    # Build display options: show name with role
    _NONE_STAFF = "\u2014 Select Staff \u2014"
    _staff_name_to_id = {}
    _staff_names_list = []
    for _u in sorted(all_users, key=lambda x: x.get("name", "").lower()):
        _role = _u.get("role", "attorney").title()
        _display = f"{_u.get('name', '?')} ({_role})"
        _staff_name_to_id[_display] = _u.get("id", "")
        _staff_names_list.append(_display)

    def _render_staff_slot(slot_idx, current_uid, label):
        """Render a single staff dropdown slot."""
        _opts = [_NONE_STAFF] + _staff_names_list
        _cur_idx = 0
        if current_uid:
            for _i, _opt in enumerate(_opts):
                if _staff_name_to_id.get(_opt) == current_uid:
                    _cur_idx = _i
                    break

        _sel = st.selectbox(
            label,
            options=_opts,
            index=_cur_idx,
            key=f"_cv_staff_slot_{slot_idx}",
            help="Assign a firm member to this case.",
        )

        _sel_uid = _staff_name_to_id.get(_sel, "")

        # Detect change
        if _sel_uid != (current_uid or ""):
            if current_uid:
                case_mgr.remove_assigned_staff(case_id, current_uid)
            if _sel_uid:
                case_mgr.add_assigned_staff(case_id, _sel_uid)
            st.rerun()

        return _sel_uid

    # --- Determine how many slots to show ---
    _primary_uid = assigned_ids[0] if assigned_ids else ""
    _extra_uids = assigned_ids[1:] if len(assigned_ids) > 1 else []

    _staff_key = f"_cv_extra_staff_count_{case_id}"
    if _staff_key not in st.session_state:
        st.session_state[_staff_key] = max(len(_extra_uids), 0)
    if st.session_state[_staff_key] < len(_extra_uids):
        st.session_state[_staff_key] = len(_extra_uids)

    # Primary staff slot
    _render_staff_slot(0, _primary_uid, "\U0001f4bc Assigned Attorney / Staff")

    # Extra staff slots
    _extra_s_count = st.session_state.get(_staff_key, 0)
    for _si in range(_extra_s_count):
        _ex_uid = _extra_uids[_si] if _si < len(_extra_uids) else ""
        _ex_col, _rm_col = st.columns([5, 1])
        with _ex_col:
            _render_staff_slot(_si + 1, _ex_uid, f"\U0001f4bc Additional Staff #{_si + 1}")
        with _rm_col:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("\u2715", key=f"_cv_rm_staff_{_si + 1}", help="Remove this staff slot"):
                if _ex_uid:
                    case_mgr.remove_assigned_staff(case_id, _ex_uid)
                st.session_state[_staff_key] = max(
                    st.session_state.get(_staff_key, 1) - 1, 0
                )
                st.rerun()

    # "+ Additional Staff" button
    if st.button("\u2795 Additional Staff", key="_cv_add_extra_staff"):
        st.session_state[_staff_key] = (
            st.session_state.get(_staff_key, 0) + 1
        )
        st.rerun()


def render_case_view():
    """Render the full case view (case selected)."""
    case_mgr = get_case_manager()
    case_id = st.session_state.current_case_id
    prep_id = st.session_state.get("current_prep_id")
    model_provider = get_model_provider()

    # Resolve prep metadata
    current_prep_meta = (
        case_mgr.get_preparation(case_id, prep_id) if prep_id else None
    )
    current_prep_type = current_prep_meta["type"] if current_prep_meta else "trial"
    current_prep_name = current_prep_meta["name"] if current_prep_meta else "No Preparation"

    case_type = case_mgr.get_case_type(case_id)
    client_name = case_mgr.get_client_name(case_id)

    # Sync to agent_results
    if st.session_state.get("agent_results"):
        st.session_state.agent_results["case_type"] = case_type
        st.session_state.agent_results["client_name"] = client_name

    # ===== WAR ROOM HEADER =====
    _ct_labels_display = {
        "criminal": "Criminal Defense",
        "criminal-juvenile": "Criminal \u2014 Juvenile",
        "civil-plaintiff": "Civil \u2014 Plaintiff",
        "civil-defendant": "Civil \u2014 Defendant",
        "civil-juvenile": "Civil \u2014 Juvenile",
    }
    _ct_icons = {
        "criminal": "\U0001f512",
        "criminal-juvenile": "\U0001f512",
        "civil-plaintiff": "\u2696\ufe0f",
        "civil-defendant": "\U0001f6e1\ufe0f",
        "civil-juvenile": "\u2696\ufe0f",
    }
    ct_display = _ct_labels_display.get(case_type, "Legal")
    ct_icon = _ct_icons.get(case_type, "\u2696\ufe0f")

    st.markdown(
        f'<h1 class="hero-title">{case_mgr.get_case_name(case_id)}</h1>',
        unsafe_allow_html=True,
    )

    # Client badge + type badge
    try:
        from core.crm import get_clients_for_case

        _linked_clients = get_clients_for_case(case_id)
        if _linked_clients:
            _client_names = " \u00b7 ".join(
                cl.get("name", "?") for cl in _linked_clients
            )
            st.markdown(
                f'<span class="pill-badge pill-badge-neutral" style="font-size:0.95rem;">\U0001f464 {_client_names}</span> '
                f'<span class="pill-badge pill-badge-accent">{ct_icon} {ct_display}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="pill-badge pill-badge-accent">{ct_icon} {ct_display}</span>',
                unsafe_allow_html=True,
            )
    except Exception:
        st.markdown(
            f'<span class="pill-badge pill-badge-accent">{ct_icon} {ct_display}</span>',
            unsafe_allow_html=True,
        )

    # Phase / Sub-Phase selectors
    _cur_phase, _cur_sub = case_mgr.get_phase(case_id)
    _phase_col, _subphase_col = st.columns([1, 2])
    with _phase_col:
        _phase_opts = ["active", "closed", "archived"]
        _phase_labels = {"active": "🟢 Active", "closed": "🟡 Closed", "archived": "📦 Archived"}
        _phase_idx = _phase_opts.index(_cur_phase) if _cur_phase in _phase_opts else 0
        _new_phase = st.selectbox(
            "Phase",
            options=_phase_opts,
            index=_phase_idx,
            format_func=lambda x: _phase_labels.get(x, x.capitalize()),
            key="_cv_phase_select",
        )
        if _new_phase != _cur_phase:
            try:
                case_mgr.set_phase(case_id, _new_phase)
                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                st.rerun()
            except Exception as _phase_err:
                st.error(f"Failed to change phase: {_phase_err}")
    with _subphase_col:
        if _cur_phase == "active":
            _sub_phases = case_mgr.get_sub_phases_for_case(case_id)
            _sub_opts = ["(none)"] + _sub_phases
            _sub_idx = _sub_opts.index(_cur_sub) if _cur_sub in _sub_opts else 0
            _new_sub = st.selectbox("Sub-Phase", _sub_opts, index=_sub_idx,
                                    key="_cv_subphase_select")
            _actual_sub = _new_sub if _new_sub != "(none)" else ""
            if _actual_sub != _cur_sub:
                case_mgr.set_sub_phase(case_id, _actual_sub)
                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                st.rerun()
        elif _cur_phase == "closed":
            _meta_tmp = case_mgr.storage.get_case_metadata(case_id)
            _closed_at = _meta_tmp.get("closed_at", "")
            if _closed_at:
                try:
                    _days_closed = (datetime.now() - datetime.fromisoformat(_closed_at)).days
                    _days_left = max(0, 21 - _days_closed)
                    st.info(f"Auto-archives in {_days_left} day{'s' if _days_left != 1 else ''}")
                except (ValueError, TypeError):
                    st.info("Case closed — auto-archives after 21 days")
            else:
                st.info("Case closed — auto-archives after 21 days")
        elif _cur_phase == "archived":
            _purged_flag = case_mgr.storage.get_case_metadata(case_id).get("purged", False)
            if _purged_flag:
                st.warning("📦 Files purged")
            else:
                st.info("Archived — files available for purge")

    # Editable case type & client name
    _ct_col1, _ct_col2 = st.columns([3, 1])
    with _ct_col2:
        _ct_options = [
            "criminal", "criminal-juvenile", "civil-plaintiff",
            "civil-defendant", "civil-juvenile",
        ]
        _ct_labels = {
            "criminal": "\U0001f512 Criminal Defense",
            "criminal-juvenile": "\U0001f512 Criminal - Juvenile",
            "civil-plaintiff": "\u2696\ufe0f Civil - Plaintiff",
            "civil-defendant": "\U0001f6e1\ufe0f Civil - Defendant",
            "civil-juvenile": "\u2696\ufe0f Civil - Juvenile",
        }
        _ct_current_idx = (
            _ct_options.index(case_type) if case_type in _ct_options else 0
        )
        _ct_new = st.selectbox(
            "Case Type",
            options=_ct_options,
            index=_ct_current_idx,
            format_func=lambda x: _ct_labels.get(x, x),
            key="_edit_case_type",
        )
        if _ct_new != case_type:
            case_mgr.update_case_type(case_id, _ct_new)
            if st.session_state.agent_results:
                st.session_state.agent_results["case_type"] = _ct_new
            st.rerun()
    with _ct_col1:
        # --- CRM-Linked Client Selector (multi-client) ---
        from core.crm import (
            load_clients, add_client, link_client_to_case,
            unlink_client_from_case, get_clients_for_case, get_client,
            CLIENT_TYPES,
        )

        _all_crm = sorted(load_clients(), key=lambda x: x.get("name", "").lower())
        _linked = get_clients_for_case(case_id)
        _linked_ids = [cl.get("id", "") for cl in _linked]

        # Build option list: name only, plus sentinel entries
        _name_to_id = {}
        _client_names_list = []
        for _cl in _all_crm:
            _cname = _cl.get("name", "?")
            # Handle duplicate names by appending ID hint
            if _cname in _name_to_id:
                _cname = f"{_cname} (#{_cl.get('id', '')[:4]})"
            _name_to_id[_cname] = _cl.get("id", "")
            _client_names_list.append(_cname)

        _NONE_OPT = "\u2014 Select Client \u2014"
        _ADD_OPT = "\u2795 Add New Client"

        def _sync_client_name():
            """Sync case metadata client_name from all currently linked CRM clients."""
            _cur_linked = get_clients_for_case(case_id)
            _joined = " & ".join(cl.get("name", "?") for cl in _cur_linked) if _cur_linked else ""
            case_mgr.update_client_name(case_id, _joined)
            if st.session_state.get("agent_results"):
                st.session_state.agent_results["client_name"] = _joined

        def _render_client_slot(slot_idx, current_id, label):
            """Render a single client dropdown slot. Returns selected client id or None."""
            _opts = [_NONE_OPT] + _client_names_list + [_ADD_OPT]
            # Find current selection index
            _cur_idx = 0
            if current_id:
                for _i, _opt in enumerate(_opts):
                    if _name_to_id.get(_opt) == current_id:
                        _cur_idx = _i
                        break

            _sel = st.selectbox(
                label,
                options=_opts,
                index=_cur_idx,
                key=f"_cv_client_slot_{slot_idx}",
                help="Select a CRM client to link to this case.",
            )

            if _sel == _ADD_OPT:
                st.session_state[f"_cv_adding_client_{slot_idx}"] = True
                return current_id  # keep old link until form submitted

            _sel_id = _name_to_id.get(_sel, "")

            # Detect change
            if _sel_id != (current_id or ""):
                # Unlink old
                if current_id:
                    unlink_client_from_case(current_id, case_id)
                # Link new
                if _sel_id:
                    link_client_to_case(_sel_id, case_id)
                _sync_client_name()
                st.rerun()

            return _sel_id

        # --- Determine how many slots to show ---
        # Primary slot always shown; extra slots for 2nd+ linked clients
        _primary_id = _linked_ids[0] if _linked_ids else ""
        _extra_ids = _linked_ids[1:] if len(_linked_ids) > 1 else []

        # Session state tracks how many extra slots are visible (keyed by case)
        _client_key = f"_cv_extra_client_count_{case_id}"
        if _client_key not in st.session_state:
            st.session_state[_client_key] = max(len(_extra_ids), 0)
        # Ensure at least enough slots for existing links
        if st.session_state[_client_key] < len(_extra_ids):
            st.session_state[_client_key] = len(_extra_ids)

        # Render primary slot
        _render_client_slot(0, _primary_id, "\U0001f464 Client / Party Represented")

        # Render inline add form for primary slot
        if st.session_state.get("_cv_adding_client_0"):
            _render_add_client_form(0, case_id, case_mgr, _sync_client_name)

        # Render extra slots
        _extra_count = st.session_state.get(_client_key, 0)
        for _si in range(_extra_count):
            _ex_id = _extra_ids[_si] if _si < len(_extra_ids) else ""
            _ex_col, _rm_col = st.columns([5, 1])
            with _ex_col:
                _render_client_slot(_si + 1, _ex_id, f"\U0001f464 Additional Client #{_si + 1}")
            with _rm_col:
                st.markdown("<br>", unsafe_allow_html=True)  # vertical align
                if st.button("\u2715", key=f"_cv_rm_client_{_si + 1}", help="Remove this client slot"):
                    # Unlink this client if one is selected
                    if _ex_id:
                        unlink_client_from_case(_ex_id, case_id)
                        _sync_client_name()
                    st.session_state[_client_key] = max(
                        st.session_state.get(_client_key, 1) - 1, 0
                    )
                    st.rerun()
            # Inline add form for this extra slot
            if st.session_state.get(f"_cv_adding_client_{_si + 1}"):
                _render_add_client_form(_si + 1, case_id, case_mgr, _sync_client_name)

        # "+ Additional Client" button
        if st.button("\u2795 Additional Client", key="_cv_add_extra_client"):
            st.session_state[_client_key] = (
                st.session_state.get(_client_key, 0) + 1
            )
            st.rerun()

    # ===== ASSIGNED STAFF =====
    _render_assigned_staff(case_id, case_mgr)

    # ===== ATTORNEY DIRECTIVES =====
    _render_attorney_directives(case_id, case_mgr)

    # ===== CONTACT LOG =====
    _render_contact_log(case_id, case_mgr)

    # ===== PREPARATION SELECTOR BAR =====
    _render_prep_selector(case_id, prep_id, current_prep_name, case_mgr)

    # Show prep type badge
    if current_prep_meta:
        prep_badge_color = {
            "trial": "\U0001f7e2",
            "prelim_hearing": "\U0001f535",
            "motion_hearing": "\U0001f7e1",
        }
        st.caption(
            f"{prep_badge_color.get(current_prep_type, '\u26aa')} "
            f"**{current_prep_name}** \u2014 "
            f"{CaseManager.PREP_TYPE_LABELS.get(current_prep_type, current_prep_type)}"
        )

    # ===== WAR ROOM METRICS =====
    if st.session_state.agent_results:
        results = st.session_state.agent_results
        _render_war_room_metrics(results)
        # Charges/claims prompt when analysis exists but no charges defined
        _charges = results.get("charges", [])
        if results.get("case_summary") and not _charges:
            st.warning(
                "**No charges/claims defined.** Adding charges improves Legal Elements "
                "mapping, Jury Instructions, and overall readiness score. "
                "Go to **Evidence & Facts \u2192 Charges** to add them."
            )
        # Performance profile from last analysis run
        _lpt = results.get("_last_per_node_times", {})
        if _lpt:
            with st.expander("Last Analysis Performance"):
                import pandas as pd
                _perf_data = sorted(_lpt.items(), key=lambda x: x[1], reverse=True)
                _df = pd.DataFrame(_perf_data, columns=["Module", "Time (s)"])
                st.bar_chart(_df.set_index("Module"), horizontal=True)
                _total = sum(v for v in _lpt.values())
                st.caption(f"Total node time: {int(_total // 60)}m {int(_total % 60)}s")
        st.markdown('<div class="hero-divider"></div>', unsafe_allow_html=True)

    # ===== AUTO-START PASSIVE OCR =====
    try:
        from core.ocr_worker import start_ocr_worker, get_ocr_status
        _ocr_stat = get_ocr_status(case_id)
        if _ocr_stat.get("status") != "running" and case_mgr.get_case_files(case_id):
            start_ocr_worker(case_id, case_mgr, model_provider)
    except Exception:
        pass

    # ===== FILE MANAGEMENT =====
    _render_file_management(case_id, case_mgr, model_provider)

    # ===== ANALYSIS ENGINE =====
    _render_analysis_engine(
        case_id, prep_id, case_mgr, model_provider, current_prep_type, current_prep_name
    )

    st.divider()

    # ---- Major Document Drafter Mode ----
    if st.session_state.get("_md_active", False):
        from ui.pages import major_docs_ui
        major_docs_ui.render_workspace(
            case_id, case_mgr,
            st.session_state.get("agent_results") or {},
            model_provider, prep_id,
        )
        return

    # ===== PREP-TYPE-AWARE NAVIGATION =====
    nav_groups = get_nav_groups(current_prep_type, is_admin())

    default_group = st.session_state.get("_nav_group", list(nav_groups.keys())[0])
    group_keys = list(nav_groups.keys())
    default_idx = group_keys.index(default_group) if default_group in group_keys else 0

    selected_group = st.selectbox(
        "Navigate to",
        options=group_keys,
        index=default_idx,
        key="_nav_group_select",
        label_visibility="collapsed",
    )
    st.session_state["_nav_group"] = selected_group

    # ===== QUICK TASK ====
    with st.popover("➕ Quick Task"):
        st.markdown("#### New Task")
        _qt_title = st.text_input("Title", key="_qt_title", placeholder="Enter task title...")
        _qt_col1, _qt_col2 = st.columns(2)
        with _qt_col1:
            _qt_priority = st.selectbox("Priority", ["high", "medium", "low"], index=1, key="_qt_priority")
        with _qt_col2:
            _qt_due = st.date_input("Due Date", value=None, key="_qt_due")
        _qt_assignee = st.text_input("Assignee", key="_qt_assignee", placeholder="Optional...")
        if st.button("Create Task", key="_qt_create", type="primary", disabled=not _qt_title):
            if _qt_title.strip():
                try:
                    from core.tasks import add_task
                    from ui.shared import PROJECT_ROOT
                    _qt_data_dir = str(PROJECT_ROOT / "data")
                    _qt_user = st.session_state.get("current_user", {})
                    add_task(
                        data_dir=_qt_data_dir,
                        case_id=case_id,
                        title=_qt_title.strip(),
                        priority=_qt_priority,
                        due_date=str(_qt_due) if _qt_due else "",
                        assigned_to=_qt_assignee.strip() if _qt_assignee else "",
                        assigned_by=_qt_user.get("name", "") if _qt_user else "",
                    )
                    st.toast(f"✅ Task created: {_qt_title.strip()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create task: {e}")

    # ===== GLOBAL SEARCH =====
    _render_global_search(st.session_state.get("agent_results") or {}, nav_groups, case_mgr)

    # ===== COURTROOM MODE + TAB DISPATCH =====
    _cm_col1, _cm_col2 = st.columns([4, 1])
    with _cm_col2:
        _courtroom_mode = st.toggle(
            "\u26a1 Courtroom",
            key="_courtroom_mode",
            help="Dense single-screen view for counsel table",
        )

    if _courtroom_mode:
        _render_courtroom_mode(st.session_state.get("agent_results") or {})
    else:
        # Normal tab mode — dispatch to page modules
        tab_labels = nav_groups.get(selected_group, [])
        if tab_labels:
            tabs = st.tabs(tab_labels)
            _dispatch_to_page(
                selected_group, case_id, prep_id, case_mgr, model_provider, tabs, nav_groups
            )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _render_attorney_directives(case_id: str, case_mgr):
    """Render the attorney directives expander."""
    _directives = case_mgr.load_directives(case_id)
    _dir_count = len(_directives)
    label = (
        f"\U0001f4cc **Attorney Directives** ({_dir_count})"
        if _dir_count
        else "\U0001f4cc **Attorney Directives** \u2014 _override AI assumptions_"
    )
    with st.expander(label, expanded=False):
        st.caption(
            "Directives are binding instructions for the AI. "
            "Stated facts are treated as TRUE. Strategic directions are followed exactly."
        )

        with st.form("_add_directive", clear_on_submit=True):
            _dir_cols = st.columns([3, 1])
            with _dir_cols[0]:
                _dir_text = st.text_area(
                    "New directive",
                    height=68,
                    placeholder="e.g. 'The defendant was at the grocery store from 2:45-3:30pm \u2014 this is confirmed.'",
                )
            with _dir_cols[1]:
                _dir_cat = st.selectbox(
                    "Type",
                    ["fact", "strategy", "instruction"],
                    format_func=lambda x: {
                        "fact": "\U0001f4cc Fact",
                        "strategy": "\u265f\ufe0f Strategy",
                        "instruction": "\U0001f4cb Instruction",
                    }.get(x, x),
                )
            _dir_submit = st.form_submit_button(
                "\u2795 Add Directive", use_container_width=True
            )
            if _dir_submit and _dir_text.strip():
                case_mgr.save_directive(case_id, _dir_text, _dir_cat)
                st.rerun()

        if _directives:
            _cat_icons = {
                "fact": "\U0001f4cc",
                "strategy": "\u265f\ufe0f",
                "instruction": "\U0001f4cb",
            }
            for _d in _directives:
                _d_icon = _cat_icons.get(_d.get("category", "instruction"), "\U0001f4cb")
                _d_id = _d.get("id", "")
                _editing_dir = st.session_state.get("_editing_dir_id") == _d_id
                _d_cols = st.columns([0.3, 4, 0.3, 0.3])
                with _d_cols[0]:
                    st.markdown(f"### {_d_icon}")
                with _d_cols[1]:
                    if _editing_dir:
                        _edit_text = st.text_area(
                            "Edit directive",
                            value=_d.get("text", ""),
                            key=f"_edit_dir_text_{_d_id}",
                            height=68,
                            label_visibility="collapsed",
                        )
                        _save_c, _cancel_c = st.columns(2)
                        with _save_c:
                            if st.button("Save", key=f"_save_dir_{_d_id}", type="primary"):
                                case_mgr.update_directive(case_id, _d_id, _edit_text)
                                st.session_state.pop("_editing_dir_id", None)
                                st.rerun()
                        with _cancel_c:
                            if st.button("Cancel", key=f"_cancel_dir_{_d_id}"):
                                st.session_state.pop("_editing_dir_id", None)
                                st.rerun()
                    else:
                        st.markdown(
                            f"**{_d.get('category', 'instruction').upper()}**: {_d.get('text', '')}"
                        )
                        st.caption(_d.get("created_at", "")[:16].replace("T", " "))
                with _d_cols[2]:
                    if not _editing_dir:
                        if st.button(
                            "\u270f\ufe0f",
                            key=f"_edit_dir_{_d_id}",
                            help="Edit this directive",
                        ):
                            st.session_state["_editing_dir_id"] = _d_id
                            st.rerun()
                with _d_cols[3]:
                    if st.button(
                        "\U0001f5d1\ufe0f",
                        key=f"_del_dir_{_d_id}",
                        help="Delete this directive",
                    ):
                        case_mgr.delete_directive(case_id, _d_id)
                        st.rerun()
        else:
            st.info("No directives set. Add one above to override AI assumptions.")


def _render_contact_log(case_id: str, case_mgr):
    """Render the contact log expander."""
    _cl_entries = case_mgr.load_contact_log(case_id)
    _cl_count = len(_cl_entries)
    label = (
        f"\U0001f4de **Contact Log** ({_cl_count})"
        if _cl_count
        else "\U0001f4de **Contact Log** \u2014 _document client communications_"
    )
    _cl_type_icons = {
        "Phone Call": "\U0001f4f1",
        "In-Person": "\U0001f91d",
        "Zoom/Video": "\U0001f4bb",
        "Email": "\U0001f4e7",
        "Text/Message": "\U0001f4ac",
        "Court Appearance": "\U0001f3db\ufe0f",
        "Other": "\U0001f4cb",
    }

    with st.expander(label, expanded=False):
        st.caption("Log all contacts with clients, witnesses, opposing counsel, and other parties.")

        with st.form("_add_contact_log", clear_on_submit=True):
            st.markdown("**\u2795 Log New Contact**")
            _cl_form_c1, _cl_form_c2 = st.columns(2)
            with _cl_form_c1:
                _cl_type = st.selectbox(
                    "Contact Type",
                    options=CaseManager.CONTACT_TYPES,
                    format_func=lambda x: f"{_cl_type_icons.get(x, '\U0001f4cb')} {x}",
                    key="_cl_type",
                )
                _cl_person = st.text_input(
                    "Person Contacted",
                    placeholder="e.g. John Smith (Client)",
                    key="_cl_person",
                )
                _cl_subject = st.text_input(
                    "Subject",
                    placeholder="e.g. Discussed alibi timeline",
                    key="_cl_subject",
                )
            with _cl_form_c2:
                _cl_date = st.date_input("Date", value=date.today(), key="_cl_date")
                _cl_time = st.time_input("Time", key="_cl_time")
                _cl_duration = st.number_input(
                    "Duration (minutes)",
                    min_value=0,
                    max_value=600,
                    value=0,
                    step=5,
                    key="_cl_duration",
                    help="Optional \u2014 enter 0 to skip",
                )
            _cl_notes = st.text_area(
                "Notes",
                height=80,
                placeholder="Details of the conversation, agreements made, action items...",
                key="_cl_notes",
            )
            _cl_submit = st.form_submit_button(
                "\U0001f4de Log Contact", use_container_width=True
            )
            if _cl_submit and _cl_person.strip():
                case_mgr.add_contact_log_entry(
                    case_id,
                    contact_type=_cl_type,
                    person=_cl_person,
                    subject=_cl_subject,
                    notes=_cl_notes,
                    contact_date=str(_cl_date),
                    contact_time=_cl_time.strftime("%H:%M") if _cl_time else "",
                    duration_mins=_cl_duration,
                )
                st.toast("\U0001f4de Contact logged!", icon="\u2705")
                st.rerun()
            elif _cl_submit:
                st.warning("Please enter the person contacted.")

        # Filter + show existing
        if _cl_entries:
            _cl_filter_c1, _cl_filter_c2 = st.columns([1, 3])
            with _cl_filter_c1:
                _cl_filter_type = st.selectbox(
                    "Filter by type",
                    options=["All"] + CaseManager.CONTACT_TYPES,
                    key="_cl_filter_type",
                    label_visibility="collapsed",
                )
            with _cl_filter_c2:
                st.caption(
                    f"Showing {'all' if _cl_filter_type == 'All' else _cl_filter_type} "
                    f"contacts \u00b7 {_cl_count} total"
                )
            _cl_filtered = (
                _cl_entries
                if _cl_filter_type == "All"
                else [e for e in _cl_entries if e.get("contact_type") == _cl_filter_type]
            )
            if not _cl_filtered:
                st.info(f"No {_cl_filter_type} contacts found.")

            for _cl_idx, _cl_e in enumerate(_cl_filtered):
                _cl_eid = _cl_e.get("id", "")
                _cl_etype = _cl_e.get("contact_type", "Other")
                _cl_eicon = _cl_type_icons.get(_cl_etype, "\U0001f4cb")
                _cl_eperson = _cl_e.get("person", "Unknown")
                _cl_esubject = _cl_e.get("subject", "")
                _cl_edate = _cl_e.get("contact_date", "")
                _cl_etime = _cl_e.get("contact_time", "")
                _cl_eduration = _cl_e.get("duration_mins", 0)
                _cl_enotes = _cl_e.get("notes", "")
                _cl_editing = st.session_state.get("_editing_cl_id") == _cl_eid

                _cl_dur_str = ""
                if _cl_eduration and _cl_eduration > 0:
                    if _cl_eduration >= 60:
                        _cl_dur_str = f" \u00b7 {_cl_eduration // 60}h {_cl_eduration % 60}m"
                    else:
                        _cl_dur_str = f" \u00b7 {_cl_eduration}min"

                with st.container(border=True):
                    if _cl_editing:
                        st.markdown(f"**\u270f\ufe0f Editing contact with {_cl_eperson}**")
                        _ec1, _ec2 = st.columns(2)
                        with _ec1:
                            _e_person = st.text_input("Person", value=_cl_eperson, key=f"_cle_person_{_cl_eid}")
                            _e_subject = st.text_input("Subject", value=_cl_esubject, key=f"_cle_subj_{_cl_eid}")
                        with _ec2:
                            _e_type = st.selectbox(
                                "Type", options=CaseManager.CONTACT_TYPES,
                                index=CaseManager.CONTACT_TYPES.index(_cl_etype) if _cl_etype in CaseManager.CONTACT_TYPES else 0,
                                key=f"_cle_type_{_cl_eid}",
                            )
                            _e_duration = st.number_input(
                                "Duration (min)", min_value=0, max_value=600,
                                value=_cl_eduration or 0, step=5, key=f"_cle_dur_{_cl_eid}",
                            )
                        _e_notes = st.text_area("Notes", value=_cl_enotes, height=68, key=f"_cle_notes_{_cl_eid}")
                        _es_c, _ec_c = st.columns(2)
                        with _es_c:
                            if st.button("Save Changes", key=f"_cle_save_{_cl_eid}", type="primary", use_container_width=True):
                                case_mgr.update_contact_log_entry(case_id, _cl_eid, {
                                    "person": _e_person, "subject": _e_subject,
                                    "contact_type": _e_type, "duration_mins": _e_duration,
                                    "notes": _e_notes,
                                })
                                st.session_state.pop("_editing_cl_id", None)
                                st.toast("\u2705 Contact updated")
                                st.rerun()
                        with _ec_c:
                            if st.button("Cancel", key=f"_cle_cancel_{_cl_eid}", use_container_width=True):
                                st.session_state.pop("_editing_cl_id", None)
                                st.rerun()
                    else:
                        _cl_card_c1, _cl_card_c2, _cl_card_c3, _cl_card_c4 = st.columns([0.5, 4, 0.3, 0.3])
                        with _cl_card_c1:
                            st.markdown(f"### {_cl_eicon}")
                        with _cl_card_c2:
                            _cl_header = f"**{_cl_etype}** with **{_cl_eperson}**"
                            if _cl_esubject:
                                _cl_header += f" \u2014 {_cl_esubject}"
                            st.markdown(_cl_header)
                            _cl_meta = f"\U0001f4c5 {_cl_edate}"
                            if _cl_etime:
                                _cl_meta += f" at {_cl_etime}"
                            _cl_meta += _cl_dur_str
                            st.caption(_cl_meta)
                            if _cl_enotes:
                                st.markdown(f"_{_cl_enotes}_")
                        with _cl_card_c3:
                            if st.button(
                                "\u270f\ufe0f",
                                key=f"_cl_edit_{_cl_eid}",
                                help="Edit this contact",
                            ):
                                st.session_state["_editing_cl_id"] = _cl_eid
                                st.rerun()
                        with _cl_card_c4:
                            if st.button(
                                "\U0001f5d1\ufe0f",
                                key=f"_cl_del_{_cl_eid}",
                                help="Delete this contact",
                            ):
                                case_mgr.delete_contact_log_entry(case_id, _cl_eid)
                                st.toast("\U0001f5d1\ufe0f Contact deleted")
                                st.rerun()
        else:
            st.info(
                "No contacts logged yet. Use the form above to log your first contact."
            )


def _render_prep_selector(case_id, prep_id, current_prep_name, case_mgr):
    """Render the preparation selector bar with New/Clone/Import."""
    preps = case_mgr.list_preparations(case_id)
    preps.sort(key=lambda p: p.get("created_at", ""), reverse=True)  # Newest first

    prep_bar_cols = st.columns([3, 1])
    with prep_bar_cols[0]:
        if preps:
            prep_type_icons = {
                "trial": "\u2694\ufe0f",
                "prelim_hearing": "\U0001f4cb",
                "motion_hearing": "\U0001f4dd",
            }
            prep_options = {
                p["id"]: f"{prep_type_icons.get(p['type'], '\U0001f4c4')} {p['name']}"
                for p in preps
            }
            selected_prep = st.selectbox(
                "Active Preparation",
                options=list(prep_options.keys()),
                format_func=lambda x: prep_options[x],
                index=(
                    list(prep_options.keys()).index(prep_id)
                    if prep_id and prep_id in prep_options
                    else 0
                ),
                key="_prep_selector",
            )
            if selected_prep != prep_id:
                load_preparation(case_id, selected_prep)
        else:
            st.info("No preparations yet. Create one to begin analysis.")

    with prep_bar_cols[1]:
        prep_action_c1, prep_action_c2, prep_action_c3 = st.columns(3)
        with prep_action_c1:
            with st.popover("\u2795 New", use_container_width=True):
                new_prep_type = st.selectbox(
                    "Preparation Type",
                    options=["trial", "prelim_hearing", "motion_hearing"],
                    format_func=lambda x: CaseManager.PREP_TYPE_LABELS.get(x, x),
                    key="_new_prep_type",
                )
                default_names = {
                    "trial": "Trial Preparation",
                    "prelim_hearing": "Preliminary Hearing",
                    "motion_hearing": "",
                }
                new_prep_name = st.text_input(
                    "Preparation Name",
                    value=default_names.get(new_prep_type, ""),
                    placeholder="e.g., Motion to Suppress - Warrantless Search",
                    key="_new_prep_name",
                )
                if st.button(
                    "Create Preparation",
                    key="_create_prep",
                    type="primary",
                    use_container_width=True,
                ):
                    if new_prep_name:
                        new_id = case_mgr.create_preparation(
                            case_id, new_prep_type, new_prep_name
                        )
                        load_preparation(case_id, new_id)
                    else:
                        st.error("Please enter a name for the preparation.")
        with prep_action_c2:
            if prep_id:
                with st.popover("\U0001f4cb Clone", use_container_width=True):
                    _clone_prep_name = st.text_input(
                        "Clone name",
                        value=f"{current_prep_name} (Copy)",
                        key="_clone_prep_name",
                    )
                    if st.button(
                        "Clone Prep",
                        key="_clone_prep_btn",
                        type="primary",
                        use_container_width=True,
                    ):
                        new_pid = case_mgr.clone_preparation(
                            case_id, prep_id, _clone_prep_name
                        )
                        st.success("Cloned!")
                        load_preparation(case_id, new_pid)
        with prep_action_c3:
            if prep_id and len(preps) >= 2:
                with st.popover("\U0001f4e5 Import", use_container_width=True):
                    st.caption("Import data from another preparation")
                    other_preps = [p for p in preps if p["id"] != prep_id]
                    source_options = {p["id"]: p["name"] for p in other_preps}
                    import_source = st.selectbox(
                        "Source prep",
                        options=list(source_options.keys()),
                        format_func=lambda x: source_options[x],
                        key="_import_src",
                    )
                    importable_keys = [
                        ("witnesses", "\U0001f465 Witnesses"),
                        ("strategy_notes", "\U0001f3af Strategy Notes"),
                        ("legal_elements", "\U0001f9e9 Legal Elements"),
                        ("cross_examination_plan", "\u2694\ufe0f Cross-Exam Plan"),
                        ("direct_examination_plan", "\U0001f6e1\ufe0f Direct-Exam Plan"),
                        ("investigation_plan", "\U0001f575\ufe0f Investigation Plan"),
                        ("timeline", "\U0001f4c5 Timeline"),
                        ("entities", "\U0001f3f7\ufe0f Entities"),
                    ]
                    selected_keys = []
                    for key, label in importable_keys:
                        if st.checkbox(label, key=f"_imp_{key}"):
                            selected_keys.append(key)

                    if st.button(
                        "Import Selected",
                        key="_import_btn",
                        type="primary",
                        use_container_width=True,
                        disabled=not selected_keys,
                    ):
                        result = case_mgr.import_from_prep(
                            case_id, import_source, prep_id, selected_keys
                        )
                        st.session_state.agent_results = case_mgr.load_prep_state(
                            case_id, prep_id
                        )
                        summary = ", ".join(
                            f"{k}: +{v}" for k, v in result.items() if v > 0
                        )
                        st.success(
                            f"Imported: {summary}" if summary else "No new data to import."
                        )
                        st.rerun()


def _render_war_room_metrics(results):
    """Render the 5 war room metric cards."""
    elements = results.get("legal_elements", [])
    conflicts = results.get("consistency_check", [])

    strength = 50
    high_count = 0
    if isinstance(elements, list):
        for e in elements:
            if isinstance(e, dict):
                s = e.get("strength", "").lower()
                if "low" in s:
                    strength += 5
                elif "high" in s:
                    strength -= 5
                    high_count += 1
    strength = max(0, min(100, strength))

    if strength >= 65:
        strength_delta = "Strong"
    elif strength >= 40:
        strength_delta = "Moderate"
    else:
        strength_delta = "Weak"

    _gauge_color = (
        "#22c55e" if strength >= 65 else "#eab308" if strength >= 40 else "#ef4444"
    )
    _gauge_pct = strength / 100
    _gauge_dash = _gauge_pct * 201.06
    _gauge_remain = 201.06 - _gauge_dash

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        _badge_class = (
            "success" if strength >= 65 else "warning" if strength >= 40 else "danger"
        )
        st.markdown(
            f"""
            <div class="glass-stat-card" style="text-align:center; padding:14px 12px;">
                <div class="stat-label">Position Score</div>
                <div class="gauge-ring" style="margin:8px auto;">
                    <svg width="72" height="72" viewBox="0 0 72 72">
                        <circle cx="36" cy="36" r="32" fill="none" stroke="rgba(128,128,128,0.15)" stroke-width="5"/>
                        <circle cx="36" cy="36" r="32" fill="none" stroke="{_gauge_color}" stroke-width="5"
                            stroke-dasharray="{_gauge_dash} {_gauge_remain}" stroke-linecap="round"
                            style="filter: drop-shadow(0 0 4px {_gauge_color}40);"/>
                    </svg>
                    <div class="gauge-value" style="color:{_gauge_color};">{strength}</div>
                </div>
                <div class="pill-badge pill-badge-{_badge_class}" style="margin-top:4px;">{strength_delta}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
    with m2:
        _risk_style = "color:#ef4444;" if high_count > 0 else ""
        st.markdown(
            f"""
            <div class="glass-stat-card">
                <div class="stat-icon">\U0001f534</div>
                <div class="stat-value" style="{_risk_style}">{high_count}</div>
                <div class="stat-label">High Risk</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
    conflict_count = len(conflicts) if isinstance(conflicts, list) else 0
    with m3:
        _conflict_style = "color:#eab308;" if conflict_count > 0 else ""
        st.markdown(
            f"""
            <div class="glass-stat-card">
                <div class="stat-icon">\u26a0\ufe0f</div>
                <div class="stat-value" style="{_conflict_style}">{conflict_count}</div>
                <div class="stat-label">Conflicts</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
    with m4:
        _witness_count = len(results.get("witnesses", []))
        st.markdown(
            f"""
            <div class="glass-stat-card">
                <div class="stat-icon">\U0001f465</div>
                <div class="stat-value">{_witness_count}</div>
                <div class="stat-label">Witnesses</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
    inv_plan = results.get("investigation_plan", [])
    open_tasks = 0
    if isinstance(inv_plan, list):
        open_tasks = len(
            [t for t in inv_plan if isinstance(t, dict) and t.get("status") != "completed"]
        )
    with m5:
        st.markdown(
            f"""
            <div class="glass-stat-card">
                <div class="stat-icon">\U0001f4cb</div>
                <div class="stat-value">{open_tasks}</div>
                <div class="stat-label">Open Tasks</div>
            </div>
        """,
            unsafe_allow_html=True,
        )


def _render_file_management(case_id, case_mgr, model_provider):
    """Render the file management expander."""
    # Guard: if files have been purged, show notice instead
    _fm_meta = case_mgr.storage.get_case_metadata(case_id)
    if _fm_meta.get("purged"):
        with st.expander("\U0001f4c2 Case Files & Ingestion", expanded=False):
            st.info(
                "📦 Source documents have been purged from this archived case. "
                "Analysis results are still available. "
                "Original files are in your Dropbox backup."
            )
            _purged_count = _fm_meta.get("purged_file_count", 0)
            _purged_at = _fm_meta.get("purged_at", "")
            if _purged_count or _purged_at:
                st.caption(f"Purged {_purged_count} file(s)"
                           + (f" on {_purged_at[:10]}" if _purged_at else ""))
        return
    with st.expander("\U0001f4c2 Case Files & Ingestion", expanded=False):
        # Force OCR toggle
        _force_ocr_col1, _force_ocr_col2 = st.columns([1, 3])
        with _force_ocr_col1:
            _force_ocr = st.toggle(
                "\U0001f50d Force OCR",
                value=st.session_state.get("_force_ocr_mode", False),
                key="_force_ocr_toggle",
            )
            st.session_state._force_ocr_mode = _force_ocr
        with _force_ocr_col2:
            if _force_ocr:
                st.caption(
                    "\u26a1 **ON** \u2014 Every PDF page will be read by AI vision."
                )
            else:
                st.caption("Auto-detect mode: AI will OCR pages only when text quality is poor.")
        st.divider()

        # Existing files (with caching and pagination)
        _file_cache_key = f"_cached_files_{case_id}"
        _file_cache_ver = f"_file_cache_ver_{case_id}"
        _current_ver = st.session_state.get("_uploader_key_counter", 0)
        if (
            _file_cache_key not in st.session_state
            or st.session_state.get(_file_cache_ver) != _current_ver
        ):
            st.session_state[_file_cache_key] = case_mgr.get_ordered_files(case_id)
            st.session_state[_file_cache_ver] = _current_ver
        current_files = st.session_state[_file_cache_key]

        if current_files:
            total_bytes = sum(
                os.path.getsize(f) for f in current_files if os.path.exists(f)
            )

            def fmt_size(b):
                if b < 1024:
                    return f"{b} B"
                elif b < 1024**2:
                    return f"{b / 1024:.1f} KB"
                else:
                    return f"{b / (1024**2):.1f} MB"

            st.markdown(
                f"**\U0001f4da Case Library ({len(current_files)} files, {fmt_size(total_bytes)})**"
            )

            # OCR worker status indicator
            try:
                from core.ocr_worker import get_ocr_status as _get_ocr_st
                _ocr_stat = _get_ocr_st(case_id)
                _ocr_ws = _ocr_stat.get("status")
                if _ocr_ws == "running":
                    _ocr_cf = _ocr_stat.get("current_file", "")
                    _ocr_fd = _ocr_stat.get("files_done", 0)
                    _ocr_ft = _ocr_stat.get("files_total", 0)
                    _ocr_cp = _ocr_stat.get("current_page", 0)
                    _ocr_tp = _ocr_stat.get("total_pages", 0)
                    _ocr_pag = f" (page {_ocr_cp}/{_ocr_tp})" if _ocr_tp > 0 else ""
                    st.caption(
                        f"\U0001f50d **Background OCR:** {_ocr_fd}/{_ocr_ft} files "
                        f"| Processing: {_ocr_cf}{_ocr_pag}"
                    )
                    try:
                        from streamlit_autorefresh import st_autorefresh
                        st_autorefresh(interval=5000, limit=None, key="_ocr_status_poll")
                    except ImportError:
                        pass
                elif _ocr_ws == "idle" and _ocr_stat.get("files_done", 0) > 0:
                    st.caption(
                        f"\u2705 **OCR complete:** {_ocr_stat.get('files_done', 0)} files indexed"
                    )
            except Exception:
                pass

            _all_file_tags = case_mgr.get_all_file_tags(case_id)
            _custom_tag_cats = case_mgr.get_custom_file_tag_categories(case_id)
            _tag_options = (
                case_mgr.FILE_TAG_CATEGORIES + _custom_tag_cats + ["\u2795 Add New..."]
            )
            # --- Sort dropdown + relevance scores ---
            _sort_col1, _sort_col2 = st.columns([3, 1])
            with _sort_col2:
                _sort_mode = st.selectbox(
                    "Sort by", ["Custom Order", "Name (A-Z)", "Size", "Relevance"],
                    index=0, key=f"_file_sort_{case_id}", label_visibility="collapsed",
                )
            with _sort_col1:
                if _sort_mode != "Custom Order":
                    st.caption(f"Sorted by: {_sort_mode}")

            # Load relevance scores (always, for badges)
            _relevance_scores = {}
            try:
                from core.relevance import load_relevance_scores as _load_rel
                _rel_data_dir = str(Path(__file__).resolve().parent.parent / "data")
                _current_prep = st.session_state.get("current_prep_id", "")
                if _current_prep:
                    _relevance_scores = _load_rel(_rel_data_dir, case_id, _current_prep)
            except Exception:
                pass

            # Apply sort
            if _sort_mode == "Name (A-Z)":
                current_files = sorted(current_files, key=lambda f: os.path.basename(f).lower())
            elif _sort_mode == "Size":
                current_files = sorted(
                    current_files,
                    key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0,
                    reverse=True,
                )
            elif _sort_mode == "Relevance" and _relevance_scores:
                current_files = sorted(
                    current_files,
                    key=lambda f: _relevance_scores.get(os.path.basename(f), {}).get("score", -1),
                    reverse=True,
                )

            # Basenames must be computed AFTER sorting
            _basenames_ordered = [os.path.basename(f) for f in current_files]

            # ---- Drag-and-Drop Reorder (Custom Order only) ----
            if _sort_mode == "Custom Order" and len(current_files) > 1:
                try:
                    from streamlit_sortables import sort_items as _sort_items
                    with st.expander("\u2195\ufe0f **Drag to Reorder Files**", expanded=False):
                        _reordered = _sort_items(_basenames_ordered, direction="vertical")
                        if _reordered != _basenames_ordered:
                            case_mgr.set_file_order(case_id, _reordered)
                            st.session_state.pop(_file_cache_key, None)
                            st.rerun()
                except ImportError:
                    pass  # Fall back to up/down arrows below

            # Pagination for large file lists
            _files_per_page = 20
            _total_file_pages = max(1, (len(current_files) + _files_per_page - 1) // _files_per_page)
            if _total_file_pages > 1:
                _fp_col1, _fp_col2 = st.columns([3, 1])
                with _fp_col2:
                    _file_page = st.number_input(
                        "File page", min_value=1, max_value=_total_file_pages,
                        value=1, key="_file_page", label_visibility="collapsed",
                    )
                with _fp_col1:
                    st.caption(f"Page {_file_page}/{_total_file_pages}")
            else:
                _file_page = 1
            _fp_start = (_file_page - 1) * _files_per_page
            _fp_end = min(_fp_start + _files_per_page, len(current_files))
            _page_files = list(enumerate(current_files))[_fp_start:_fp_end]

            # Load OCR cache for badge display
            try:
                from core.ingest import OCRCache as _OcrCache
                _ocr_cache = _OcrCache(os.path.join(
                    str(Path(__file__).resolve().parent.parent / "data" / "cases"), case_id
                ))
                _ocr_statuses = _ocr_cache.get_all_statuses()
            except Exception:
                _ocr_statuses = {}

            for idx, file_path in _page_files:
                fname = os.path.basename(file_path)
                fsize = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                _ftags = _all_file_tags.get(fname, [])

                # OCR status badge
                _fkey = f"{fname}:{fsize}"
                _ocr_entry = _ocr_statuses.get(_fkey, {})
                _ocr_st = _ocr_entry.get("status")
                _ocr_ext = os.path.splitext(fname)[1].lower()
                if _ocr_st == "done":
                    _ocr_badge = '<span style="background:#238636;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:6px;" title="OCR complete">OCR</span>'
                elif _ocr_st == "in_progress":
                    _pg_done = _ocr_entry.get("pages_done", 0)
                    _pg_total = _ocr_entry.get("total_pages", 0)
                    _ocr_badge = f'<span style="background:#1f6feb;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:6px;" title="OCR in progress">OCR {_pg_done}/{_pg_total}</span>'
                elif _ocr_st == "skipped":
                    _ocr_badge = '<span style="background:#484f58;color:#8b949e;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:6px;" title="Text-based file, no OCR needed">TXT</span>'
                elif _ocr_st == "error":
                    _ocr_badge = '<span style="background:#da3633;color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:6px;" title="OCR failed">ERR</span>'
                elif _ocr_ext in (".pdf", ".jpg", ".jpeg", ".png"):
                    _ocr_badge = '<span style="background:#6e7681;color:#c9d1d9;padding:1px 6px;border-radius:8px;font-size:11px;margin-left:6px;" title="Pending OCR">...</span>'
                else:
                    _ocr_badge = ""

                c1, c_preview, c2, c3, c4, c_ocr, c6 = st.columns(
                    [0.04, 0.04, 0.28, 0.28, 0.10, 0.06, 0.06]
                )
                with c1:
                    st.markdown("\U0001f4c4")
                with c_preview:
                    if st.button("\U0001f441", key=f"_preview_{idx}", help="Preview file"):
                        if st.session_state.get("_previewing_file") == file_path:
                            st.session_state.pop("_previewing_file", None)
                        else:
                            st.session_state["_previewing_file"] = file_path
                        st.rerun()
                with c2:
                    _tag_str = (
                        "  ".join(f"`{t}`" for t in _ftags) if _ftags else ""
                    )
                    # Relevance badge
                    _rel_entry = _relevance_scores.get(fname, {})
                    _rel_score = _rel_entry.get("score")
                    if _rel_score is not None:
                        _rel_cites = _rel_entry.get("citations", 0)
                        if _rel_score >= 70:
                            _rel_badge = f'<span style="background:#238636;color:#fff;padding:1px 5px;border-radius:8px;font-size:10px;margin-left:4px;" title="Relevance: {_rel_score}/100 ({_rel_cites} citations)">{_rel_score}</span>'
                        elif _rel_score >= 30:
                            _rel_badge = f'<span style="background:#9e6a03;color:#fff;padding:1px 5px;border-radius:8px;font-size:10px;margin-left:4px;" title="Relevance: {_rel_score}/100 ({_rel_cites} citations)">{_rel_score}</span>'
                        else:
                            _rel_badge = f'<span style="background:#484f58;color:#8b949e;padding:1px 5px;border-radius:8px;font-size:10px;margin-left:4px;" title="Relevance: {_rel_score}/100 ({_rel_cites} citations)">{_rel_score}</span>'
                    else:
                        _rel_badge = ""
                    _fname_html = f"{fname}  {_tag_str}{_ocr_badge}{_rel_badge}" if _tag_str else f"{fname}{_ocr_badge}{_rel_badge}"
                    st.markdown(_fname_html, unsafe_allow_html=True)
                with c3:
                    _new_tags = st.multiselect(
                        "Tags",
                        _tag_options,
                        default=_ftags,
                        key=f"_ftag_{idx}",
                        label_visibility="collapsed",
                    )
                    if "\u2795 Add New..." in _new_tags:
                        _new_tags.remove("\u2795 Add New...")
                        _custom_type = st.text_input(
                            "New type name",
                            placeholder="e.g. Body Cam Footage",
                            key=f"_ftag_custom_{idx}",
                            label_visibility="collapsed",
                        )
                        if _custom_type and _custom_type.strip():
                            if st.button("Add", key=f"_ftag_add_{idx}", type="primary"):
                                case_mgr.add_custom_file_tag_category(
                                    case_id, _custom_type.strip()
                                )
                                _new_tags.append(_custom_type.strip())
                                case_mgr.set_file_tags(case_id, fname, _new_tags)
                                st.rerun()
                    elif _new_tags != _ftags:
                        case_mgr.set_file_tags(case_id, fname, _new_tags)
                        st.rerun()
                with c4:
                    st.caption(fmt_size(fsize))
                with c_ocr:
                    if _ocr_ext in (".pdf", ".jpg", ".jpeg", ".png") and _ocr_st != "done":
                        if st.button("\U0001f50d", key=f"_ocr_{idx}", help="Prioritize OCR for this file"):
                            try:
                                from core.ocr_worker import prioritize_file, start_ocr_worker
                                prioritize_file(case_id, _fkey)
                                start_ocr_worker(case_id, case_mgr, model_provider)
                                st.toast(f"Prioritized OCR for {fname}")
                            except Exception as _oe:
                                st.toast(f"OCR error: {_oe}")
                            st.rerun()
                with c6:
                    if st.button("\u274c", key=f"del_file_{idx}", help="Delete file"):
                        if case_mgr.delete_file(case_id, fname):
                            st.session_state["_uploader_key_counter"] = (
                                st.session_state.get("_uploader_key_counter", 0) + 1
                            )
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                            st.toast(f"\U0001f5d1\ufe0f Deleted {fname}")
                            st.rerun()

                # Inline preview
                if st.session_state.get("_previewing_file") == file_path:
                    _ext = os.path.splitext(fname)[1].lower()
                    with st.container(border=True):
                        st.caption(f"Preview: {fname}")
                        if _ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                            st.image(file_path, use_container_width=True)
                        elif _ext in (".txt", ".md", ".csv", ".log", ".json"):
                            try:
                                with open(file_path, "r", encoding="utf-8", errors="replace") as _pf:
                                    _preview_text = _pf.read(10000)
                                st.code(_preview_text, language="text")
                                if len(_preview_text) >= 10000:
                                    st.caption("(Showing first 10,000 characters)")
                            except Exception as _pe:
                                st.warning(f"Could not read file: {_pe}")
                        elif _ext == ".pdf":
                            try:
                                import fitz as _fitz_preview
                                _pdf_doc = _fitz_preview.open(file_path)
                                _pdf_total = len(_pdf_doc)
                                _pk = f"_pdf_page_{idx}"
                                _pdf_pg = st.session_state.get(_pk, 0)
                                if _pdf_total > 1:
                                    _pp1, _pp2, _pp3 = st.columns([1, 3, 1])
                                    with _pp1:
                                        if st.button("\u25c0", key=f"_pprev_{idx}", disabled=_pdf_pg <= 0):
                                            st.session_state[_pk] = _pdf_pg - 1
                                            st.rerun()
                                    with _pp2:
                                        st.caption(f"Page {_pdf_pg + 1} / {_pdf_total}")
                                    with _pp3:
                                        if st.button("\u25b6", key=f"_pnext_{idx}", disabled=_pdf_pg >= _pdf_total - 1):
                                            st.session_state[_pk] = _pdf_pg + 1
                                            st.rerun()
                                _page = _pdf_doc[min(_pdf_pg, _pdf_total - 1)]
                                _pix = _page.get_pixmap(dpi=120)
                                st.image(_pix.tobytes("png"), use_container_width=True)
                                _pdf_doc.close()
                                # Full viewer link
                                if st.button("\U0001f50d Open Full Viewer", key=f"_fullview_{idx}"):
                                    st.session_state["_viewing_file"] = file_path
                                    st.session_state["_nav_group"] = "Tools"
                                    st.rerun()
                            except ImportError:
                                st.info("Install `pymupdf` for inline PDF preview: `pip install pymupdf`")
                            except Exception as _pe:
                                st.warning(f"PDF preview error: {_pe}")
                        else:
                            # Try to read as text for common document types
                            try:
                                with open(file_path, "r", encoding="utf-8", errors="replace") as _pf:
                                    _preview_text = _pf.read(5000)
                                if _preview_text.strip():
                                    st.code(_preview_text, language="text")
                                else:
                                    st.info(f"Binary file ({_ext}) — no text preview available.")
                            except Exception:
                                st.info(f"Binary file ({_ext}) — no text preview available.")

            st.divider()

        # ---- Supported file extensions (shared by uploader + folder import) ----
        _SUPPORTED_EXTS = {
            ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".mp3", ".wav", ".m4a",
            ".mp4", ".mpeg", ".mpga", ".webm", ".avi", ".mov", ".mkv",
            ".ogg", ".flac", ".aac", ".xlsx", ".xls", ".csv",
        }

        # ---- Shared post-upload pipeline ----
        def _post_upload_pipeline(saved_names: list) -> None:
            """Auto-classify, check media, start background workers."""
            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
            # Invalidate the file-list cache so new files appear in the UI
            st.session_state["_uploader_key_counter"] = (
                st.session_state.get("_uploader_key_counter", 0) + 1
            )
            # Also nuke the cached file list directly (belt-and-suspenders)
            st.session_state.pop(f"_cached_files_{case_id}", None)
            # Auto-classify
            try:
                from core.ingest import auto_classify_file as _auto_clf
                _auto_suggestions = {}
                for _fn in saved_names:
                    _suggested = _auto_clf(_fn)
                    if _suggested:
                        _auto_suggestions[_fn] = _suggested
                if _auto_suggestions:
                    st.session_state["_pending_auto_tags"] = _auto_suggestions
            except ImportError:
                pass
            # Check for media files and offer transcription
            _media_exts = {
                ".mp4", ".mp3", ".wav", ".m4a", ".mpeg", ".mpga",
                ".webm", ".avi", ".mov", ".mkv", ".ogg", ".flac", ".aac",
            }
            _media_names = [
                fn for fn in saved_names
                if os.path.splitext(fn)[1].lower() in _media_exts
            ]
            if _media_names:
                st.session_state["_pending_transcription"] = _media_names
            # Start background ingestion
            try:
                from core.ingestion_worker import start_background_ingestion
                start_background_ingestion(
                    case_id,
                    case_mgr,
                    model_provider,
                    force_ocr=st.session_state.get("_force_ocr_mode", False),
                )
            except ImportError:
                pass
            # Start passive OCR worker
            try:
                from core.ocr_worker import start_ocr_worker
                start_ocr_worker(case_id, case_mgr, model_provider)
            except Exception:
                pass

        # ---- Helper: scan a folder path, dedup, and import in one shot ----
        def _scan_and_import_folder(folder_path_str: str, recurse: bool = True):
            """Scan folder, dedup against case files, save all new files, run pipeline."""
            _fp = Path(folder_path_str.strip().strip('"').strip("'"))
            logger.info("[folder-import] Starting import from: %s", _fp)
            if not _fp.exists() or not _fp.is_dir():
                st.error(f"\u274c Folder not found on disk: `{_fp}`")
                logger.error("[folder-import] Folder not found: %s", _fp)
                return
            _pattern = "**/*" if recurse else "*"
            _found_files = []
            for _f in _fp.glob(_pattern):
                if _f.is_file() and _f.suffix.lower() in _SUPPORTED_EXTS:
                    _found_files.append(_f)
            _found_files.sort(key=lambda f: f.name.lower())
            logger.info("[folder-import] Found %d supported files in %s", len(_found_files), _fp)
            if not _found_files:
                st.warning(
                    f"No supported files found in **{_fp.name}**. "
                    f"Supported types: {', '.join(sorted(_SUPPORTED_EXTS))}",
                    icon="\U0001f4c2",
                )
                return
            _existing_names = set(
                os.path.basename(f) for f in (case_mgr.get_case_files(case_id) or [])
            )
            _seen_names: set = set()
            _to_import = []
            _dup_names = []
            for _f in _found_files:
                if _f.name in _existing_names or _f.name in _seen_names:
                    _dup_names.append(_f.name)
                else:
                    _seen_names.add(_f.name)
                    _to_import.append(_f)
            if _dup_names:
                _dup_display = ", ".join(f"**{n}**" for n in _dup_names[:10])
                _extra = f" +{len(_dup_names) - 10} more" if len(_dup_names) > 10 else ""
                st.warning(
                    f"Skipped {len(_dup_names)} duplicate(s): {_dup_display}{_extra}",
                    icon="\u26a0\ufe0f",
                )
            if not _to_import:
                st.info("All files in this folder are already in the case.")
                return
            _bar = st.progress(0, text="\U0001f4c1 Importing folder...")
            _saved = []
            _errors = []
            for _i, _f in enumerate(_to_import):
                _bar.progress(
                    min(int((_i / len(_to_import)) * 100), 99),
                    text=f"\U0001f4be {_f.name} ({_i + 1}/{len(_to_import)})",
                )
                try:
                    _data = _f.read_bytes()
                    case_mgr.save_file(case_id, _data, _f.name)
                    _saved.append(_f.name)
                    logger.info("[folder-import] Saved: %s (%d bytes)", _f.name, len(_data))
                except Exception as _save_err:
                    _errors.append((_f.name, str(_save_err)))
                    logger.error("[folder-import] Failed to save %s: %s", _f.name, _save_err)
            _bar.empty()

            if _errors:
                _err_list = "\n".join(f"- **{n}**: {e}" for n, e in _errors[:5])
                st.error(f"\u274c {len(_errors)} file(s) failed to save:\n{_err_list}")

            if _saved:
                # Verify files actually landed on disk
                _verify_files = case_mgr.get_case_files(case_id) or []
                _verify_names = set(os.path.basename(f) for f in _verify_files)
                _confirmed = [n for n in _saved if n in _verify_names]
                logger.info(
                    "[folder-import] Verified: %d/%d files on disk",
                    len(_confirmed), len(_saved),
                )
                _post_upload_pipeline(_saved)
                # Clear any stale folder import state
                for _k in ("_folder_import_files", "_folder_dup_existing",
                            "_folder_dup_internal"):
                    st.session_state.pop(_k, None)
                st.toast(
                    f"\u2705 Imported {len(_confirmed)} file(s) from "
                    f"**{_fp.name}**"
                )
                st.rerun()
            else:
                st.error("No files were saved. Check the folder path and permissions.")

        # ---- File & Folder Upload Zone ----
        _uploader_key = f"_case_uploader_{st.session_state.get('_uploader_key_counter', 0)}"

        # -- Top row: Upload buttons --
        _up_col1, _up_col2 = st.columns(2)
        with _up_col1:
            st.markdown("**\U0001f4c4 Upload Files**")
        with _up_col2:
            if st.button(
                "\U0001f4c1 Import Folder",
                key="_folder_import_top_btn",
                use_container_width=True,
                type="primary",
                help="Open folder picker — imports all supported files from the folder",
            ):
                # Open native folder picker (tkinter) — keep _scan_and_import_folder
                # OUTSIDE try/except so st.rerun() can propagate.
                _selected_folder = None
                try:
                    import tkinter as _tk
                    from tkinter import filedialog as _fd
                    _root = _tk.Tk()
                    _root.withdraw()
                    _root.wm_attributes("-topmost", 1)
                    _selected_folder = _fd.askdirectory(title="Select folder to import into case")
                    _root.destroy()
                except Exception as _e:
                    logger.error("[folder-import-btn] Picker error: %s", _e)
                    st.error(f"Folder picker error: {_e}")
                if _selected_folder:
                    logger.info("[folder-import-btn] User selected: %s", _selected_folder)
                    _scan_and_import_folder(_selected_folder)

        uploaded_files = st.file_uploader(
            "Upload Evidence",
            type=[e.lstrip(".") for e in sorted(_SUPPORTED_EXTS)],
            accept_multiple_files=True,
            key=_uploader_key,
            label_visibility="collapsed",
        )

        if uploaded_files:
            _existing_names = set(
                os.path.basename(f) for f in (case_mgr.get_case_files(case_id) or [])
            )
            _dup_files = [uf for uf in uploaded_files if uf.name in _existing_names]
            _new_files = [uf for uf in uploaded_files if uf.name not in _existing_names]

            # Show duplicate rejection feedback
            if _dup_files:
                _dup_names = ", ".join(f"**{uf.name}**" for uf in _dup_files)
                st.warning(
                    f"Skipped {len(_dup_files)} duplicate(s): {_dup_names}",
                    icon="\u26a0\ufe0f",
                )

            if _new_files:
                _ingest_bar = st.progress(0, text="\U0001f4be Saving new files...")
                for _i, _uf in enumerate(_new_files):
                    _save_pct = int((_i / len(_new_files)) * 30)
                    _ingest_bar.progress(
                        min(_save_pct, 29),
                        text=f"\U0001f4be Saving {_uf.name}... ({_i + 1}/{len(_new_files)})",
                    )
                    case_mgr.save_file(case_id, _uf, _uf.name)
                _ingest_bar.empty()
                _post_upload_pipeline([_uf.name for _uf in _new_files])
                st.rerun()

        # ---- Folder Drag-and-Drop Zone ----
        try:
            from ui.components.folder_drop import folder_drop_zone, find_folder_on_disk

            _drop_key = f"_folder_drop_{st.session_state.get('_folder_drop_counter', 0)}"
            _dropped = folder_drop_zone(
                supported_extensions=sorted(_SUPPORTED_EXTS),
                height=120,
                key=_drop_key,
            )
            # JS sends metadata only (no file content) to avoid browser OOM.
            # Python locates the folder on disk and reads files directly.
            if _dropped and isinstance(_dropped, dict) and _dropped.get("folder_name"):
                _drop_folder_name = _dropped["folder_name"]
                _drop_files_meta = _dropped.get("files", [])
                _total_mb = _dropped.get("total_bytes", 0) / (1024 * 1024)

                logger.info(
                    "[folder-drop] Received drop: folder=%s, files=%d, size=%.1f MB",
                    _drop_folder_name, len(_drop_files_meta), _total_mb,
                )
                st.info(
                    f"\U0001f4c1 Detected **{_drop_folder_name}** "
                    f"({len(_drop_files_meta)} files, {_total_mb:.1f} MB) — locating on disk..."
                )

                # Bump counter so the component resets on next render
                st.session_state["_folder_drop_counter"] = (
                    st.session_state.get("_folder_drop_counter", 0) + 1
                )

                # Try to locate the folder on the local filesystem
                _found_path = find_folder_on_disk(_drop_folder_name)

                if _found_path:
                    logger.info("[folder-drop] Auto-detected path: %s", _found_path)
                    _scan_and_import_folder(str(_found_path))
                else:
                    # Auto-detect failed — try opening native folder picker
                    logger.warning(
                        "[folder-drop] Could not auto-locate '%s', opening picker",
                        _drop_folder_name,
                    )
                    _picker_path = None
                    try:
                        import tkinter as _tk
                        from tkinter import filedialog as _fd
                        _root = _tk.Tk()
                        _root.withdraw()
                        _root.wm_attributes("-topmost", 1)
                        _picker_path = _fd.askdirectory(
                            title=f"Locate the dropped folder: {_drop_folder_name}",
                        )
                        _root.destroy()
                    except Exception as _tk_err:
                        logger.warning("[folder-drop] tkinter picker failed: %s", _tk_err)

                    if _picker_path:
                        _scan_and_import_folder(_picker_path)
                    else:
                        st.warning(
                            f"Could not locate **{_drop_folder_name}**. "
                            "Use the **Import Folder** button above to select the folder."
                        )
        except ImportError:
            pass  # Component not available — folder drop silently disabled

        # ---- Manual Folder Path Input (fallback) ----
        with st.expander("\U0001f4c1 Paste Folder Path", expanded=False):
            st.caption(
                "Paste a full folder path and click Import. "
                "Subfolders included. Duplicates auto-skipped."
            )
            _folder_path_input = st.text_input(
                "Folder path",
                placeholder=r"C:\Users\...\Case Files",
                key="_folder_path_text",
                label_visibility="collapsed",
            )
            if _folder_path_input and st.button(
                "\U0001f4e5 Import Folder", key="_folder_scan_btn",
                use_container_width=True, type="primary",
            ):
                _scan_and_import_folder(_folder_path_input)

        # ---- Auto-Classification Preview ----
        _pending_tags = st.session_state.get("_pending_auto_tags", {})
        if _pending_tags:
            with st.container(border=True):
                st.markdown("#### \U0001f3f7\ufe0f Auto-Classification Preview")
                st.caption(
                    "Files were automatically classified based on filename patterns. "
                    "Review and adjust tags below, or click **Classify Later** to skip."
                )
                _apply_tags = {}
                _tag_options = (
                    case_mgr.FILE_TAG_CATEGORIES
                    + case_mgr.get_custom_file_tag_categories(case_id)
                    + ["\u2795 Add New..."]
                )
                for _at_fn, _at_suggested in _pending_tags.items():
                    _at_col1, _at_col2, _at_col3 = st.columns([0.35, 0.35, 0.15])
                    with _at_col1:
                        st.markdown(f"**{_at_fn}**")
                    with _at_col2:
                        _at_choice = st.selectbox(
                            "Tag",
                            [_at_suggested] + [t for t in _tag_options if t != _at_suggested and t != "\u2795 Add New..."],
                            key=f"_at_{_at_fn}",
                            label_visibility="collapsed",
                        )
                        _apply_tags[_at_fn] = _at_choice
                    with _at_col3:
                        if st.button("Skip", key=f"_at_skip_{_at_fn}", help="Classify later"):
                            _apply_tags.pop(_at_fn, None)

                _at_btn_col1, _at_btn_col2 = st.columns(2)
                with _at_btn_col1:
                    if st.button(
                        "\u2705 Apply All Tags",
                        type="primary",
                        use_container_width=True,
                        key="_at_apply_all",
                    ):
                        for _at_fn, _at_tag in _apply_tags.items():
                            if _at_tag:
                                case_mgr.set_file_tags(case_id, _at_fn, [_at_tag])
                        st.session_state.pop("_pending_auto_tags", None)
                        st.toast(f"\U0001f3f7\ufe0f Tagged {len(_apply_tags)} files")
                        st.rerun()
                with _at_btn_col2:
                    if st.button(
                        "\u23e9 Classify Later",
                        use_container_width=True,
                        key="_at_classify_later",
                    ):
                        st.session_state.pop("_pending_auto_tags", None)
                        st.toast("Classification skipped -- you can tag files anytime")
                        st.rerun()

        # ---- Transcription Prompt (after media upload) ----
        _pending_tr = st.session_state.get("_pending_transcription")
        if _pending_tr:
            _n_media = len(_pending_tr)
            with st.container(border=True):
                st.info(
                    f"\U0001f3ac **{_n_media} video/audio file{'s' if _n_media > 1 else ''} detected.** "
                    "Transcribe now for faster analysis later?"
                )
                _tr_col1, _tr_col2 = st.columns(2)
                with _tr_col1:
                    if st.button(
                        "\U0001f3a4 Transcribe Now",
                        type="primary",
                        use_container_width=True,
                        key="_transcribe_now_btn",
                    ):
                        try:
                            from core.transcription_worker import start_transcription_worker
                            _all_case_files = case_mgr.get_case_files(case_id) or []
                            _media_paths = [
                                fp for fp in _all_case_files
                                if os.path.basename(fp) in _pending_tr
                            ]
                            start_transcription_worker(case_id, case_mgr, _media_paths)
                            st.session_state.pop("_pending_transcription", None)
                            st.toast(f"\U0001f3a4 Transcribing {len(_media_paths)} file(s) in background...")
                        except Exception as _tr_err:
                            st.error(f"Could not start transcription: {_tr_err}")
                        st.rerun()
                with _tr_col2:
                    if st.button(
                        "\u23e9 Skip \u2014 Transcribe During Analysis",
                        use_container_width=True,
                        key="_transcribe_skip_btn",
                    ):
                        st.session_state.pop("_pending_transcription", None)
                        st.toast("Transcription skipped \u2014 will run during analysis")
                        st.rerun()

        # ---- Transcription Progress ----
        try:
            from core.transcription_worker import get_transcription_status as _get_tr_status
            _tr_status = _get_tr_status(case_id)
            if _tr_status.get("status") == "running":
                try:
                    from streamlit_autorefresh import st_autorefresh
                    st_autorefresh(interval=5000, limit=None, key="_bg_transcription_poll")
                except ImportError:
                    pass
                _tr_done = _tr_status.get("files_done", 0)
                _tr_total = max(_tr_status.get("files_total", 1), 1)
                _tr_file = _tr_status.get("current_file", "")
                _tr_pct = _tr_done / _tr_total
                st.progress(
                    _tr_pct,
                    text=f"\U0001f3a4 **Transcribing:** {_tr_file} ({_tr_done}/{_tr_total})",
                )
        except ImportError:
            pass

        # Ingestion polling
        try:
            from core.ingestion_worker import (
                get_ingestion_status, clear_ingestion_status, write_ingestion_decision,
            )

            ingestion_status = get_ingestion_status(case_id)
            _ing_st = ingestion_status.get("status")

            if _ing_st == "running":
                try:
                    from streamlit_autorefresh import st_autorefresh

                    st_autorefresh(interval=5000, limit=None, key="_bg_ingestion_poll")
                except ImportError:
                    pass
                pct = ingestion_status.get("progress", 0) / 100.0
                msg = ingestion_status.get("message", "Processing documents...")
                st.progress(pct, text=f"\u23f3 **Ingesting Documents:** {pct * 100:.2f}% - {msg}")
                st.info(
                    "\U0001f4a1 You can navigate to other tabs while documents process in the background."
                )
            elif _ing_st == "file_error":
                # A file failed — worker is paused waiting for user decision
                try:
                    from streamlit_autorefresh import st_autorefresh

                    st_autorefresh(interval=3000, limit=None, key="_bg_ingestion_poll")
                except ImportError:
                    pass
                _failed_file = ingestion_status.get("failed_file", "unknown file")
                _err_detail = ingestion_status.get("error_detail", "Unknown error")
                st.error(
                    f"\u26a0\ufe0f **File processing error:** `{_failed_file}`\n\n"
                    f"**Error:** {_err_detail}"
                )
                st.warning("Processing is paused. Choose an action to continue:")
                _skip_col, _retry_col = st.columns(2)
                with _skip_col:
                    if st.button("\u23e9 Skip This File", use_container_width=True, key="_ing_skip_file"):
                        write_ingestion_decision(case_id, "skip")
                        st.rerun()
                with _retry_col:
                    if st.button("\U0001f504 Retry This File", use_container_width=True, key="_ing_retry_file"):
                        write_ingestion_decision(case_id, "retry")
                        st.rerun()
            elif _ing_st == "error":
                st.error(
                    f"\u274c **Ingestion Failed:** {ingestion_status.get('message')}"
                )
                if st.button("Dismiss Error"):
                    clear_ingestion_status(case_id)
                    st.rerun()
            elif _ing_st == "completed":
                if not st.session_state.get("_waiting_for_analysis_preview", False):
                    st.success(f"\u2705 **{ingestion_status.get('message')}**")
                    clear_ingestion_status(case_id)
        except ImportError:
            pass


def _render_analysis_engine(
    case_id, prep_id, case_mgr, model_provider, current_prep_type, current_prep_name
):
    """Render the two-step analysis engine."""
    from core.nodes.graph_builder import NODE_LABELS, get_node_count

    _pending = st.session_state.get("_analysis_pending")

    if not _pending:
        # STEP 1: Run button
        _is_waiting = st.session_state.get("_waiting_for_analysis_preview", False)

        if _is_waiting:
            try:
                from core.ingestion_worker import (
                    get_ingestion_status, clear_ingestion_status, write_ingestion_decision,
                )

                _stat = get_ingestion_status(case_id)
                _ing_status = _stat.get("status", "none")

                if _ing_status == "running":
                    try:
                        from streamlit_autorefresh import st_autorefresh

                        st_autorefresh(interval=2000, limit=None, key="_bg_analysis_poll")
                    except ImportError:
                        pass
                    pct = _stat.get("progress", 0) / 100.0
                    msg = _stat.get("message", "Processing documents...")
                    st.progress(
                        pct,
                        text=f"\u23f3 **Preparing files for analysis:** {pct * 100:.2f}% - {msg}",
                    )

                    # --- Ingestion Stream of Consciousness ---
                    import html as _html_mod
                    from datetime import datetime as _dt_cls

                    _ing_updated = _stat.get("updated_at", "")
                    _stale_warning = ""
                    if _ing_updated:
                        try:
                            _last_update = _dt_cls.fromisoformat(_ing_updated)
                            _age_secs = (_dt_cls.now() - _last_update).total_seconds()
                            if _age_secs > 180:
                                _stale_warning = (
                                    f"<div style='color:#f0883e;margin-top:4px;'>"
                                    f"&#9888; Last update was {int(_age_secs)}s ago "
                                    f"&mdash; file may be taking a long time (OCR on scanned pages). "
                                    f"The file will auto-skip after 5 minutes.</div>"
                                )
                            elif _age_secs > 60:
                                _stale_warning = (
                                    f"<div style='color:#8b949e;margin-top:4px;'>"
                                    f"&#8987; Processing for {int(_age_secs)}s... "
                                    f"(OCR on scanned documents can take 1-2 min per page)</div>"
                                )
                        except Exception:
                            pass

                    _safe_msg = _html_mod.escape(msg)
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #30363d;"
                        f"border-radius:6px;padding:12px 16px;margin-top:8px;"
                        f"font-family:monospace;font-size:13px;"
                        f"line-height:1.5;color:#c9d1d9;'>"
                        f"<div style='color:#58a6ff;font-weight:bold;margin-bottom:6px;'>"
                        f"&#128196; Document Processing</div>"
                        f"<div>{_safe_msg}</div>"
                        f"{_stale_warning}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                elif _ing_status == "file_error":
                    try:
                        from streamlit_autorefresh import st_autorefresh

                        st_autorefresh(interval=3000, limit=None, key="_bg_analysis_poll")
                    except ImportError:
                        pass
                    _af = _stat.get("failed_file", "unknown file")
                    _ad = _stat.get("error_detail", "Unknown error")
                    st.error(
                        f"\u26a0\ufe0f **File processing error:** `{_af}`\n\n"
                        f"**Error:** {_ad}"
                    )
                    st.warning("Processing is paused. Choose an action to continue:")
                    _asc, _arc = st.columns(2)
                    with _asc:
                        if st.button("\u23e9 Skip This File", use_container_width=True, key="_analysis_skip_file"):
                            write_ingestion_decision(case_id, "skip")
                            st.rerun()
                    with _arc:
                        if st.button("\U0001f504 Retry This File", use_container_width=True, key="_analysis_retry_file"):
                            write_ingestion_decision(case_id, "retry")
                            st.rerun()
                elif _ing_status == "error":
                    st.error(f"\u274c **Preparation Failed:** {_stat.get('message')}")
                    if st.button("Dismiss & Try Again"):
                        clear_ingestion_status(case_id)
                        st.session_state._waiting_for_analysis_preview = False
                        st.rerun()
                elif _ing_status in ("completed", "none"):
                    st.session_state._waiting_for_analysis_preview = False
                    st.session_state._trigger_token_count = True
                    try:
                        clear_ingestion_status(case_id)
                    except Exception:
                        pass
                    st.rerun()
            except ImportError:
                st.session_state._waiting_for_analysis_preview = False
                st.rerun()
        else:
            # Show Run Full Analysis + Re-analyze buttons
            st.markdown('<div class="analysis-btn-wrap">', unsafe_allow_html=True)
            _analysis_col1, _analysis_col2 = st.columns([3, 1])
            with _analysis_col1:
                _run_btn = st.button(
                    "\U0001f680 Run Full Analysis",
                    use_container_width=True,
                    type="primary",
                    key="_run_full_analysis_btn",
                )
            st.markdown("</div>", unsafe_allow_html=True)
            with _analysis_col2:
                _reanalyze_toggle = st.button(
                    "\U0001f504 Re-analyze", use_container_width=True,
                    key="_reanalyze_toggle_btn",
                )

            # Toggle the re-analyze module selector panel
            if _reanalyze_toggle:
                _currently_open = st.session_state.get("_reanalyze_panel_open", False)
                st.session_state._reanalyze_panel_open = not _currently_open
                if not _currently_open:
                    # Initialize module selection with all checked
                    st.session_state._reanalyze_modules = {k: True for k in NODE_LABELS}
                st.rerun()

            # ── Re-analyze Module Selector Panel ──
            if st.session_state.get("_reanalyze_panel_open", False):
                with st.container(border=True):
                    st.markdown("#### \U0001f504 Re-analyze \u2014 Select Modules")
                    st.caption("Choose which analysis modules to re-run. Only selected modules will be executed.")

                    if "_reanalyze_modules" not in st.session_state:
                        st.session_state._reanalyze_modules = {k: True for k in NODE_LABELS}

                    # Select All / Deselect All
                    _sa_col1, _sa_col2, _sa_col3 = st.columns([1, 1, 2])
                    with _sa_col1:
                        if st.button("\u2705 Select All", key="_ra_sel_all", use_container_width=True):
                            st.session_state._reanalyze_modules = {k: True for k in NODE_LABELS}
                            st.rerun()
                    with _sa_col2:
                        if st.button("\u2b1c Deselect All", key="_ra_desel_all", use_container_width=True):
                            st.session_state._reanalyze_modules = {k: False for k in NODE_LABELS}
                            st.rerun()
                    with _sa_col3:
                        _ra_n_sel = sum(1 for v in st.session_state._reanalyze_modules.values() if v)
                        st.caption(f"**{_ra_n_sel}/{len(NODE_LABELS)}** modules selected")

                    # Module checkboxes in 3 columns
                    _ra_keys = list(NODE_LABELS.keys())
                    _ra_col_size = (len(_ra_keys) + 2) // 3
                    _rac1, _rac2, _rac3 = st.columns(3)
                    for _ri, _rk in enumerate(_ra_keys):
                        _ra_col = _rac1 if _ri < _ra_col_size else (_rac2 if _ri < _ra_col_size * 2 else _rac3)
                        with _ra_col:
                            _ra_checked = st.checkbox(
                                NODE_LABELS[_rk],
                                value=st.session_state._reanalyze_modules.get(_rk, True),
                                key=f"_ra_mod_{_rk}",
                            )
                            st.session_state._reanalyze_modules[_rk] = _ra_checked

                    st.markdown("---")

                    # Run / Cancel
                    _ra_run_col, _ra_cancel_col = st.columns(2)
                    with _ra_run_col:
                        _ra_n_active = sum(1 for v in st.session_state._reanalyze_modules.values() if v)
                        _ra_run_label = (
                            f"\U0001f680 Run {_ra_n_active} Module{'s' if _ra_n_active != 1 else ''}"
                            if _ra_n_active < len(NODE_LABELS)
                            else "\U0001f680 Run All Modules"
                        )
                        _ra_run_btn = st.button(
                            _ra_run_label, type="primary", use_container_width=True,
                            key="_ra_run_btn", disabled=(_ra_n_active == 0),
                        )
                    with _ra_cancel_col:
                        _ra_cancel_btn = st.button(
                            "\u274c Cancel", use_container_width=True, key="_ra_cancel_btn",
                        )

                    if _ra_cancel_btn:
                        st.session_state._reanalyze_panel_open = False
                        st.session_state.pop("_reanalyze_modules", None)
                        st.rerun()

                    if _ra_run_btn:
                        if not case_mgr.get_case_files(case_id):
                            st.error("Please upload documents first.")
                        else:
                            _ra_active = {
                                k for k, v in st.session_state._reanalyze_modules.items() if v
                            }
                            st.session_state._reanalyze_panel_open = False
                            st.session_state.pop("_reanalyze_modules", None)

                            # Load cached documents (skip ingestion)
                            _ra_all_paths = case_mgr.get_case_files(case_id)
                            _ra_all_docs = []
                            _ra_cache_path = os.path.join(DATA_DIR, case_id, "ingestion_cache.json")
                            if os.path.exists(_ra_cache_path):
                                try:
                                    with open(_ra_cache_path, "r", encoding="utf-8") as _raf:
                                        _ra_cache = json.load(_raf)
                                    from langchain_core.documents import Document as _RaDoc
                                    for _rk2, _rvs in _ra_cache.items():
                                        for _rv in _rvs:
                                            _ra_all_docs.append(
                                                _RaDoc(page_content=_rv["page_content"],
                                                       metadata=_rv.get("metadata", {}))
                                            )
                                except Exception:
                                    pass

                            if not _ra_all_docs:
                                # No cached docs — need to run ingestion first
                                st.warning("No cached documents found. Running ingestion first...")
                                try:
                                    from core.ingestion_worker import start_background_ingestion
                                    start_background_ingestion(
                                        case_id, case_mgr, model_provider,
                                        force_ocr=st.session_state.get("_force_ocr_mode", False),
                                    )
                                except ImportError:
                                    pass
                                st.session_state._waiting_for_analysis_preview = True
                                st.rerun()
                            else:
                                # Go straight to analysis — skip ingestion
                                if not prep_id:
                                    prep_id = case_mgr.create_preparation(
                                        case_id, "trial", "Trial Preparation"
                                    )
                                    st.session_state.current_prep_id = prep_id
                                    _ra_ptype = "trial"
                                    _ra_pname = "Trial Preparation"
                                else:
                                    _ra_pm = case_mgr.get_preparation(case_id, prep_id) or {}
                                    _ra_ptype = _ra_pm.get("type", "trial")
                                    _ra_pname = _ra_pm.get("name", "Trial Preparation")

                                _ra_state = {
                                    "case_files": _ra_all_paths,
                                    "raw_documents": _ra_all_docs,
                                    "current_model": model_provider,
                                    "max_context_mode": st.session_state.get("_max_context_mode", True),
                                    "case_id": case_id,
                                    "case_type": case_mgr.get_case_type(case_id),
                                    "client_name": case_mgr.get_client_name(case_id),
                                    "attorney_directives": case_mgr.load_directives(case_id),
                                    "prep_type": _ra_ptype,
                                    "prep_name": _ra_pname,
                                    "_file_tags": case_mgr.get_all_file_tags(case_id),
                                }
                                try:
                                    from core.bg_analysis import start_background_analysis
                                    start_background_analysis(
                                        case_id=case_id,
                                        prep_id=prep_id,
                                        state=_ra_state,
                                        active_modules=(
                                            _ra_active
                                            if _ra_active != set(NODE_LABELS.keys())
                                            else None
                                        ),
                                        prep_type=_ra_ptype,
                                        model_provider=model_provider,
                                        max_context_mode=st.session_state.get("_max_context_mode", True),
                                    )
                                    st.toast(
                                        f"\U0001f680 Re-analysis started ({len(_ra_active)} modules)!",
                                        icon="\U0001f504",
                                    )
                                    st.session_state._bg_analysis_active = True
                                except ImportError as exc:
                                    st.error(f"Background analysis module not available: {exc}")
                                st.rerun()

            _auto_trigger = st.session_state.pop("_trigger_token_count", False)

            # Run Full Analysis button handler — skip ingestion if docs already cached
            if _run_btn or st.session_state.pop("_reanalyze", False):
                if not case_mgr.get_case_files(case_id):
                    st.error("Please upload documents first.")
                else:
                    _all_case_paths = case_mgr.get_case_files(case_id)
                    _force_ocr = st.session_state.get("_force_ocr_mode", False)

                    # Check if ingestion cache already has all files
                    _cache_path = os.path.join(DATA_DIR, case_id, "ingestion_cache.json")
                    _cached_keys = set()
                    _needs_ingestion = _force_ocr  # force_ocr always re-ingests
                    if not _needs_ingestion and os.path.exists(_cache_path):
                        try:
                            with open(_cache_path, "r", encoding="utf-8") as _cf:
                                _cached_keys = set(json.load(_cf).keys())
                        except Exception:
                            _needs_ingestion = True

                        if not _needs_ingestion:
                            # Check each file — if any file is not in cache, we need ingestion
                            for _fp in _all_case_paths:
                                _fn = os.path.basename(_fp)
                                try:
                                    _fsz = os.path.getsize(_fp)
                                except OSError:
                                    _fsz = 0
                                _fkey = f"{_fn}:{_fsz}"
                                if _fkey not in _cached_keys:
                                    _needs_ingestion = True
                                    break
                    else:
                        _needs_ingestion = True

                    if _needs_ingestion:
                        # New/changed files detected — run ingestion first
                        try:
                            from core.ingestion_worker import start_background_ingestion
                            start_background_ingestion(
                                case_id, case_mgr, model_provider,
                                force_ocr=_force_ocr,
                            )
                        except ImportError:
                            pass
                        st.session_state._waiting_for_analysis_preview = True
                        st.rerun()
                    else:
                        # All files cached — skip ingestion, go straight to token preview
                        st.session_state._trigger_token_count = True
                        st.rerun()

            if _auto_trigger:
                # Token counting after ingestion completes
                all_paths = case_mgr.get_case_files(case_id)
                all_docs = []
                _acache_path = os.path.join(DATA_DIR, case_id, "ingestion_cache.json")
                if os.path.exists(_acache_path):
                    try:
                        with open(_acache_path, "r", encoding="utf-8") as _acf:
                            _acache = json.load(_acf)
                            for _k, _cached_docs in _acache.items():
                                from langchain_core.documents import Document as _DocA

                                for _acd in _cached_docs:
                                    all_docs.append(
                                        _DocA(
                                            page_content=_acd["page_content"],
                                            metadata=_acd.get("metadata", {}),
                                        )
                                    )
                    except Exception:
                        pass

                _doc_text = "\n".join(str(d) for d in all_docs)
                _est_tokens = len(_doc_text) // 4
                _node_count = get_node_count(current_prep_type)
                _per_node_overhead = 1000
                _total_prompt_tokens = (_est_tokens * _node_count) + (
                    _per_node_overhead * _node_count
                )

                _model_limits = {
                    "xai": ("Grok", 131_072),
                    "claude-sonnet-4.6": ("Claude Sonnet 4.6", 1_000_000),
                    "claude-sonnet-4.5": ("Claude Sonnet 4.5", 200_000),
                    "claude-opus-4.6": ("Claude Opus 4.6", 1_000_000),
                    "gemini": ("Gemini Pro", 1_000_000),
                }
                _model_name, _ctx_limit = _model_limits.get(
                    model_provider, ("Unknown", 200_000)
                )

                _cost_rates = {
                    "xai": 0.005,
                    "gemini": 0.00125,
                    "claude-opus-4.6": 0.015,
                    "claude-sonnet-4.6": 0.005,
                    "claude-sonnet-4.5": 0.003,
                }
                _cost_per_1k = _cost_rates.get(model_provider, 0.003)
                _est_cost = (_total_prompt_tokens / 1000) * _cost_per_1k
                _needs_chunking = _est_tokens > int(_ctx_limit * 0.80)
                _num_chunks = 1
                if _needs_chunking:
                    try:
                        from core.workflow import chunk_documents

                        _num_chunks = len(
                            chunk_documents(all_docs, int(_ctx_limit * 0.80))
                        )
                    except ImportError:
                        _num_chunks = 2

                st.session_state._analysis_pending = {
                    "all_paths": all_paths,
                    "all_docs": all_docs,
                    "est_tokens": _est_tokens,
                    "total_prompt_tokens": _total_prompt_tokens,
                    "node_count": _node_count,
                    "model_name": _model_name,
                    "ctx_limit": _ctx_limit,
                    "est_cost": _est_cost,
                    "fits": _est_tokens < _ctx_limit,
                    "total_files": len(all_paths) if all_paths else 0,
                    "total_chars": len(_doc_text),
                    "needs_chunking": _needs_chunking,
                    "num_chunks": _num_chunks,
                }
                st.rerun()
    else:
        # STEP 2: Token preview + module selector + confirm
        _p = _pending

        st.markdown("---")
        st.subheader("\U0001f4ca Analysis Preview \u2014 Token Estimate")

        _n_chunks = _p.get("num_chunks", 1)
        if _n_chunks > 1:
            m1, m2, m3, m4, m5 = st.columns(5)
        else:
            m1, m2, m3, m4 = st.columns(4)
            m5 = None
        m1.metric("\U0001f4c4 Documents", f"{_p['total_files']}")
        m2.metric("\U0001f4dd Doc Tokens", f"{_p['est_tokens']:,}")
        m3.metric("\U0001f504 AI Nodes", f"{_p['node_count']}")
        m4.metric("\U0001f4b0 Est. Cost", f"${_p['est_cost']:.2f}")
        if m5 is not None:
            m5.metric("\U0001f4e6 Chunks", f"{_n_chunks}")

        _pct_used = (_p["est_tokens"] / _p["ctx_limit"]) * 100
        if _p.get("needs_chunking"):
            st.info(
                f"\U0001f4e6 **Auto-Chunking Enabled** \u2014 Documents will be split into **{_n_chunks} chunks** per node."
            )
        elif _pct_used > 100:
            st.error(
                f"\u26a0\ufe0f **EXCEEDS CONTEXT LIMIT** \u2014 {_p['est_tokens']:,} tokens vs {_p['ctx_limit']:,} limit."
            )
        elif _pct_used > 75:
            st.warning(f"\U0001f7e1 **Large prompt** \u2014 {_pct_used:.0f}% of context window.")
        else:
            st.success(f"\u2705 {_pct_used:.0f}% of context window used.")

        st.progress(
            min(_pct_used / 100, 1.0),
            text=f"Context window: {_pct_used:.1f}% ({_p['est_tokens']:,} / {_p['ctx_limit']:,})",
        )

        # ---- File Selector for Partial Document Analysis ----
        _all_file_paths = _p.get("all_paths") or []
        _all_file_names = [os.path.basename(fp) for fp in _all_file_paths]
        _total_file_count = len(_all_file_names)

        if _total_file_count > 1:
            with st.expander(f"\U0001f4c2 Select Documents for Analysis ({_total_file_count} files)", expanded=False):
                _fsel_col1, _fsel_col2 = st.columns(2)
                with _fsel_col1:
                    if st.button("\u2705 Select All Files", key="_fsel_all", use_container_width=True):
                        for _fn in _all_file_names:
                            st.session_state[f"_file_sel_{_fn}"] = True
                        st.rerun()
                with _fsel_col2:
                    if st.button("\u2b1c Deselect All Files", key="_fsel_none", use_container_width=True):
                        for _fn in _all_file_names:
                            st.session_state[f"_file_sel_{_fn}"] = False
                        st.rerun()

                # Get file tags for display
                _all_tags = case_mgr.get_all_file_tags(case_id)
                _selected_files = set()

                for _fn in sorted(_all_file_names):
                    _tags = _all_tags.get(_fn, [])
                    _tag_str = f" \u2014 *{', '.join(_tags)}*" if _tags else ""
                    _default = st.session_state.get(f"_file_sel_{_fn}", True)
                    _checked = st.checkbox(
                        f"{_fn}{_tag_str}",
                        value=_default,
                        key=f"_file_sel_{_fn}",
                    )
                    if _checked:
                        _selected_files.add(_fn)

                _n_selected_files = len(_selected_files)
                st.caption(f"**{_n_selected_files}/{_total_file_count}** files selected")

                # If subset selected, update the pending analysis data
                if _n_selected_files < _total_file_count:
                    _filtered_docs = [
                        d for d in _p["all_docs"]
                        if os.path.basename(d.metadata.get("source", "")) in _selected_files
                    ]
                    _filtered_paths = [
                        fp for fp in _all_file_paths
                        if os.path.basename(fp) in _selected_files
                    ]
                    _p["all_docs"] = _filtered_docs
                    _p["all_paths"] = _filtered_paths
                    _p["total_files"] = len(_filtered_paths)

                    # Recalculate token estimate
                    _filt_text = "\n".join(str(d) for d in _filtered_docs)
                    _p["est_tokens"] = len(_filt_text) // 4
                    _p["total_chars"] = len(_filt_text)
                    _p["total_prompt_tokens"] = (
                        (_p["est_tokens"] * _p["node_count"]) + (1000 * _p["node_count"])
                    )
                    _p["est_cost"] = (_p["total_prompt_tokens"] / 1000) * {
                        "xai": 0.005, "gemini": 0.00125,
                        "claude-opus-4.6": 0.015, "claude-sonnet-4.6": 0.005,
                        "claude-sonnet-4.5": 0.003,
                    }.get(model_provider, 0.003)
                    _p["fits"] = _p["est_tokens"] < _p["ctx_limit"]
                    _pct_used = (_p["est_tokens"] / _p["ctx_limit"]) * 100

                    st.info(
                        f"\U0001f4c2 Using **{_n_selected_files}/{_total_file_count}** files "
                        f"\u2014 ~{_p['est_tokens']:,} tokens ({_pct_used:.0f}% of context)"
                    )

        # Module selector
        st.markdown("---")
        st.markdown("#### \U0001f9e9 Select Analysis Modules")

        if "_selected_modules" not in st.session_state:
            st.session_state._selected_modules = {k: True for k in NODE_LABELS}

        _sel_col1, _sel_col2, _sel_col3 = st.columns([1, 1, 2])
        with _sel_col1:
            if st.button("\u2705 Select All", key="_sel_all_modules", use_container_width=True):
                st.session_state._selected_modules = {k: True for k in NODE_LABELS}
                st.rerun()
        with _sel_col2:
            if st.button(
                "\u2b1c Deselect All", key="_desel_all_modules", use_container_width=True
            ):
                st.session_state._selected_modules = {k: False for k in NODE_LABELS}
                st.rerun()
        with _sel_col3:
            _n_selected = sum(
                1 for v in st.session_state._selected_modules.values() if v
            )
            st.caption(f"**{_n_selected}/{len(NODE_LABELS)}** modules selected")

        _mod_keys = list(NODE_LABELS.keys())
        _col_size = (len(_mod_keys) + 2) // 3
        _mc1, _mc2, _mc3 = st.columns(3)
        for i, node_key in enumerate(_mod_keys):
            _target_col = _mc1 if i < _col_size else (_mc2 if i < _col_size * 2 else _mc3)
            with _target_col:
                _checked = st.checkbox(
                    NODE_LABELS[node_key],
                    value=st.session_state._selected_modules.get(node_key, True),
                    key=f"_mod_sel_{node_key}",
                )
                st.session_state._selected_modules[node_key] = _checked

        st.markdown("---")

        # Max context toggle
        _mcx = st.toggle(
            "\U0001f4d0 Enable Max Context (send ALL text, no truncation)",
            value=st.session_state.get("_max_context_mode", True),
            key="_analysis_max_ctx_toggle",
        )
        st.session_state._max_context_mode = _mcx

        # Confirm / Cancel
        _confirm_col, _cancel_col = st.columns(2)
        with _confirm_col:
            _n_active = sum(
                1 for v in st.session_state._selected_modules.values() if v
            )
            _confirm_label = (
                f"\u2705 Run {_n_active} Module{'s' if _n_active != 1 else ''}"
                if _n_active < len(NODE_LABELS)
                else "\u2705 Confirm & Run Full Analysis"
            )
            _confirm_btn = st.button(
                _confirm_label,
                type="primary",
                use_container_width=True,
                key="_confirm_analysis",
                disabled=(_n_active == 0),
            )
        with _cancel_col:
            _cancel_btn = st.button(
                "\u274c Cancel", use_container_width=True, key="_cancel_analysis"
            )

        if _cancel_btn:
            st.session_state._analysis_pending = None
            st.session_state.pop("_selected_modules", None)
            st.rerun()

        if _confirm_btn:
            all_docs = _p["all_docs"]
            all_paths = _p["all_paths"]
            _active_modules = {
                k for k, v in st.session_state._selected_modules.items() if v
            }
            st.session_state._analysis_pending = None
            st.session_state.pop("_selected_modules", None)

            if not prep_id:
                prep_id = case_mgr.create_preparation(
                    case_id, "trial", "Trial Preparation"
                )
                st.session_state.current_prep_id = prep_id
                _prep_type_val = "trial"
                _prep_name_val = "Trial Preparation"
            else:
                _prep_meta = case_mgr.get_preparation(case_id, prep_id) or {}
                _prep_type_val = _prep_meta.get("type", "trial")
                _prep_name_val = _prep_meta.get("name", "Trial Preparation")

            state = {
                "case_files": all_paths,
                "raw_documents": all_docs,
                "current_model": model_provider,
                "max_context_mode": st.session_state.get("_max_context_mode", True),
                "case_id": case_id,
                "case_type": case_mgr.get_case_type(case_id),
                "client_name": case_mgr.get_client_name(case_id),
                "attorney_directives": case_mgr.load_directives(case_id),
                "prep_type": _prep_type_val,
                "prep_name": _prep_name_val,
                "_file_tags": case_mgr.get_all_file_tags(case_id),
            }

            try:
                from core.bg_analysis import start_background_analysis

                start_background_analysis(
                    case_id=case_id,
                    prep_id=prep_id,
                    state=state,
                    active_modules=(
                        _active_modules
                        if _active_modules != set(NODE_LABELS.keys())
                        else None
                    ),
                    prep_type=_prep_type_val,
                    model_provider=model_provider,
                    max_context_mode=st.session_state.get("_max_context_mode", True),
                )
                st.toast(
                    "\U0001f680 Analysis started in background!",
                    icon="\U0001f504",
                )
                st.session_state._bg_analysis_active = True
            except Exception as exc:
                st.error(f"Could not start analysis: {exc}")
                logger.exception("start_background_analysis failed: %s", exc)
            st.rerun()

    # Background analysis progress monitor
    if prep_id:
        try:
            from core.bg_analysis import is_analysis_running, get_analysis_progress

            # Render autorefresh BEFORE the file read to prevent race condition:
            # On Windows, os.replace() during atomic writes can briefly make
            # progress.json unavailable, causing is_analysis_running() to return
            # False, which would skip the autorefresh component, permanently
            # stopping UI updates. Using a session state flag ensures the
            # autorefresh keeps firing until analysis is confirmed complete.
            _expect_running = st.session_state.get("_bg_analysis_active", False)
            if _expect_running or is_analysis_running(case_id, prep_id):
                try:
                    from streamlit_autorefresh import st_autorefresh
                    st_autorefresh(interval=2000, limit=None, key="_bg_analysis_progress_poll")
                except ImportError:
                    pass

            if is_analysis_running(case_id, prep_id):
                st.session_state._bg_analysis_active = True
                _bg_progress = get_analysis_progress(case_id, prep_id)
                _bg_nodes_done = _bg_progress.get("nodes_completed", 0)
                _bg_total = _bg_progress.get("total_nodes", 1)
                _bg_current = _bg_progress.get("current_node", "Processing...")
                _bg_description = _bg_progress.get("current_description", "Working...")
                _bg_node_pct = _bg_progress.get("node_pct", 0)
                _bg_completed_nodes = _bg_progress.get("completed_nodes", [])
                _bg_skipped_nodes = _bg_progress.get("skipped_nodes", [])
                _bg_per_node_times = _bg_progress.get("per_node_times", {})

                _bg_overall_pct = (
                    (_bg_nodes_done + (_bg_node_pct / 100.0)) / max(_bg_total, 1)
                ) * 100.0
                _bg_overall_pct = min(_bg_overall_pct, 99.0)

                # Load historical node times for ETA
                _hist_times = st.session_state.get("_historical_node_times")
                if _hist_times is None:
                    _prev_state = case_mgr.load_prep_state(case_id, prep_id)
                    _hist_times = _prev_state.get("_last_per_node_times", {}) if _prev_state else {}
                    st.session_state._historical_node_times = _hist_times

                # Estimate remaining time
                _est_remaining = 0.0
                if _hist_times:
                    for _hk, _hv in _hist_times.items():
                        if _hk not in _bg_completed_nodes and _hk not in _bg_skipped_nodes:
                            _est_remaining += _hv
                    # Subtract partial progress of current node
                    if _bg_current in _hist_times and _bg_node_pct > 0:
                        _est_remaining -= _hist_times[_bg_current] * (_bg_node_pct / 100.0)
                    _est_remaining = max(0, _est_remaining)

                _eta_text = ""
                if _est_remaining > 0:
                    if _est_remaining >= 60:
                        _eta_text = f" \u2014 ~{int(_est_remaining // 60)}m {int(_est_remaining % 60)}s remaining"
                    else:
                        _eta_text = f" \u2014 ~{int(_est_remaining)}s remaining"

                # Summary progress bar
                st.progress(
                    _bg_overall_pct / 100.0,
                    text=f"\U0001f504 **Analyzing:** {_bg_current} \u2014 {_bg_description} ({_bg_overall_pct:.1f}%){_eta_text}",
                )

                # Node grid visualization
                try:
                    from core.nodes.graph_builder import NODE_LABELS, NODE_DESCRIPTIONS
                except ImportError:
                    NODE_LABELS = {}
                    NODE_DESCRIPTIONS = {}

                _all_node_keys = list(NODE_LABELS.keys()) if NODE_LABELS else []
                if _all_node_keys:
                    st.markdown("#### \U0001f4ca Analysis Nodes")
                    _grid_cols = st.columns(3)
                    for _ni, _nkey in enumerate(_all_node_keys):
                        _n_label = NODE_LABELS.get(_nkey, _nkey)
                        _n_desc = NODE_DESCRIPTIONS.get(_nkey, "")[:50]
                        _n_time = _bg_per_node_times.get(_nkey, 0)

                        if _nkey in _bg_completed_nodes:
                            _n_color = "#2ea043"
                            _n_icon = "\u2705"
                            _n_status = f"{_n_time:.1f}s" if _n_time else "Done"
                        elif _nkey == _bg_current or _n_label == _bg_current:
                            _n_color = "#58a6ff"
                            _n_icon = "\U0001f535"
                            _n_status = f"{_bg_node_pct}%"
                        elif _nkey in _bg_skipped_nodes:
                            _n_color = "#d29922"
                            _n_icon = "\u23ed\ufe0f"
                            _n_status = "Skipped"
                        else:
                            _n_color = "#484f58"
                            _n_icon = "\u2b1c"
                            _n_hist = _hist_times.get(_nkey, 0) if _hist_times else 0
                            _n_status = f"~{_n_hist:.0f}s" if _n_hist else "Queued"

                        with _grid_cols[_ni % 3]:
                            st.markdown(
                                f"<div style='border:1px solid {_n_color};border-radius:8px;"
                                f"padding:8px 12px;margin:4px 0;background:rgba(0,0,0,0.2);'>"
                                f"<span style='font-size:1.1em;'>{_n_icon}</span> "
                                f"<strong style='color:{_n_color};'>{_n_label}</strong><br/>"
                                f"<span style='font-size:0.75em;opacity:0.6;'>{_n_desc}</span><br/>"
                                f"<span style='font-size:0.8em;color:{_n_color};'>{_n_status}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                # Info + cancel
                _bg_info_col, _bg_cancel_col = st.columns([4, 1])
                with _bg_info_col:
                    _bg_rate = _bg_progress.get("node_token_rate", 0)
                    _bg_tokens = _bg_progress.get("node_tokens", 0)
                    st.caption(
                        f"Step {_bg_nodes_done + 1}/{_bg_total} \u2014 "
                        f"{_bg_nodes_done} completed \u2014 "
                        f"{_bg_tokens} tokens ({_bg_rate} tok/s)"
                    )
                with _bg_cancel_col:
                    if st.button("\u23f9 Stop Analysis", key="_cancel_bg_analysis", type="secondary"):
                        from core.bg_analysis import stop_background_analysis
                        stop_background_analysis(case_id, prep_id)
                        st.toast("Stopping analysis... partial results will be saved.")
                        st.rerun()

                # AI Stream of Consciousness
                _bg_stream_text = _bg_progress.get("streamed_text", "")
                _show_thinking = st.checkbox(
                    "Show AI thinking", value=True, key="_show_ai_thinking",
                )
                if _show_thinking and _bg_stream_text:
                    import html as _html_mod
                    _safe_stream = _html_mod.escape(_bg_stream_text)
                    _safe_node = _html_mod.escape(_bg_current)
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #30363d;"
                        f"border-radius:6px;padding:12px 16px;max-height:400px;"
                        f"overflow-y:auto;font-family:monospace;font-size:13px;"
                        f"line-height:1.5;color:#c9d1d9;white-space:pre-wrap;"
                        f"word-wrap:break-word;'>"
                        f"<div style='color:#58a6ff;font-weight:bold;margin-bottom:8px;'>"
                        f"\U0001f9e0 {_safe_node}</div>"
                        f"{_safe_stream}"
                        f"<div id='_stream_bottom'></div>"
                        f"</div>"
                        f"<script>var e=document.getElementById('_stream_bottom');"
                        f"if(e)e.scrollIntoView({{behavior:'smooth'}});</script>",
                        unsafe_allow_html=True,
                    )
                elif _show_thinking and not _bg_stream_text:
                    st.caption("Waiting for AI output...")
            else:
                # Analysis is not running — detect transition and notify
                if st.session_state.get("_bg_analysis_active", False):
                    st.session_state._bg_analysis_active = False
                    st.session_state._historical_node_times = None  # Reset for next run
                    # Reload results from disk to pick up new data
                    st.session_state.agent_results = case_mgr.load_prep_state(
                        case_id, prep_id
                    )
                    st.success("Analysis complete! Results have been loaded.")
                    st.balloons()
                    # Post-analysis summary
                    _final_progress = get_analysis_progress(case_id, prep_id)
                    if _final_progress:
                        _fp_completed = _final_progress.get("completed_nodes", [])
                        _fp_skipped = _final_progress.get("skipped_nodes", [])
                        _fp_times = _final_progress.get("per_node_times", {})
                        _fp_started = _final_progress.get("started_at", "")
                        _fp_ended = _final_progress.get("completed_at", "")
                        with st.expander("Analysis Summary", expanded=True):
                            if _fp_started and _fp_ended:
                                from datetime import datetime as _dt_cls
                                try:
                                    _t0 = _dt_cls.fromisoformat(_fp_started)
                                    _t1 = _dt_cls.fromisoformat(_fp_ended)
                                    _elapsed = (_t1 - _t0).total_seconds()
                                    _regen_count = len([n for n in _fp_completed if n not in _fp_skipped])
                                    st.caption(
                                        f"Completed in {int(_elapsed // 60)}m {int(_elapsed % 60)}s — "
                                        f"{_regen_count} regenerated, {len(_fp_skipped)} cached"
                                    )
                                except Exception:
                                    pass
                            _summary_rows = []
                            try:
                                from core.nodes.graph_builder import NODE_LABELS as _NL
                            except ImportError:
                                _NL = {}
                            for _nk in _fp_completed:
                                _nl = _NL.get(_nk, _nk)
                                _nt = _fp_times.get(_nk, _fp_times.get(_nl, 0))
                                _summary_rows.append({
                                    "Module": _nl,
                                    "Status": "Cached" if _nk in _fp_skipped else "Regenerated",
                                    "Time": f"{_nt:.1f}s" if _nt else "\u2014",
                                })
                            if _summary_rows:
                                st.dataframe(_summary_rows, use_container_width=True, hide_index=True)
                else:
                    st.session_state._bg_analysis_active = False
        except ImportError:
            pass


def _render_global_search(results, nav_groups, case_mgr=None):
    """Render global search across all analysis results."""
    _search_q = st.text_input(
        "\U0001f50d Search all analysis...",
        key="_global_search",
        placeholder="Type to search across all modules...",
        label_visibility="collapsed",
    )
    if _search_q and len(_search_q) >= 2:
        _q_lower = _search_q.lower()
        _search_hits = []
        for _sk, _sv in results.items():
            if _sk.startswith("_") or _sk in (
                "raw_documents", "case_files", "case_type",
                "client_name", "prep_type", "prep_name",
            ):
                continue
            if isinstance(_sv, (list, dict)):
                _flat = json.dumps(_sv, default=str)
            else:
                _flat = str(_sv)

            if _q_lower in _flat.lower():
                _idx = _flat.lower().find(_q_lower)
                _start = max(0, _idx - 80)
                _end = min(len(_flat), _idx + len(_search_q) + 80)
                _snippet = _flat[_start:_end]
                _count = _flat.lower().count(_q_lower)
                _search_hits.append((_sk, _snippet, _count))

        if _search_hits:
            _search_hits.sort(key=lambda x: -x[2])
            with st.expander(
                f"\U0001f50d **{sum(h[2] for h in _search_hits)} matches** "
                f"across **{len(_search_hits)} sections**",
                expanded=True,
            ):
                for _sk, _snippet, _count in _search_hits:
                    st.markdown(f"**{_sk}** \u2014 {_count} match{'es' if _count > 1 else ''}")
                    st.caption(f"\u2026{_snippet}\u2026")
                    st.divider()
        else:
            st.caption(f'No results for "{_search_q}"')

        # Cross-entity search within case
        try:
            from core.search import search_in_case
            _case_search = search_in_case(
                _search_q,
                st.session_state.get("current_case_id", ""),
                case_mgr,
            )
            _s_tasks = _case_search.get("tasks", [])
            _s_activity = _case_search.get("activity", [])
            if _s_tasks or _s_activity:
                with st.expander(
                    f"\U0001f4cb {len(_s_tasks)} tasks, {len(_s_activity)} activity entries matched",
                    expanded=False,
                ):
                    if _s_tasks:
                        st.markdown("**Tasks**")
                        for _st in _s_tasks[:5]:
                            _pri_icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(
                                _st.get("priority", ""), "\u26aa"
                            )
                            st.markdown(
                                f"\u2022 {_pri_icon} **{_st.get('title', 'Task')}** \u2014 {_st.get('status', '')}"
                            )
                    if _s_activity:
                        st.markdown("**Activity**")
                        for _sa in _s_activity[:5]:
                            st.caption(
                                f"\u2022 {_sa.get('action', '')} \u2014 {_sa.get('detail', '')[:60]}"
                            )
        except Exception:
            pass


def _render_courtroom_mode(results):
    """Render the dense courtroom quick-reference mode."""
    st.markdown("### \u26a1 Courtroom Quick-Reference")

    _cm_left, _cm_right = st.columns([3, 2])

    with _cm_left:
        _witnesses = results.get("witnesses", [])
        if _witnesses and isinstance(_witnesses, list):
            st.markdown("#### \U0001f465 Witness Order")
            for _wi, _w in enumerate(_witnesses):
                if isinstance(_w, dict):
                    _wname = _w.get("name", _w.get("witness", f"Witness {_wi + 1}"))
                    _wrole = _w.get("role", _w.get("type", ""))
                    _badge = (
                        "\U0001f534"
                        if str(_wrole).lower() in ("state", "prosecution", "plaintiff", "opposing")
                        else ("\U0001f7e1" if str(_wrole).lower() in ("swing", "neutral") else "\U0001f7e2")
                    )
                    st.markdown(f"{_badge} **{_wname}** \u2014 {_wrole}")
                else:
                    st.markdown(f"\u2022 {_w}")

        st.divider()
        _cross = results.get("cross_examination", "")
        if _cross:
            st.markdown("#### \u2694\ufe0f Key Cross Questions")
            _cross_str = str(_cross) if not isinstance(_cross, str) else _cross
            for _cl in _cross_str.split("\n")[:30]:
                if _cl.strip():
                    st.markdown(_cl.strip())

        st.divider()
        _cheat = results.get("cheat_sheet", "")
        if _cheat:
            st.markdown("#### \U0001f4cb Cheat Sheet")
            st.markdown(str(_cheat)[:3000])

    with _cm_right:
        _elements = results.get("legal_elements", "")
        _charges = results.get("charges", [])
        if _elements or _charges:
            st.markdown("#### \U0001f9e9 Elements & Charges")
            if isinstance(_charges, list) and _charges:
                for _ch in _charges[:6]:
                    if isinstance(_ch, dict):
                        _ch_name = _ch.get("charge", _ch.get("name", "Unknown"))
                        st.markdown(f"**{_ch_name}**")

        st.divider()
        _timeline = results.get("timeline", "")
        if _timeline:
            st.markdown("#### \U0001f4c5 Timeline")
            _tl_str = str(_timeline) if not isinstance(_timeline, str) else _timeline
            for _tl in _tl_str.split("\n")[:20]:
                if _tl.strip():
                    st.markdown(_tl.strip())

        st.divider()
        _strategy = results.get("strategy_notes", "")
        if _strategy:
            st.markdown("#### \U0001f3af Strategy")
            st.markdown(str(_strategy)[:1200])


# Emoji-prefixed tab labels for modules that use the active_tab pattern.
# These modules dispatch content via `ctx.get("active_tab")` string matching.
_ETHICAL_TAB_LABELS = [
    "\U0001f4ca Dashboard", "\U0001f50d Smart Conflicts", "\U0001f464 Prospective Clients",
    "\U0001f4de Communication Gaps", "\U0001f3e6 Trust Account", "\U0001f4b0 Fee Agreements",
    "\U0001f512 Litigation Hold", "\U0001f4cb Withdrawal", "\U0001f441\ufe0f Supervision",
    "\U0001f4d6 Ethics Reference", "\U0001f6a8 Reporting", "\u23f0 SOL Tracker",
    "\U0001f4dd Letters", "\U0001f4ca Sentencing",
]
_CRM_TAB_LABELS = [
    "\U0001f4c7 Client Directory", "\U0001f4dd Intake Forms", "\U0001f4ca CRM Dashboard",
]
_CALENDAR_TAB_LABELS = [
    "\U0001f4c5 Calendar View", "\u2795 New Event", "\U0001f4e4 Export Calendar",
]


def _render_active_tab_module(module, tabs, tab_labels, case_id, case_mgr, results):
    """Render a module that uses the active_tab dispatch pattern.

    Iterates over the st.tabs objects and calls module.render() for each
    with the correct active_tab string.
    """
    for i, tab in enumerate(tabs):
        if i < len(tab_labels):
            with tab:
                module.render(
                    case_id=case_id, case_mgr=case_mgr,
                    results=results, active_tab=tab_labels[i],
                )


def _dispatch_to_page(
    selected_group, case_id, prep_id, case_mgr, model_provider, tabs, nav_groups
):
    """Dispatch to the correct page module based on selected group."""
    results = st.session_state.get("agent_results") or {}

    render_kwargs = dict(
        case_id=case_id,
        case_mgr=case_mgr,
        results=results,
        tabs=tabs,
        selected_group=selected_group,
        nav_groups=nav_groups,
        model_provider=model_provider,
        prep_id=prep_id,
    )

    # Strip emoji prefix from group name for matching
    _clean = selected_group.split(" ", 1)[-1] if " " in selected_group else selected_group
    # Also try exact match
    _group = selected_group

    try:
        if _clean in ("Core Analysis",) or _group == "Core Analysis":
            from ui.pages import core_analysis_ui
            core_analysis_ui.render(**render_kwargs)

        elif _clean in ("Evidence & Facts",) or _group == "Evidence & Facts":
            from ui.pages import evidence_ui
            evidence_ui.render(**render_kwargs)

        elif _clean in ("Witnesses & Exam",) or _group == "Witnesses & Exam":
            from ui.pages import witnesses_ui
            witnesses_ui.render(**render_kwargs)

        elif _clean in ("Strategy & Jury",) or _group == "Strategy & Jury":
            from ui.pages import strategy_ui
            strategy_ui.render(**render_kwargs)

        elif _clean in ("Research & Draft",) or _group == "Research & Draft":
            from ui.pages import research_ui
            research_ui.render(**render_kwargs)

        elif _clean in ("Tools",) or _group == "Tools":
            # If a file is open for viewing, show doc viewer first
            if st.session_state.get("_viewing_file"):
                from ui.pages import doc_viewer_ui
                doc_viewer_ui.render(case_id=case_id, case_mgr=case_mgr, model_provider=model_provider)
                st.divider()
            from ui.pages import tools_ui
            tools_ui.render(**render_kwargs)

        elif _clean in ("Ethical Compliance",) or _group == "Ethical Compliance":
            from ui.pages import ethical_compliance_ui
            _render_active_tab_module(
                ethical_compliance_ui, tabs, _ETHICAL_TAB_LABELS,
                case_id, case_mgr, results,
            )

        elif _clean in ("Billing",) or _group == "Billing":
            from ui.pages import billing_ui
            billing_ui.render(**render_kwargs)

        elif _clean in ("Client CRM",) or _group == "Client CRM":
            from ui.pages import crm_ui
            _render_active_tab_module(
                crm_ui, tabs, _CRM_TAB_LABELS,
                case_id, case_mgr, results,
            )

        elif _clean in ("Calendar",) or _group == "Calendar":
            from ui.pages import calendar_ui
            _render_active_tab_module(
                calendar_ui, tabs, _CALENDAR_TAB_LABELS,
                case_id, case_mgr, results,
            )

        elif _clean in ("E-Signature",) or _group == "E-Signature":
            from ui.pages import esign_ui
            esign_ui.render(**render_kwargs)

        elif _clean in ("User Admin",) or _group == "User Admin":
            from ui.pages import user_admin_ui
            user_admin_ui.render(**render_kwargs)

        elif _clean in ("Activity",) or _group == "Activity":
            from ui.pages import activity_ui
            activity_ui.render(**render_kwargs)

        elif _clean in ("Tasks",) or _group == "Tasks":
            from ui.pages import tasks_ui
            tasks_ui.render(**render_kwargs)

        elif _clean in ("Email",) or _group == "Email":
            from ui.pages import email_ui
            email_ui.render(**render_kwargs)

        else:
            st.info(f"Page '{selected_group}' is not yet implemented.")

    except ImportError as exc:
        st.warning(f"Page module for '{selected_group}' not found: {exc}")
        logger.warning("Missing page module for %s: %s", selected_group, exc)
    except Exception as exc:
        st.error(f"Error rendering '{selected_group}': {exc}")
        logger.exception("Error rendering page %s", selected_group)
