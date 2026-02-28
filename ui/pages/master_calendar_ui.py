"""Master Calendar UI module — dashboard-level firm-wide calendar.
Ported from legacy ui_modules/master_calendar_ui.py."""
import calendar as _cal_mod
import logging
from datetime import date as _date_cls

import streamlit as st

logger = logging.getLogger(__name__)


def _filter_events_by_staff(events, selected_user_ids):
    """Filter events to only those assigned to selected users."""
    if not selected_user_ids:
        return events
    return [
        e for e in events
        if set(e.get("assigned_to", [])) & set(selected_user_ids)
    ]


def render_master_calendar(case_mgr, user_id: str = "", user_mgr=None):
    """Render the master calendar section on the dashboard."""
    try:
        from core import calendar_events
    except ImportError:
        st.caption("Calendar module not available.")
        return

    st.subheader("\U0001f4c5 Master Calendar")

    # Google Calendar connection
    try:
        from core import google_cal_sync
        _gcal_connected = google_cal_sync.is_connected(user_id) if user_id else False
    except ImportError:
        _gcal_connected = False
        google_cal_sync = None

    if _gcal_connected:
        _gcal_email = google_cal_sync.get_connected_email(user_id)
        st.caption(
            f"\U0001f517 Google Calendar connected"
            f"{f' ({_gcal_email})' if _gcal_email else ''}"
        )

    # Staff filter
    _staff_filter_ids = []
    if user_mgr:
        try:
            _all_users = user_mgr.list_users()
            _active_users = [u for u in _all_users if u.get("active", True)]
            if _active_users:
                _user_label_map = {
                    f"{u['name']} ({u.get('role', '').title()})": u["id"]
                    for u in _active_users
                }
                _selected_labels = st.multiselect(
                    "\U0001f464 Filter by Attorney / Staff",
                    options=list(_user_label_map.keys()),
                    default=[],
                    key="_mcal_staff_filter",
                    placeholder="All team members",
                )
                _staff_filter_ids = [_user_label_map[lbl] for lbl in _selected_labels]
        except Exception:
            pass

    # Month navigation
    _today = _date_cls.today()
    _cal_year = st.session_state.get("_mcal_year", _today.year)
    _cal_month = st.session_state.get("_mcal_month", _today.month)

    _nav_c1, _nav_c2, _nav_c3, _nav_c4 = st.columns([1, 3, 1, 1])
    with _nav_c1:
        if st.button("\u25c0 Prev", key="_mcal_prev", use_container_width=True):
            _cal_month -= 1
            if _cal_month < 1:
                _cal_month = 12
                _cal_year -= 1
            st.session_state["_mcal_year"] = _cal_year
            st.session_state["_mcal_month"] = _cal_month
            st.rerun()
    with _nav_c2:
        st.markdown(f"### {_cal_mod.month_name[_cal_month]} {_cal_year}")
    with _nav_c3:
        if st.button("Next \u25b6", key="_mcal_next", use_container_width=True):
            _cal_month += 1
            if _cal_month > 12:
                _cal_month = 1
                _cal_year += 1
            st.session_state["_mcal_year"] = _cal_year
            st.session_state["_mcal_month"] = _cal_month
            st.rerun()
    with _nav_c4:
        if st.button("\U0001f4cd Today", key="_mcal_today", use_container_width=True):
            st.session_state["_mcal_year"] = _today.year
            st.session_state["_mcal_month"] = _today.month
            st.rerun()

    # Calendar grid
    try:
        _cal_data = calendar_events.get_month_calendar(_cal_year, _cal_month)
    except Exception:
        st.caption("Could not load calendar data.")
        return

    _type_icons = {
        "Court Date": "\u2696\ufe0f",
        "Filing Deadline": "\U0001f4c4",
        "Client Meeting": "\U0001f464",
        "Deposition": "\U0001f4cb",
        "Mediation": "\U0001f91d",
        "Consultation": "\U0001f4ac",
        "Internal": "\U0001f3e2",
        "Other": "\U0001f4c5",
    }

    _day_headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    _hdr_cols = st.columns(7)
    for _i, _h in enumerate(_day_headers):
        _hdr_cols[_i].markdown(f"**{_h}**")

    for _week in _cal_data.get("weeks", []):
        _week_cols = st.columns(7)
        for _di, _day_data in enumerate(_week):
            with _week_cols[_di]:
                if _day_data is None:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                else:
                    _day_num = _day_data.get("day", 0)
                    _day_events = _day_data.get("events", [])
                    if _staff_filter_ids:
                        _day_events = _filter_events_by_staff(
                            _day_events, _staff_filter_ids
                        )
                    _is_today = _day_data.get("is_today", False)

                    if _is_today:
                        _label = f"**\U0001f535 {_day_num}**"
                    elif _day_events:
                        _label = f"**{_day_num}** \U0001f4cc"
                    else:
                        _label = str(_day_num)

                    st.markdown(_label)
                    for _de in _day_events[:2]:
                        _icon = _type_icons.get(_de.get("event_type", ""), "\U0001f4c5")
                        st.caption(f"{_icon} {_de.get('title', '')[:18]}")
                    if len(_day_events) > 2:
                        st.caption(f"+{len(_day_events) - 2} more")

    # Daily detail
    st.divider()
    _det_c1, _det_c2 = st.columns([1, 1])

    with _det_c1:
        _sel_date = st.date_input(
            "View events for:", value=_today, key="_mcal_date_pick"
        )
        _date_str = str(_sel_date)
        try:
            _day_evts = calendar_events.get_events_for_date(_date_str)
        except Exception:
            _day_evts = []
        if _staff_filter_ids:
            _day_evts = _filter_events_by_staff(_day_evts, _staff_filter_ids)

        if _day_evts:
            st.markdown(f"#### {len(_day_evts)} event(s) on {_date_str}")
            for _evt in _day_evts:
                _et = _evt.get("event_type", "Other")
                _icon = _type_icons.get(_et, "\U0001f4c5")
                _time_str = f" at {_evt.get('time', '')}" if _evt.get("time") else ""
                with st.expander(f"{_icon} {_evt.get('title', '')}{_time_str}"):
                    st.markdown(f"**Type:** {_et}")
                    if _evt.get("time"):
                        st.markdown(f"**Time:** {_evt['time']}")
                    if _evt.get("location"):
                        st.markdown(f"**Location:** {_evt['location']}")
                    if _evt.get("description"):
                        st.markdown(f"**Notes:** {_evt['description']}")
                    if _evt.get("case_id"):
                        st.markdown(f"**Case:** `{_evt['case_id']}`")
        else:
            st.info(f"No events on {_date_str}.")

    with _det_c2:
        st.markdown("#### \U0001f4c5 Upcoming (14 days)")
        try:
            _upcoming = calendar_events.get_upcoming_events(14)
        except Exception:
            _upcoming = []
        if _staff_filter_ids:
            _upcoming = _filter_events_by_staff(_upcoming, _staff_filter_ids)
        if _upcoming:
            for _ue in _upcoming:
                _days = _ue.get("days_until", 999)
                _urg = (
                    "\U0001f534" if _days == 0
                    else "\U0001f7e1" if _days <= 3
                    else "\U0001f7e2"
                )
                _t = f" {_ue.get('time', '')}" if _ue.get("time") else ""
                st.markdown(
                    f"- {_urg} **{_ue.get('title', '')}** \u2014 "
                    f"{_ue.get('date', '')}{_t} ({_days}d)"
                )
        else:
            st.caption("No upcoming events.")

    # New event form
    st.divider()
    with st.expander("\u2795 Add Event to Master Calendar", expanded=False):
        _ne1, _ne2 = st.columns(2)
        with _ne1:
            _ne_title = st.text_input(
                "Event Title *", key="_mc_ne_title",
                placeholder="e.g., Smith v. Jones \u2014 Hearing",
            )
            try:
                _ne_type = st.selectbox(
                    "Event Type", calendar_events.EVENT_TYPES, key="_mc_ne_type"
                )
            except Exception:
                _ne_type = st.text_input("Event Type", key="_mc_ne_type")
            _ne_date = st.date_input("Date *", key="_mc_ne_date")
            _ne_time = st.time_input("Start Time", value=None, key="_mc_ne_time")

        with _ne2:
            _all_cases = case_mgr.list_cases() if case_mgr else []
            _case_options = ["\u2014 No Case \u2014"] + [
                f"{c.get('name', '?')} ({c['id'][:8]})" for c in _all_cases
            ]
            _ne_case_sel = st.selectbox(
                "Link to Case", _case_options, key="_mc_ne_case"
            )
            _ne_location = st.text_input(
                "Location", key="_mc_ne_loc",
                placeholder="e.g., Courtroom 4B",
            )

        _ne_desc = st.text_area(
            "Description / Notes", key="_mc_ne_desc", height=80
        )

        if st.button(
            "\U0001f4c5 Create Event",
            key="_mc_ne_submit",
            type="primary",
            use_container_width=True,
        ):
            if not _ne_title:
                st.error("Event title is required.")
            else:
                _case_id = ""
                if _ne_case_sel and _ne_case_sel != "\u2014 No Case \u2014":
                    _case_id = _ne_case_sel.split("(")[-1].rstrip(")")

                _time_str = _ne_time.strftime("%H:%M") if _ne_time else ""

                try:
                    calendar_events.add_event(
                        title=_ne_title,
                        event_type=_ne_type,
                        event_date=str(_ne_date),
                        time=_time_str,
                        location=_ne_location,
                        case_id=_case_id,
                        description=_ne_desc,
                    )
                    st.success(f"\u2705 **{_ne_title}** created on {_ne_date}!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to create event: {exc}")
