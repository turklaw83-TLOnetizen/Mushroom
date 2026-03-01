# ---- Landing Dashboard ----------------------------------------------------
# Renders the firm-level dashboard when no case is selected.
# Ported from original app.py lines 1493-2153.

import logging
import os
from datetime import datetime

import streamlit as st

from ui.shared import (
    get_case_manager,
    get_user_manager,
    load_case,
    PROJECT_ROOT,
)
from core.readiness import compute_readiness_score

logger = logging.getLogger(__name__)


def render_dashboard():
    """Render the full landing dashboard (no case selected)."""
    case_mgr = get_case_manager()

    st.markdown('<h1 class="hero-title">AllRise Beta</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-subtitle">Legal Intelligence Suite</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hero-divider"></div>', unsafe_allow_html=True)

    # ===== DASHBOARD METRICS (cached) =====
    _show_archived = st.checkbox(
        "Show archived cases", value=False, key="_show_archived"
    )

    # Cache dashboard metrics in session state to avoid repeated I/O.
    # Invalidate when _dash_cache_ver changes (bumped on case create/delete/modify).
    _dash_ver = st.session_state.get("_dash_cache_ver", 0)
    _cached = st.session_state.get("_dash_metrics_cache")
    if _cached is None or _cached.get("_ver") != _dash_ver:
        all_cases_raw = case_mgr.list_cases(include_archived=True)
        # Phase-aware categorization (backward compatible)
        _active = []
        _closed = []
        _archived = []
        for c in all_cases_raw:
            _ph = c.get("phase") or c.get("status", "active")
            if _ph == "archived":
                _archived.append(c)
            elif _ph == "closed":
                _closed.append(c)
            else:
                _active.append(c)
        _total_docs = 0
        _total_preps = 0
        _analyzed_count = 0
        _per_case = {}  # per-case precomputed data for the table
        for c in all_cases_raw:
            cid = c["id"]
            c_files = case_mgr.get_case_files(cid)
            c_preps = case_mgr.list_preparations(cid)
            n_files = len(c_files) if c_files else 0
            n_preps = len(c_preps) if c_preps else 0
            _ph = c.get("phase") or c.get("status", "active")
            if _ph != "archived":
                _total_docs += n_files
                _total_preps += n_preps
                if c_preps:
                    _analyzed_count += 1
            _per_case[cid] = {
                "files": n_files, "preps": c_preps, "n_preps": n_preps,
            }
        _cached = {
            "_ver": _dash_ver,
            "all_cases": all_cases_raw,
            "active_cases": _active,
            "closed_cases": _closed,
            "archived_cases": _archived,
            "total_docs": _total_docs,
            "total_preps": _total_preps,
            "analyzed_count": _analyzed_count,
            "per_case": _per_case,
        }
        st.session_state["_dash_metrics_cache"] = _cached

        # Auto-archive closed cases past 21-day limit
        try:
            _auto_archived = case_mgr.check_auto_archive_closed_cases()
            if _auto_archived:
                st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
        except Exception as e:
            logger.warning("Auto-archive check failed: %s", e)

    all_cases_for_metrics = _cached["all_cases"]
    active_cases = _cached["active_cases"]
    closed_cases = _cached.get("closed_cases", [])
    archived_cases = _cached["archived_cases"]
    total_docs = _cached["total_docs"]
    total_preps = _cached["total_preps"]
    analyzed_count = _cached["analyzed_count"]

    _stat_data = [
        ("\U0001f4c2", "Active", len(active_cases)),
        ("\U0001f7e1", "Closed", len(closed_cases)),
        ("\U0001f4e6", "Archived", len(archived_cases)),
        ("\U0001f4cb", "Preps", total_preps),
        ("\u2705", "Analyzed", f"{analyzed_count}/{len(active_cases) + len(closed_cases)}"),
    ]
    _stat_cols = st.columns(5)
    for _si, (_s_icon, _s_label, _s_val) in enumerate(_stat_data):
        with _stat_cols[_si]:
            st.markdown(
                f"""
                <div class="glass-stat-card" style="animation-delay: {_si * 0.08}s">
                    <div class="stat-icon">{_s_icon}</div>
                    <div class="stat-value">{_s_val}</div>
                    <div class="stat-label">{_s_label}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

    # ===== BILLING METRICS ROW =====
    try:
        from core.billing import get_firm_billing_stats

        _bill_stats = get_firm_billing_stats(case_mgr)
        st.divider()
        st.subheader("\U0001f4bc Billing Overview")
        _bc1, _bc2, _bc3, _bc4, _bc5 = st.columns(5)
        _bc1.metric(
            "\U0001f4b0 Unbilled Hours",
            f"{_bill_stats.get('unbilled_hours', 0):.1f}h",
        )
        _bc2.metric(
            "\U0001f4b5 Unbilled Amount",
            f"${_bill_stats.get('unbilled_amount', 0):,.0f}",
        )
        _bc3.metric(
            "\U0001f4c4 Outstanding Invoices",
            _bill_stats.get("outstanding_invoices", 0),
        )
        _bc4.metric(
            "\U0001f4c8 Monthly Revenue",
            f"${_bill_stats.get('monthly_revenue', 0):,.0f}",
        )
        _bc5_overdue = _bill_stats.get("overdue_count", 0)
        if _bc5_overdue > 0:
            _bc5.metric(
                "\U0001f534 Overdue",
                _bc5_overdue,
                delta=f"-${_bill_stats.get('overdue_total', 0):,.0f}",
                delta_color="inverse",
            )
        else:
            _bc5.metric("\u2705 Overdue", 0)
    except ImportError:
        pass  # Billing module not installed
    except Exception as e:
        logger.warning("Billing metrics failed: %s", e)
        st.caption("\u26a0\ufe0f Billing data unavailable")

    # ===== CRM METRICS + CLIENT DIRECTORY =====
    try:
        from core.crm import get_crm_stats, load_clients, search_clients, get_cases_for_client
        from core.crm import update_client, delete_client, add_client

        _crm_dash = get_crm_stats()
        if _crm_dash.get("total_clients", 0) > 0:
            st.divider()
            st.subheader("\U0001f465 Client CRM")
            _cc1, _cc2, _cc3, _cc4 = st.columns(4)
            _cc1.metric("\U0001f465 Total Clients", _crm_dash.get("total_clients", 0))
            _cc2.metric("\U0001f7e2 Active", _crm_dash.get("active", 0))
            _cc3.metric("\U0001f534 Former", _crm_dash.get("former", 0))
            _cc4.metric("\U0001f7e1 Prospective", _crm_dash.get("prospective", 0))

            # Client Directory (accessible from dashboard — no case needed)
            with st.expander("\U0001f4c7 Client Directory", expanded=False):
                # Search + Add
                _crm_s_col, _crm_a_col = st.columns([3, 1])
                with _crm_s_col:
                    _crm_q = st.text_input(
                        "\U0001f50d Search clients...", key="_dash_crm_search",
                        placeholder="Name, email, phone, or tag...",
                    )
                with _crm_a_col:
                    st.markdown("")
                    _crm_show_add = st.button(
                        "\u2795 Add Client", key="_dash_crm_add",
                        type="primary", use_container_width=True,
                    )

                # Add Client Form
                if _crm_show_add or st.session_state.get("_dash_crm_adding"):
                    st.session_state["_dash_crm_adding"] = True
                    with st.form("dash_crm_add_client", clear_on_submit=True):
                        _dac1, _dac2 = st.columns(2)
                        with _dac1:
                            _dac_first = st.text_input("First Name *", key="_dac_first_name")
                            _dac_last = st.text_input("Last Name *", key="_dac_last_name")
                            _dac_email = st.text_input("Email", key="_dac_email")
                            _dac_phone = st.text_input("Phone", key="_dac_phone")
                        with _dac2:
                            _dac_type = st.selectbox(
                                "Client Type",
                                ["Individual", "Organization", "Government",
                                 "Business", "Trust/Estate"],
                                key="_dac_type",
                            )
                            _dac_status = st.selectbox(
                                "Status",
                                ["active", "prospective", "former", "declined"],
                                key="_dac_status",
                            )
                            _dac_referral = st.text_input("Referral Source", key="_dac_referral")
                        _dac_notes = st.text_area("Notes", key="_dac_notes", height=68)
                        _dac_submit = st.form_submit_button("\U0001f4be Save Client", type="primary")
                        if _dac_submit and (_dac_first or _dac_last):
                            add_client(
                                first_name=_dac_first, last_name=_dac_last,
                                client_type=_dac_type,
                                email=_dac_email, phone=_dac_phone,
                                notes=_dac_notes, referral_source=_dac_referral,
                                intake_status=_dac_status,
                            )
                            st.session_state["_dash_crm_adding"] = False
                            _dac_display = f"{_dac_first} {_dac_last}".strip()
                            st.toast(f"\u2705 Client added: {_dac_display}")
                            st.rerun()

                # Client List
                _all_clients = search_clients(_crm_q) if _crm_q else load_clients()

                # Status filter
                _crm_filter = st.selectbox(
                    "Filter by Status",
                    ["All", "Active", "Prospective", "Former", "Declined"],
                    key="_dash_crm_filter",
                )
                if _crm_filter != "All":
                    _all_clients = [
                        c for c in _all_clients
                        if c.get("intake_status", "active") == _crm_filter.lower()
                    ]

                if _all_clients:
                    st.caption(f"Showing {len(_all_clients)} client{'s' if len(_all_clients) != 1 else ''}")
                    for _ci, _cli in enumerate(sorted(_all_clients, key=lambda x: x.get("name", "").lower())):
                        _cli_name = _cli.get("name", "Unknown")
                        _cli_type = _cli.get("client_type", "Individual")
                        _cli_status = _cli.get("intake_status", "active")
                        _status_icon = {
                            "active": "\U0001f7e2", "former": "\U0001f534",
                            "prospective": "\U0001f7e1", "declined": "\u26aa",
                        }.get(_cli_status, "\u26aa")
                        _cli_email = _cli.get("email", "")
                        _cli_phone = _cli.get("phone", "")
                        _contact_parts = []
                        if _cli_email:
                            _contact_parts.append(_cli_email)
                        if _cli_phone:
                            _contact_parts.append(_cli_phone)
                        _contact_str = " | ".join(_contact_parts)
                        _tags = _cli.get("tags", [])
                        _tag_str = " ".join(f"`{t}`" for t in _tags) if _tags else ""

                        with st.expander(
                            f"{_status_icon} **{_cli_name}** ({_cli_type})"
                            + (f" | {_contact_str}" if _contact_str else "")
                        ):
                            _dc1, _dc2 = st.columns(2)
                            with _dc1:
                                st.markdown(f"**Name:** {_cli_name}")
                                st.markdown(f"**Type:** {_cli_type}")
                                st.markdown(f"**Email:** {_cli_email or 'N/A'}")
                                st.markdown(f"**Phone:** {_cli_phone or 'N/A'}")
                                st.markdown(f"**DOB:** {_cli.get('date_of_birth', 'N/A')}")
                            with _dc2:
                                st.markdown(f"**Address:** {_cli.get('address', 'N/A')}")
                                st.markdown(f"**Employer:** {_cli.get('employer', 'N/A')}")
                                st.markdown(f"**Referral:** {_cli.get('referral_source', 'N/A')}")
                                st.markdown(f"**Status:** {_status_icon} {_cli_status.title()}")
                                if _tag_str:
                                    st.markdown(f"**Tags:** {_tag_str}")
                            if _cli.get("notes"):
                                st.markdown(f"**Notes:** {_cli['notes']}")

                            # Linked cases — with Open Case buttons
                            _linked_ids = get_cases_for_client(_cli.get("id", ""))
                            if _linked_ids:
                                st.markdown(f"**Linked Cases ({len(_linked_ids)}):**")
                                for _lc_id in _linked_ids:
                                    _lc_name = case_mgr.get_case_name(_lc_id) if case_mgr else _lc_id
                                    _lc_col1, _lc_col2 = st.columns([3, 1])
                                    with _lc_col1:
                                        st.markdown(f"\U0001f4c1 {_lc_name}")
                                    with _lc_col2:
                                        if st.button(
                                            "Open", key=f"_dash_open_case_{_cli.get('id')}_{_lc_id}",
                                            use_container_width=True,
                                        ):
                                            st.session_state.current_case_id = _lc_id
                                            st.rerun()
                            else:
                                st.caption("No linked cases")

                            # Actions
                            st.markdown("---")
                            _ab1, _ab2 = st.columns(2)
                            with _ab1:
                                _new_status = "former" if _cli_status == "active" else "active"
                                _toggle_icon = "\U0001f534" if _cli_status == "active" else "\U0001f7e2"
                                if st.button(
                                    f"{_toggle_icon} Mark {_new_status.title()}",
                                    key=f"_dash_crm_toggle_{_cli.get('id')}",
                                    use_container_width=True,
                                ):
                                    update_client(_cli.get("id", ""), {"intake_status": _new_status})
                                    st.rerun()
                            with _ab2:
                                if st.button(
                                    "\U0001f5d1\ufe0f Delete",
                                    key=f"_dash_crm_del_{_cli.get('id')}",
                                    use_container_width=True,
                                ):
                                    delete_client(_cli.get("id", ""))
                                    st.toast(f"Deleted {_cli_name}")
                                    st.rerun()

                elif _crm_q:
                    st.info(f"No clients matching '{_crm_q}'.")
                else:
                    st.info("No clients yet. Click **Add Client** to create your first client record.")
        else:
            # No clients yet — show add button
            st.divider()
            st.subheader("\U0001f465 Client CRM")
            st.info("No clients yet. Add your first client to get started.")
            if st.button("\u2795 Add First Client", key="_dash_first_client"):
                st.session_state["_dash_crm_adding"] = True
                st.rerun()
    except ImportError:
        pass  # CRM module not installed
    except Exception as e:
        logger.warning("CRM section failed: %s", e)
        st.caption("\u26a0\ufe0f Client directory unavailable")

    # ===== CALENDAR METRICS ROW =====
    try:
        from core.calendar_events import get_calendar_stats

        _cal_dash = get_calendar_stats()
        if _cal_dash.get("total_events", 0) > 0:
            st.divider()
            st.subheader("\U0001f4c5 Calendar")
            _ce1, _ce2, _ce3, _ce4 = st.columns(4)
            _ce1.metric(
                "\U0001f4c5 Total Events", _cal_dash.get("total_events", 0)
            )
            _ce2.metric("\U0001f4c6 Upcoming", _cal_dash.get("upcoming", 0))
            _ce3.metric("\U0001f4c5 This Week", _cal_dash.get("this_week", 0))
            _past = _cal_dash.get("past_due", 0)
            if _past > 0:
                _ce4.metric("\U0001f534 Past Due", _past)
            else:
                _ce4.metric("\u2705 Past Due", 0)
    except ImportError:
        pass  # Calendar module not installed
    except Exception as e:
        logger.warning("Calendar metrics failed: %s", e)
        st.caption("\u26a0\ufe0f Calendar data unavailable")

    # ===== DEADLINE URGENCY BOARD =====
    try:
        all_deadlines = case_mgr.get_all_deadlines()
        upcoming = [d for d in all_deadlines if d.get("days_remaining", 999) <= 14]
        if upcoming:
            st.divider()
            st.subheader("\u23f0 Upcoming Deadlines")
            for dl in upcoming:
                days = dl.get("days_remaining", 999)
                label = dl.get("label", "Untitled")
                dl_date = dl.get("date", "")
                case_name = dl.get("case_name", "")
                category = dl.get("category", "")

                if days < 0:
                    st.error(
                        f"\U0001f6a8 **OVERDUE** ({abs(days)}d) \u2014 {label} | {case_name} | {dl_date} | {category}"
                    )
                elif days == 0:
                    st.error(
                        f"\U0001f534 **TODAY** \u2014 {label} | {case_name} | {dl_date} | {category}"
                    )
                elif days == 1:
                    st.warning(
                        f"\U0001f7e0 **TOMORROW** \u2014 {label} | {case_name} | {dl_date} | {category}"
                    )
                elif days <= 3:
                    st.warning(
                        f"\U0001f7e1 **{days} days** \u2014 {label} | {case_name} | {dl_date} | {category}"
                    )
                else:
                    st.info(
                        f"\U0001f4c5 {days} days \u2014 {label} | {case_name} | {dl_date} | {category}"
                    )
    except Exception as e:
        logger.warning("Deadline urgency board failed: %s", e)
        st.caption("\u26a0\ufe0f Deadline data unavailable")

    # ===== TEAM WORKLOAD =====
    try:
        user_mgr = get_user_manager()
        _team_users = user_mgr.list_users()
        if _team_users and len(_team_users) > 1:
            st.divider()
            st.subheader("\U0001f3d7\ufe0f Team Workload")
            _tw_cols = st.columns(min(len(_team_users), 6))
            for _tw_i, _tw_u in enumerate(_team_users[:6]):
                _tw_name = _tw_u.get("name", "?")
                _tw_initials = _tw_u.get("initials", "?")
                _tw_role = _tw_u.get("role", "attorney")
                _tw_case_ids = _tw_u.get("assigned_case_ids", [])
                _tw_active = (
                    len(
                        [c for c in active_cases if c.get("id") in _tw_case_ids]
                    )
                    if _tw_case_ids
                    else 0
                )
                with _tw_cols[_tw_i % len(_tw_cols)]:
                    st.metric(
                        f"{_tw_initials} \u2014 {_tw_name}",
                        f"{_tw_active} cases",
                        help=_tw_role.title(),
                    )
    except Exception as e:
        logger.warning("Team workload section failed: %s", e)
        st.caption("\u26a0\ufe0f Team workload unavailable")

    # ===== CASE OVERVIEW DASHBOARD (sortable table) =====
    _display_cases = active_cases if not _show_archived else all_cases_for_metrics

    st.divider()
    _overview_left, _overview_right = st.columns([3, 1])
    with _overview_left:
        st.subheader("\U0001f4ca Case Overview Dashboard")
    with _overview_right:
        st.markdown("")  # spacing
        _show_new_case = st.button("\u2795 New Case", type="primary", use_container_width=True, key="_dash_new_case_btn")

    # Inline New Case form
    if _show_new_case or st.session_state.get("_dash_new_case_open"):
        st.session_state["_dash_new_case_open"] = True
        with st.expander("\u2795 Create New Case", expanded=True):
            with st.form("_new_case_form", clear_on_submit=True):
                _nc_col1, _nc_col2 = st.columns(2)
                with _nc_col1:
                    new_name = st.text_input("Case Name *", key="_nc_name")
                    new_type = st.selectbox(
                        "Case Type",
                        ["criminal", "criminal-juvenile", "civil-plaintiff",
                         "civil-defendant", "civil-juvenile"],
                        key="_nc_type",
                    )
                with _nc_col2:
                    new_client = st.text_input("Client Name (optional)", key="_nc_client")
                    new_desc = st.text_input("Description (optional)", key="_nc_desc")
                submitted = st.form_submit_button(
                    "Create Case", type="primary", use_container_width=True,
                )
                if submitted:
                    if new_name.strip():
                        st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        st.session_state["_dash_new_case_open"] = False
                        new_id = case_mgr.create_case(
                            new_name.strip(),
                            case_type=new_type,
                            client_name=new_client.strip(),
                            description=new_desc.strip(),
                        )
                        load_case(new_id)
                    else:
                        st.warning("Please enter a case name.")

    if _display_cases:

        # Search & Filter bar
        _filter_col1, _filter_col2, _filter_col3 = st.columns([3, 1.5, 1.5])
        with _filter_col1:
            _search_q = st.text_input(
                "\U0001f50d Search cases",
                placeholder="Search by case name, client, or description...",
                key="_dash_search",
                label_visibility="collapsed",
            )
        with _filter_col2:
            _type_filter = st.selectbox(
                "Case type",
                ["All Types", "criminal", "criminal-juvenile",
                 "civil-plaintiff", "civil-defendant", "civil-juvenile"],
                key="_dash_type_filter",
            )
        with _filter_col3:
            _phase_filter = st.selectbox(
                "Phase",
                ["All Phases", "Active", "Closed", "Archived"],
                key="_dash_phase_filter",
            )

        # Apply filters
        _filtered_cases = list(_display_cases)
        if _search_q.strip():
            _sq = _search_q.strip().lower()
            _filtered_cases = [
                c for c in _filtered_cases
                if _sq in c.get("name", "").lower()
                or _sq in c.get("client_name", "").lower()
                or _sq in c.get("description", "").lower()
                or _sq in c.get("id", "").lower()
            ]
        if _type_filter != "All Types":
            _filtered_cases = [
                c for c in _filtered_cases
                if c.get("case_type", "").lower() == _type_filter
            ]
        if _phase_filter != "All Phases":
            _pf = _phase_filter.lower()
            _filtered_cases = [
                c for c in _filtered_cases
                if (c.get("phase") or c.get("status", "active")).lower() == _pf
            ]

        # Cross-entity search results
        if _search_q.strip() and len(_search_q.strip()) >= 2:
            try:
                from core.search import global_search
                _cross_results = global_search(_search_q.strip(), case_mgr)
                _cross_clients = _cross_results.get("clients", [])
                _cross_tasks = _cross_results.get("tasks", [])
                if _cross_clients or _cross_tasks:
                    with st.expander(
                        f"\U0001f50d Cross-entity results: {len(_cross_clients)} clients, {len(_cross_tasks)} tasks",
                        expanded=True,
                    ):
                        if _cross_clients:
                            st.markdown("**Clients**")
                            for _cl in _cross_clients[:5]:
                                _cl_name = _cl.get("name", "Unknown")
                                _cl_email = _cl.get("email", "")
                                _cl_status = _cl.get("status", "")
                                st.markdown(
                                    f"\u2022 **{_cl_name}** {f'({_cl_email})' if _cl_email else ''} "
                                    f"{'\u2014 ' + _cl_status if _cl_status else ''}"
                                )
                            if len(_cross_clients) > 5:
                                st.caption(f"... and {len(_cross_clients) - 5} more")
                        if _cross_tasks:
                            st.markdown("**Tasks**")
                            for _tk in _cross_tasks[:5]:
                                _tk_title = _tk.get("title", "Task")
                                _tk_case = _tk.get("case_name", "")
                                _tk_status = _tk.get("status", "")
                                _pri_icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(_tk.get("priority", ""), "\u26aa")
                                st.markdown(
                                    f"\u2022 {_pri_icon} **{_tk_title}** \u2014 {_tk_case} ({_tk_status})"
                                )
                            if len(_cross_tasks) > 5:
                                st.caption(f"... and {len(_cross_tasks) - 5} more")
            except ImportError:
                pass  # Search module not installed
            except Exception as e:
                logger.warning("Cross-entity search failed: %s", e)

        try:
            all_deadlines = case_mgr.get_all_deadlines()
        except Exception as e:
            logger.warning("Failed to load deadlines: %s", e)
            all_deadlines = []

        # Batch-load calendar events for "Next Event" column
        from datetime import date as _date_cls
        try:
            from core.calendar_events import load_events as _load_all_events
            _all_events = _load_all_events()
            _today_str = str(_date_cls.today())
            _events_by_case = {}
            for _ev in _all_events:
                _ev_case = _ev.get("case_id", "")
                if not _ev_case:
                    continue
                if _ev.get("status") != "scheduled":
                    continue
                if _ev.get("date", "") < _today_str:
                    continue
                _events_by_case.setdefault(_ev_case, []).append(_ev)
            for _ek in _events_by_case:
                _events_by_case[_ek].sort(key=lambda e: (e.get("date", ""), e.get("time", "")))
        except ImportError:
            _events_by_case = {}
        except Exception as e:
            logger.warning("Failed to load calendar events: %s", e)
            _events_by_case = {}

        _dash_rows = []
        _per_case = _cached["per_case"]
        for _ac in _filtered_cases:
            _ac_id = _ac["id"]
            _ac_name = _ac.get("name", _ac_id)
            # Phase-aware display
            _ac_phase = _ac.get("phase") or _ac.get("status", "active")
            _ac_sub_phase = _ac.get("sub_phase", "")
            _ac_purged = _ac.get("purged", False)
            if _ac_phase == "active" and _ac_sub_phase:
                _ac_phase_display = f"Active — {_ac_sub_phase}"
            elif _ac_phase == "active":
                _ac_phase_display = "Active"
            elif _ac_phase == "closed":
                _ac_phase_display = "Closed"
            elif _ac_phase == "archived":
                _ac_phase_display = "Archived" + (" ✓" if _ac_purged else "")
            else:
                _ac_phase_display = _ac_phase.title()

            _pc = _per_case.get(_ac_id, {})
            _ac_preps = _pc.get("preps", [])
            _ac_readiness = "\u2014"
            _ac_prep_count = _pc.get("n_preps", 0)
            _ac_doc_count = _pc.get("files", 0)
            _ac_modules_done = 0
            _ac_modules_total = 15
            _ac_next_deadline = "\u2014"
            _ac_score_num = -1
            _ac_modules_num = 0
            _ac_deadline_days = 9999

            if _ac_preps:
                _first_prep = _ac_preps[0]
                _fp_id = _first_prep.get("id", "")
                _fp_type = _first_prep.get("type", "trial")
                try:
                    _fp_state = case_mgr.load_prep_state(_ac_id, _fp_id)
                    if _fp_state:
                        _fp_score, _fp_grade, _fp_bd = compute_readiness_score(
                            _fp_state
                        )
                        _ac_readiness = f"{_fp_score} ({_fp_grade})"
                        _ac_score_num = _fp_score
                        _ac_modules_done = sum(
                            1 for v in _fp_bd.values() if v
                        )
                        _ac_modules_total = len(_fp_bd)
                        _ac_modules_num = _ac_modules_done
                except Exception as e:
                    logger.debug("Readiness score failed for case %s: %s", _ac_id, e)

            _case_deadlines = [
                d
                for d in all_deadlines
                if d.get("case_id") == _ac_id and d.get("days_remaining", 999) >= 0
            ]
            if _case_deadlines:
                _next = _case_deadlines[0]
                _ac_next_deadline = (
                    f"{_next.get('label', '')} ({_next.get('days_remaining', '?')}d)"
                )
                try:
                    _ac_deadline_days = int(_next.get("days_remaining", 9999))
                except (ValueError, TypeError):
                    pass

            # Next Event from calendar
            _ac_next_event = "\u2014"
            _ac_event_days = 9999
            _case_events = _events_by_case.get(_ac_id, [])
            if _case_events:
                _next_evt = _case_events[0]
                try:
                    _evt_date = datetime.strptime(_next_evt["date"], "%Y-%m-%d")
                    _evt_label = _evt_date.strftime("%b %d")
                    _evt_title = _next_evt.get("title", "Event")[:20]
                    _ac_next_event = f"{_evt_label} \u2014 {_evt_title}"
                    _ac_event_days = (_evt_date.date() - _date_cls.today()).days
                except (ValueError, KeyError):
                    _ac_next_event = _next_evt.get("title", "Event")[:25]

            try:
                _score_val = int(_ac_score_num)
                if _score_val >= 80:
                    _badge = "\U0001f7e2"
                elif _score_val >= 50:
                    _badge = "\U0001f7e1"
                else:
                    _badge = "\U0001f534"
            except (ValueError, TypeError):
                _badge = "\u26aa"

            try:
                _ac_pinned = case_mgr.is_pinned(_ac_id)
            except Exception as e:
                logger.debug("Pin status check failed for case %s: %s", _ac_id, e)
                _ac_pinned = False

            _dash_rows.append(
                {
                    "_case_id": _ac_id,
                    "_score_num": _ac_score_num,
                    "_modules_num": _ac_modules_num,
                    "_deadline_days": _ac_deadline_days,
                    "_event_days": _ac_event_days,
                    "_pinned": _ac_pinned,
                    "_phase": _ac_phase,
                    "_sub_phase": _ac_sub_phase,
                    "_case_type": _ac.get("case_type", "criminal"),
                    "": _badge,
                    "Case": _ac_name,
                    "Readiness": _ac_readiness,
                    "Modules": f"{_ac_modules_done}/{_ac_modules_total}",
                    "Preps": _ac_prep_count,
                    "Docs": _ac_doc_count,
                    "Next Deadline": _ac_next_deadline,
                    "Next Event": _ac_next_event,
                    "Phase": _ac_phase_display,
                }
            )

        if not _dash_rows and (_search_q.strip() or _type_filter != "All Types" or _phase_filter != "All Phases"):
            st.info(f"No cases match your search. Try broadening your filters.")

        if _dash_rows:
            # Sort Controls
            _sort_col1, _sort_col2, _sort_col3, _sort_col4 = st.columns([2, 2, 1, 1])
            _sortable_columns = {
                "Case Name": "Case",
                "Readiness": "_score_num",
                "Modules": "_modules_num",
                "Preps": "Preps",
                "Docs": "Docs",
                "Next Deadline": "_deadline_days",
                "Next Event": "_event_days",
                "Phase": "Phase",
            }
            with _sort_col1:
                _sort_by_label = st.selectbox(
                    "Sort by",
                    options=list(_sortable_columns.keys()),
                    index=0,
                    key="_dash_sort_col",
                )
            with _sort_col2:
                _sort_dir = st.selectbox(
                    "Direction",
                    options=["Ascending \u2191", "Descending \u2193"],
                    index=0,
                    key="_dash_sort_dir",
                )
            _sort_key = _sortable_columns[_sort_by_label]
            _reverse = "Descending" in _sort_dir

            try:
                _dash_rows.sort(
                    key=lambda r: r.get(_sort_key, ""),
                    reverse=_reverse,
                )
            except TypeError:
                pass

            # Pin to top
            _dash_rows.sort(key=lambda r: (0 if r.get("_pinned") else 1))

            # Pagination
            with _sort_col3:
                _page_size = st.selectbox(
                    "Per page", [10, 25, 50], index=0, key="_dash_page_size"
                )
            _total_pages = max(1, (len(_dash_rows) + _page_size - 1) // _page_size)
            with _sort_col4:
                _page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=_total_pages,
                    value=1,
                    key="_dash_page",
                )
            _start = (_page - 1) * _page_size
            _page_rows = _dash_rows[_start : _start + _page_size]

            # Column headers
            _col_widths = [0.3, 0.3, 1.5, 0.7, 0.7, 0.5, 0.5, 1.0, 1.0, 1.2, 0.7]
            _hdr_cols = st.columns(_col_widths)
            _hdr_labels = ["\u2b50", "", "Case", "Readiness", "Modules", "Preps", "Docs", "Next Deadline", "Next Event", "Phase", ""]
            for _hi, _hl in enumerate(_hdr_labels):
                if _hl:
                    _hdr_cols[_hi].markdown(f"**{_hl}**")
            st.markdown("<hr style='margin:2px 0 6px 0; opacity:0.3;'>", unsafe_allow_html=True)

            # Render table rows
            for _row in _page_rows:
                _cols = st.columns(_col_widths)
                # Pin/unpin button
                with _cols[0]:
                    _pin_icon = "\u2b50" if _row.get("_pinned") else "\u2606"
                    if st.button(_pin_icon, key=f"_pin_{_row['_case_id']}", help="Pin/Unpin case"):
                        try:
                            if _row.get("_pinned"):
                                case_mgr.unpin_case(_row["_case_id"])
                            else:
                                case_mgr.pin_case(_row["_case_id"])
                            st.session_state.pop("_dash_metrics_cache", None)
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                        except Exception as e:
                            logger.warning("Pin/unpin failed for case %s: %s", _row["_case_id"], e)
                            st.toast(f"Failed to update pin: {e}", icon="\u26a0\ufe0f")
                        st.rerun()
                _cols[1].markdown(_row[""])
                _cols[2].markdown(f"**{_row['Case']}**")
                _cols[3].markdown(_row["Readiness"])
                _cols[4].markdown(_row["Modules"])
                _cols[5].markdown(str(_row["Preps"]))
                _cols[6].markdown(str(_row["Docs"]))
                _cols[7].caption(_row["Next Deadline"])
                _cols[8].caption(_row.get("Next Event", "\u2014"))
                # Inline sub-phase editing for active cases
                with _cols[9]:
                    if _row.get("_phase") == "active":
                        _row_ctype = _row.get("_case_type", "criminal")
                        _row_sub = _row.get("_sub_phase", "")
                        _sub_cfg = _cached.get("_phase_config", {})
                        if not _sub_cfg:
                            try:
                                _sub_cfg = case_mgr.get_phase_config()
                                _cached["_phase_config"] = _sub_cfg
                            except Exception as e:
                                logger.warning("Phase config load failed: %s", e)
                                _sub_cfg = {}
                        _sub_opts = _sub_cfg.get(_row_ctype, _sub_cfg.get("criminal", []))
                        _sel_opts = ["—"] + _sub_opts
                        _cur_idx = _sel_opts.index(_row_sub) if _row_sub in _sel_opts else 0
                        _new_sub = st.selectbox(
                            "sub",
                            _sel_opts,
                            index=_cur_idx,
                            key=f"_dsub_{_row['_case_id']}",
                            label_visibility="collapsed",
                        )
                        _actual_sub = _new_sub if _new_sub != "—" else ""
                        if _actual_sub != _row_sub:
                            case_mgr.set_sub_phase(_row["_case_id"], _actual_sub)
                            st.session_state["_dash_cache_ver"] = st.session_state.get("_dash_cache_ver", 0) + 1
                            st.rerun()
                    else:
                        st.caption(_row["Phase"])
                with _cols[10]:
                    if st.button(
                        "Open", key=f"_open_{_row['_case_id']}", type="primary"
                    ):
                        load_case(_row["_case_id"])

            _filter_note = ""
            if _search_q.strip() or _type_filter != "All Types" or _phase_filter != "All Phases":
                _filter_note = f" (filtered from {len(_display_cases)})"
            st.caption(
                f"Page {_page}/{_total_pages} \u2014 {len(_dash_rows)} cases{_filter_note}"
            )

    # ===== MASTER CALENDAR =====
    st.divider()
    try:
        from ui.pages.master_calendar_ui import render_master_calendar

        render_master_calendar(case_mgr)
    except ImportError:
        pass
    except Exception as exc:
        logger.exception("Error rendering master calendar: %s", exc)
