"""Client CRM UI module — ported from legacy ui_modules/crm_ui.py."""
import logging
import streamlit as st

from core import crm

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render all tabs for the Client CRM nav group."""
    active_tab = ctx.get("active_tab", "")

    # -- 1. Client Directory ----------------------------------------------------
    if active_tab == "\U0001f4c7 Client Directory":
        st.markdown("## \U0001f4c7 Client Directory")
        st.caption("Manage clients, contacts, and case associations.")

        # -- Search & Filter --
        _crm_search_col, _crm_add_col = st.columns([3, 1])
        with _crm_search_col:
            _crm_search = st.text_input("\U0001f50d Search clients...", key="_crm_search", placeholder="Name, email, phone, or tag...")
        with _crm_add_col:
            st.markdown("")
            _crm_show_add = st.button("\u2795 Add Client", key="_crm_add_btn", type="primary", use_container_width=True)

        # -- Add Client Form --
        if _crm_show_add or st.session_state.get("_crm_adding"):
            st.session_state["_crm_adding"] = True
            with st.expander("\u2795 Add New Client", expanded=True):
                with st.form("crm_add_client", clear_on_submit=True):
                    _ac1, _ac2 = st.columns(2)
                    with _ac1:
                        _ac_first = st.text_input("First Name *", key="_ac_first_name")
                        _ac_last = st.text_input("Last Name *", key="_ac_last_name")
                        _ac_email = st.text_input("Email", key="_ac_email")
                        _ac_phone = st.text_input("Phone", key="_ac_phone")
                        _ac_dob = st.text_input("Date of Birth", key="_ac_dob", placeholder="YYYY-MM-DD")
                    with _ac2:
                        _ac_type = st.selectbox("Client Type", ["Individual", "Organization", "Government"], key="_ac_type")
                        _ac_mailing = st.text_area("Mailing Address", key="_ac_mailing_addr", height=68)
                        _ac_home_same = st.checkbox("Home address same as mailing", key="_ac_home_same", value=False)
                        if not _ac_home_same:
                            _ac_home = st.text_area("Home Address", key="_ac_home_addr", height=68)
                        else:
                            _ac_home = ""
                        _ac_employer = st.text_input("Employer", key="_ac_employer")
                        _ac_referral = st.text_input("Referral Source", key="_ac_referral")
                    _ac_tags = st.text_input("Tags (comma-separated)", key="_ac_tags", placeholder="vip, family-law, referral")
                    _ac_notes = st.text_area("Notes", key="_ac_notes", height=68)
                    _ac_submit = st.form_submit_button("\U0001f4be Save Client", type="primary")

                    if _ac_submit and (_ac_first or _ac_last):
                        _tag_list = [t.strip() for t in _ac_tags.split(",") if t.strip()] if _ac_tags else []
                        _new_id = crm.add_client(
                            first_name=_ac_first, last_name=_ac_last,
                            client_type=_ac_type,
                            email=_ac_email, phone=_ac_phone,
                            mailing_address=_ac_mailing,
                            home_address=_ac_home,
                            home_same_as_mailing=_ac_home_same,
                            date_of_birth=_ac_dob,
                            employer=_ac_employer, notes=_ac_notes,
                            referral_source=_ac_referral, tags=_tag_list,
                        )
                        _display_name = f"{_ac_first} {_ac_last}".strip()
                        st.success(f"\u2705 Client added: **{_display_name}** (ID: {_new_id})")
                        st.session_state["_crm_adding"] = False
                        st.rerun()

        # -- Client List --
        _all_clients = crm.load_clients()
        if _crm_search:
            _all_clients = crm.search_clients(_crm_search)

        if _all_clients:
            st.markdown(f"### \U0001f4cb Clients ({len(_all_clients)})")

            # Status filter
            _status_filter = st.selectbox("Filter by Status", ["All", "Active", "Inactive", "Prospective"], key="_crm_status_filter")
            if _status_filter != "All":
                _all_clients = [c for c in _all_clients if c.get("intake_status", "active") == _status_filter.lower()]

            for _cli in sorted(_all_clients, key=lambda x: x.get("name", "").lower()):
                _cli_name = _cli.get("name", "Unknown")
                _cli_type = _cli.get("client_type", "Individual")
                _cli_status = _cli.get("intake_status", "active")
                _status_icon = {"active": "\U0001f7e2", "inactive": "\U0001f534", "prospective": "\U0001f7e1"}.get(_cli_status, "\u26aa")
                _cli_email = _cli.get("email", "")
                _cli_phone = _cli.get("phone", "")
                _contact_info = f" | {_cli_email}" if _cli_email else ""
                _contact_info += f" | {_cli_phone}" if _cli_phone else ""
                _tags = _cli.get("tags", [])
                _tag_str = " ".join([f"`{t}`" for t in _tags]) if _tags else ""

                with st.expander(f"{_status_icon} **{_cli_name}** ({_cli_type}){_contact_info}"):
                    _ec1, _ec2 = st.columns(2)
                    with _ec1:
                        _first = _cli.get("first_name", "")
                        _last = _cli.get("last_name", "")
                        if _first or _last:
                            st.markdown(f"**First Name:** {_first}")
                            st.markdown(f"**Last Name:** {_last}")
                        else:
                            st.markdown(f"**Name:** {_cli_name}")
                        st.markdown(f"**Type:** {_cli_type}")
                        st.markdown(f"**Email:** {_cli_email or 'N/A'}")
                        st.markdown(f"**Phone:** {_cli_phone or 'N/A'}")
                        st.markdown(f"**DOB:** {_cli.get('date_of_birth', 'N/A')}")
                    with _ec2:
                        _mailing = _cli.get("mailing_address", _cli.get("address", "N/A"))
                        st.markdown(f"**Mailing Address:** {_mailing or 'N/A'}")
                        if _cli.get("home_same_as_mailing"):
                            st.markdown("**Home Address:** Same as mailing")
                        elif _cli.get("home_address"):
                            st.markdown(f"**Home Address:** {_cli['home_address']}")
                        st.markdown(f"**Employer:** {_cli.get('employer', 'N/A')}")
                        st.markdown(f"**Referral:** {_cli.get('referral_source', 'N/A')}")
                        st.markdown(f"**Status:** {_status_icon} {_cli_status.title()}")
                        if _tag_str:
                            st.markdown(f"**Tags:** {_tag_str}")
                    if _cli.get("notes"):
                        st.markdown(f"**Notes:** {_cli['notes']}")

                    # Linked cases
                    _linked = crm.get_cases_for_client(_cli.get("id", ""))
                    if _linked:
                        st.markdown(f"**Linked Cases:** {len(_linked)}")
                        for _lc in _linked:
                            st.markdown(f"  - `{_lc}`")

                    # Link current case
                    st.markdown("---")
                    _btn_col1, _btn_col2, _btn_col3 = st.columns(3)
                    with _btn_col1:
                        if case_id and st.button("\U0001f517 Link to This Case", key=f"_crm_link_{_cli.get('id')}"):
                            crm.link_client_to_case(_cli.get("id", ""), case_id)
                            st.success(f"Linked {_cli_name} to current case!")
                            st.rerun()
                    with _btn_col2:
                        _new_status = "inactive" if _cli_status == "active" else "active"
                        if st.button(f"{'\U0001f534' if _cli_status == 'active' else '\U0001f7e2'} Mark {_new_status.title()}", key=f"_crm_status_{_cli.get('id')}"):
                            crm.update_client(_cli.get("id", ""), {"intake_status": _new_status})
                            st.rerun()
                    with _btn_col3:
                        if st.button("\U0001f5d1\ufe0f Delete", key=f"_crm_del_{_cli.get('id')}"):
                            crm.delete_client(_cli.get("id", ""))
                            st.success("Client deleted.")
                            st.rerun()
        else:
            if _crm_search:
                st.info(f"No clients matching '{_crm_search}'. Try a different search or add a new client.")
            else:
                st.info("No clients yet. Click **Add Client** to create your first client record.")

    # -- 2. Intake Forms --------------------------------------------------------
    if active_tab == "\U0001f4dd Intake Forms":
        st.markdown("## \U0001f4dd Client Intake Forms")
        st.caption("Standardized intake questionnaires for new client onboarding.")

        # Select client
        _intake_clients = crm.load_clients()
        _client_names = {c.get("id", ""): c.get("name", "Unknown") for c in _intake_clients}
        _client_options = ["\u2014 Select Client \u2014"] + [f"{v} ({k})" for k, v in _client_names.items()]

        _selected_client_str = st.selectbox("Select Client", _client_options, key="_intake_client_select")

        if _selected_client_str and _selected_client_str != "\u2014 Select Client \u2014":
            _sel_client_id = _selected_client_str.split("(")[-1].rstrip(")")
            _sel_client_name = _client_names.get(_sel_client_id, "Unknown")

            st.markdown(f"### Intake for: **{_sel_client_name}**")

            # Get templates
            _templates = crm.get_intake_templates()
            _template_keys = list(_templates.keys())
            _template_labels = [_templates[k]["title"] for k in _template_keys]

            _sel_template = st.selectbox("Template", _template_labels, key="_intake_template")
            _sel_template_key = _template_keys[_template_labels.index(_sel_template)]
            _template = _templates[_sel_template_key]

            # Check for existing answers
            _existing = crm.get_intake_answers(_sel_client_id, _sel_template_key)

            if _existing:
                st.success("\u2705 This intake form has been completed.")
                with st.expander("\U0001f4cb View Submitted Answers", expanded=True):
                    for _field in _template.get("fields", []):
                        _fname = _field.get("name", "")
                        _flabel = _field.get("label", _fname)
                        _val = _existing.get("answers", {}).get(_fname, "\u2014")
                        st.markdown(f"**{_flabel}:** {_val}")
                    st.caption(f"Submitted: {_existing.get('submitted_at', 'N/A')}")
            else:
                # Show form
                with st.form(f"intake_{_sel_template_key}_{_sel_client_id}", clear_on_submit=False):
                    st.markdown(f"**{_template.get('title', '')}**")
                    if _template.get("description"):
                        st.caption(_template["description"])

                    _answers = {}
                    for _field in _template.get("fields", []):
                        _fname = _field.get("name", "")
                        _flabel = _field.get("label", _fname)
                        _ftype = _field.get("type", "text")
                        _freq = _field.get("required", False)
                        _label = f"{_flabel} {'*' if _freq else ''}"

                        if _ftype == "textarea":
                            _answers[_fname] = st.text_area(_label, key=f"_if_{_fname}")
                        elif _ftype == "select":
                            _options = _field.get("options", [])
                            _answers[_fname] = st.selectbox(_label, _options, key=f"_if_{_fname}")
                        elif _ftype == "date":
                            _answers[_fname] = str(st.date_input(_label, value=None, key=f"_if_{_fname}"))
                        elif _ftype == "checkbox":
                            _answers[_fname] = st.checkbox(_label, key=f"_if_{_fname}")
                        else:
                            _answers[_fname] = st.text_input(_label, key=f"_if_{_fname}")

                    if st.form_submit_button("\U0001f4be Submit Intake Form", type="primary"):
                        crm.save_intake_answers(_sel_client_id, _sel_template_key, _answers)
                        st.success("\u2705 Intake form submitted!")
                        st.rerun()
        else:
            st.info("Select a client above to complete an intake form. Add clients in the **Client Directory** tab first.")

    # -- 3. CRM Dashboard -------------------------------------------------------
    if active_tab == "\U0001f4ca CRM Dashboard":
        st.markdown("## \U0001f4ca CRM Dashboard")
        st.caption("Client relationship metrics and overview.")

        try:
            _crm_stats = crm.get_crm_stats()

            # Metrics row
            _cm1, _cm2, _cm3, _cm4 = st.columns(4)
            _cm1.metric("\U0001f465 Total Clients", _crm_stats.get("total_clients", 0))
            _cm2.metric("\U0001f7e2 Active", _crm_stats.get("active", 0))
            _cm3.metric("\U0001f534 Former", _crm_stats.get("former", 0))
            _cm4.metric("\U0001f7e1 Prospective", _crm_stats.get("prospective", 0))

            # Type breakdown
            _type_counts = _crm_stats.get("type_breakdown", {})
            if _type_counts:
                st.markdown("### \U0001f4ca Client Types")
                _tc1, _tc2, _tc3 = st.columns(3)
                _tc1.metric("\U0001f464 Individuals", _type_counts.get("Individual", 0))
                _tc2.metric("\U0001f3e2 Organizations", _type_counts.get("Organization", 0))
                _tc3.metric("\U0001f3db\ufe0f Government", _type_counts.get("Government", 0))

            # Recent clients
            _all_clients = crm.load_clients()
            _recent = sorted(_all_clients, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
            if _recent:
                st.markdown("### \U0001f4cb Recent Clients")
                for _rc in _recent:
                    _rc_status = {"active": "\U0001f7e2", "inactive": "\U0001f534", "prospective": "\U0001f7e1"}.get(_rc.get("intake_status", ""), "\u26aa")
                    _rc_date = _rc.get("created_at", "")[:10] if _rc.get("created_at") else "N/A"
                    st.markdown(f"- {_rc_status} **{_rc.get('name', 'Unknown')}** ({_rc.get('client_type', '')}) — Added {_rc_date}")

            # Intake stats
            _intake_stats = _crm_stats.get("intake_stats", {})
            if _intake_stats:
                st.markdown("### \U0001f4dd Intake Completion")
                _completed = _intake_stats.get("completed", 0)
                _total = _intake_stats.get("total_clients", 0)
                if _total > 0:
                    st.progress(_completed / _total)
                    st.caption(f"{_completed}/{_total} clients have completed intake forms")
        except Exception as e:
            st.error(f"Error loading CRM dashboard: {e}")
