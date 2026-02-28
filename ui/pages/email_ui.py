"""
email_ui.py -- Email Integration UI
Gmail approval queue for classifying emails into cases.
"""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(case_id=None, case_mgr=None, **kwargs):
    """Render the email integration interface."""
    from core.email_integration import (
        get_pending_emails, get_all_emails, classify_email,
        dismiss_email, get_email_queue_stats, EMAIL_STATUSES,
    )

    st.markdown("### \U0001f4e7 Email Integration")

    # Stats
    stats = get_email_queue_stats()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Pending", stats["pending"])
    s2.metric("Approved", stats["approved"])
    s3.metric("Dismissed", stats["dismissed"])
    s4.metric("Total", stats["total"])

    st.divider()

    # Gmail connection check
    _gmail_connected = st.session_state.get("_gmail_connected", False)
    if not _gmail_connected:
        st.warning(
            "Gmail is not connected. To enable email integration:\n"
            "1. Configure Google OAuth credentials\n"
            "2. Add Gmail API scopes to your OAuth setup\n"
            "3. Click 'Connect Gmail' below"
        )
        if st.button("\U0001f4e7 Connect Gmail", type="primary"):
            st.info(
                "Gmail OAuth requires:\n"
                "- `google-api-python-client` and `google-auth` packages\n"
                "- Gmail API enabled in Google Cloud Console\n"
                "- OAuth consent screen configured with `gmail.readonly` scope\n\n"
                "Once configured, authentication will use your existing Google OAuth login."
            )
        st.divider()

    # Filter tabs
    _filter = st.selectbox(
        "Show", ["Pending", "All", "Approved", "Dismissed"],
        key="_email_filter",
        label_visibility="collapsed",
    )

    _status_map = {"Pending": "pending", "Approved": "approved", "Dismissed": "dismissed", "All": ""}
    emails = get_all_emails(_status_map.get(_filter, ""))

    if not emails:
        st.info("No emails in queue. Click 'Check Email' to fetch new messages.")
        return

    # Build case list for dropdown
    cases = case_mgr.list_cases() if case_mgr else []
    case_map = {c["id"]: c.get("name", c["id"]) for c in cases}
    case_ids = [c["id"] for c in cases]

    for email in emails:
        _eid = email.get("id", "")
        _status = email.get("status", "pending")

        with st.container(border=True):
            _ec1, _ec2 = st.columns([3, 1])
            with _ec1:
                _status_icon = {
                    "pending": "\u23f3", "approved": "\u2705", "dismissed": "\u274c"
                }.get(_status, "")
                st.markdown(f"{_status_icon} **{email.get('subject', '(No subject)')}**")
                st.caption(
                    f"From: {email.get('from', '?')} \u00b7 "
                    f"{email.get('date', '')}"
                )
                if email.get("snippet"):
                    st.caption(email["snippet"][:150])

                # Show attachments
                atts = email.get("attachments", [])
                if atts:
                    att_str = ", ".join(a.get("filename", "?") for a in atts)
                    st.caption(f"\U0001f4ce Attachments: {att_str}")

            with _ec2:
                if _status == "pending":
                    # Case assignment
                    _suggested = email.get("suggested_case_id", "")
                    _default_idx = case_ids.index(_suggested) if _suggested in case_ids else 0
                    _assigned_case = st.selectbox(
                        "Assign to case",
                        case_ids,
                        index=_default_idx if case_ids else 0,
                        format_func=lambda x: case_map.get(x, x),
                        key=f"_em_case_{_eid}",
                        label_visibility="collapsed",
                    ) if case_ids else ""

                    _ab1, _ab2 = st.columns(2)
                    with _ab1:
                        if st.button(
                            "\u2705 Approve", key=f"_em_approve_{_eid}",
                            type="primary", use_container_width=True,
                        ):
                            if _assigned_case:
                                classify_email(_eid, _assigned_case, case_mgr=case_mgr)
                                st.toast(f"Email approved into {case_map.get(_assigned_case, _assigned_case)}")
                                st.rerun()
                            else:
                                st.warning("Select a case first")
                    with _ab2:
                        if st.button(
                            "\u274c Dismiss", key=f"_em_dismiss_{_eid}",
                            use_container_width=True,
                        ):
                            dismiss_email(_eid)
                            st.toast("Email dismissed")
                            st.rerun()

                elif _status == "approved":
                    _assigned = email.get("assigned_case_id", "")
                    st.caption(f"\u2705 {case_map.get(_assigned, _assigned)}")
                else:
                    st.caption("\u274c Dismissed")

            # Expandable email body
            if email.get("body"):
                with st.expander("View email body", expanded=False):
                    st.text(email["body"][:5000])
                    if len(email.get("body", "")) > 5000:
                        st.caption("(Showing first 5,000 characters)")
