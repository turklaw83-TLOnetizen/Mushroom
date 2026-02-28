"""Case Activity Log UI module — enhanced with search, user attribution, filters, CSV export."""
import csv
import io
import logging
import streamlit as st
from datetime import datetime, timedelta

from core.case_manager import CaseManager

logger = logging.getLogger(__name__)

_ACT_ICONS = {
    "file_upload": "\U0001f4ce",
    "file_delete": "\U0001f5d1\ufe0f",
    "analysis_run": "\U0001f916",
    "case_create": "\U0001f4c1",
    "case_archive": "\U0001f4e6",
    "case_update": "\u270f\ufe0f",
    "invoice_created": "\U0001f9fe",
    "invoice_sent": "\U0001f4e4",
    "invoice_paid": "\u2705",
    "deadline_set": "\u23f0",
    "deadline_removed": "\U0001f515",
    "prep_create": "\U0001f4cb",
    "prep_delete": "\U0001f5d1\ufe0f",
    "directive_add": "\U0001f4dd",
    "note_add": "\U0001f5d2\ufe0f",
    "export": "\U0001f4e5",
    "login": "\U0001f511",
    "task_create": "\u2611\ufe0f",
    "task_update": "\U0001f4cb",
    "email_approve": "\U0001f4e7",
    "email_dismiss": "\U0001f4e7",
    "retainer_deposit": "\U0001f4b0",
    "payment_record": "\U0001f4b3",
}

_CATEGORY_MAP = {
    "file_upload": "document",
    "file_delete": "document",
    "analysis_run": "analysis",
    "case_create": "system",
    "case_archive": "system",
    "case_update": "system",
    "invoice_created": "billing",
    "invoice_sent": "billing",
    "invoice_paid": "billing",
    "deadline_set": "system",
    "deadline_removed": "system",
    "prep_create": "system",
    "prep_delete": "system",
    "directive_add": "system",
    "note_add": "system",
    "export": "system",
    "login": "system",
    "task_create": "system",
    "task_update": "system",
    "email_approve": "system",
    "email_dismiss": "system",
    "retainer_deposit": "billing",
    "payment_record": "billing",
}

CATEGORY_LABELS = {
    "all": "All Categories",
    "analysis": "\U0001f916 Analysis",
    "document": "\U0001f4ce Document",
    "billing": "\U0001f4b0 Billing",
    "client": "\U0001f465 Client",
    "system": "\u2699\ufe0f System",
}


def _entries_to_csv(entries):
    """Convert activity entries to a CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Action", "User", "Category", "Detail"])
    for e in entries:
        _cat = e.get("category") or _CATEGORY_MAP.get(e.get("action", ""), "system")
        writer.writerow([
            e.get("timestamp", ""),
            e.get("action", "").replace("_", " ").title(),
            e.get("user_name", "") or e.get("user", ""),
            _cat,
            e.get("detail", ""),
        ])
    return output.getvalue()


def render_activity_log(case_id: str, case_mgr):
    """Main entry point for the Activity tab UI."""
    st.subheader("\U0001f4dc Activity Log")
    st.caption("Audit trail of actions taken on this case — with search, filters, and export.")

    # -- Search Bar --
    _search = st.text_input(
        "\U0001f50d Search activity",
        placeholder="Search actions, details, users...",
        key="_act_search",
        label_visibility="collapsed",
    )

    # -- Filters Row --
    _fl1, _fl2, _fl3, _fl4, _fl5 = st.columns([2, 1.5, 1.5, 1, 1])
    with _fl1:
        _action_options = ["All Actions"] + sorted(_ACT_ICONS.keys())
        _selected_action = st.selectbox(
            "Action", _action_options, key="_act_filter", label_visibility="collapsed",
        )
    with _fl2:
        _cat_options = list(CATEGORY_LABELS.keys())
        _selected_cat = st.selectbox(
            "Category", _cat_options,
            format_func=lambda x: CATEGORY_LABELS.get(x, x),
            key="_act_cat_filter",
            label_visibility="collapsed",
        )
    with _fl3:
        # User filter — build from entries
        _all_entries_raw = case_mgr.get_activity_log(case_id, limit=2000)
        _users_in_log = sorted(set(
            e.get("user_name") or e.get("user", "")
            for e in _all_entries_raw if e.get("user_name") or e.get("user")
        ))
        _user_options = ["All Users"] + _users_in_log
        _selected_user = st.selectbox(
            "User", _user_options, key="_act_user_filter", label_visibility="collapsed",
        )
    with _fl4:
        _limit = st.number_input(
            "Entries", min_value=10, max_value=500, value=50, step=10, key="_act_limit",
        )
    with _fl5:
        _order = st.selectbox("Order", ["Newest", "Oldest"], key="_act_order")

    # -- Date Range Filter --
    _dr1, _dr2 = st.columns(2)
    with _dr1:
        _date_from = st.date_input(
            "From", value=None, key="_act_date_from",
        )
    with _dr2:
        _date_to = st.date_input(
            "To", value=None, key="_act_date_to",
        )

    # -- Apply Filters --
    _afilt = "" if _selected_action == "All Actions" else _selected_action
    _newest = _order == "Newest"
    entries = _all_entries_raw

    # Action filter
    if _afilt:
        entries = [e for e in entries if e.get("action") == _afilt]

    # Category filter
    if _selected_cat != "all":
        entries = [
            e for e in entries
            if (e.get("category") or _CATEGORY_MAP.get(e.get("action", ""), "system")) == _selected_cat
        ]

    # User filter
    if _selected_user != "All Users":
        entries = [
            e for e in entries
            if (e.get("user_name") or e.get("user", "")) == _selected_user
        ]

    # Date range filter
    if _date_from:
        _from_str = _date_from.isoformat()
        entries = [e for e in entries if e.get("timestamp", "") >= _from_str]
    if _date_to:
        _to_str = (_date_to + timedelta(days=1)).isoformat()
        entries = [e for e in entries if e.get("timestamp", "") < _to_str]

    # Text search filter
    if _search and _search.strip():
        _q = _search.strip().lower()
        entries = [
            e for e in entries
            if _q in e.get("action", "").lower()
            or _q in e.get("detail", "").lower()
            or _q in (e.get("user_name") or e.get("user", "")).lower()
        ]

    # Sort
    entries = sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=_newest)
    entries = entries[:int(_limit)]

    if not entries:
        st.info("No activity entries match your filters.")
        return

    # -- Summary + Export --
    _sum1, _sum2 = st.columns([3, 1])
    with _sum1:
        st.markdown(f"**{len(entries)} entries** (of {len(_all_entries_raw)} total)")
    with _sum2:
        _csv_data = _entries_to_csv(entries)
        st.download_button(
            "\U0001f4e5 Export CSV",
            data=_csv_data,
            file_name=f"activity_log_{case_id}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="_act_export_csv",
            use_container_width=True,
        )

    st.markdown("---")

    # -- Paginated Display --
    _page_size = 50
    _total_pages = max(1, (len(entries) + _page_size - 1) // _page_size)
    _current_page = st.session_state.get("_act_page", 1)
    if _current_page > _total_pages:
        _current_page = 1

    _start = (_current_page - 1) * _page_size
    _page_entries = entries[_start : _start + _page_size]

    for _e in _page_entries:
        _ts_raw = _e.get("timestamp", "")
        try:
            _ts = datetime.fromisoformat(_ts_raw).strftime("%b %d, %Y  %I:%M %p")
        except Exception:
            _ts = _ts_raw

        _action = _e.get("action", "unknown")
        _icon = _ACT_ICONS.get(_action, "\U0001f539")
        _detail = _e.get("detail", "")
        _user_name = _e.get("user_name") or _e.get("user", "")
        _user_badge = f"  \U0001f464 `{_user_name}`" if _user_name else ""
        _cat = _e.get("category") or _CATEGORY_MAP.get(_action, "")
        _cat_label = CATEGORY_LABELS.get(_cat, "").split(" ", 1)[-1] if _cat else ""
        _cat_badge = f"  \u00b7 {_cat_label}" if _cat_label else ""

        st.markdown(
            f"{_icon} **{_action.replace('_', ' ').title()}**{_user_badge}{_cat_badge}  \n"
            f"<small style='color:#888'>{_ts}</small>  \n"
            f"{_detail}",
            unsafe_allow_html=True,
        )
        st.markdown("<hr style='margin:4px 0;border-color:#333'>", unsafe_allow_html=True)

    # Pagination controls
    if _total_pages > 1:
        _p1, _p2, _p3 = st.columns([1, 2, 1])
        with _p1:
            if st.button("\u2190 Prev", key="_act_prev", disabled=_current_page <= 1):
                st.session_state["_act_page"] = _current_page - 1
                st.rerun()
        with _p2:
            st.caption(f"Page {_current_page} of {_total_pages}")
        with _p3:
            if st.button("Next \u2192", key="_act_next", disabled=_current_page >= _total_pages):
                st.session_state["_act_page"] = _current_page + 1
                st.rerun()


def render(case_id, case_mgr, results, **ctx):
    """Standard render() entry point — delegates to render_activity_log."""
    render_activity_log(case_id, case_mgr)
