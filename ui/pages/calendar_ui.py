"""Calendar & Events UI module — ported from legacy ui_modules/calendar_ui.py."""
import logging
import streamlit as st
from datetime import date as _date_cls

from core import calendar_events
from core import crm
from core import google_cal_sync

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, results, **ctx):
    """Render all tabs for the Calendar nav group."""
    active_tab = ctx.get("active_tab", "")

    # Resolve current user ID for Google Calendar sync
    _user_id = ""
    _current_user = st.session_state.get("current_user")
    if isinstance(_current_user, dict):
        _user_id = _current_user.get("id", "")
    _gcal_connected = google_cal_sync.is_connected(_user_id) if _user_id else False

    # Helper: filter events to current case when inside a case view
    def _case_filter(events_list):
        if not case_id:
            return events_list
        return [e for e in events_list if e.get("case_id") == case_id or not e.get("case_id")]

    # -- 1. Calendar View -------------------------------------------------------
    if active_tab == "\U0001f4c5 Calendar View":
        st.markdown("## \U0001f4c5 Calendar")
        if case_id:
            st.info("Showing events for this case. Use the **Master Calendar** on the dashboard for all firm events.")
        else:
            st.caption("Unified view of events, hearings, and deadlines.")

        # Google Calendar status badge
        if _gcal_connected:
            _gcal_email = google_cal_sync.get_connected_email(_user_id)
            st.caption(f"\U0001f517 Google Calendar connected{f' ({_gcal_email})' if _gcal_email else ''}")

        # Month navigation
        _today = _date_cls.today()
        _cal_year = st.session_state.get("_cal_year", _today.year)
        _cal_month = st.session_state.get("_cal_month", _today.month)

        _nav_c1, _nav_c2, _nav_c3 = st.columns([1, 3, 1])
        with _nav_c1:
            if st.button("\u25c0 Prev", key="_cal_prev", use_container_width=True):
                _cal_month -= 1
                if _cal_month < 1:
                    _cal_month = 12
                    _cal_year -= 1
                st.session_state["_cal_year"] = _cal_year
                st.session_state["_cal_month"] = _cal_month
                st.rerun()
        with _nav_c2:
            st.markdown(f"### \U0001f4c5 {calendar_events._cal.month_name[_cal_month]} {_cal_year}")
        with _nav_c3:
            if st.button("Next \u25b6", key="_cal_next", use_container_width=True):
                _cal_month += 1
                if _cal_month > 12:
                    _cal_month = 1
                    _cal_year += 1
                st.session_state["_cal_year"] = _cal_year
                st.session_state["_cal_month"] = _cal_month
                st.rerun()

        # Today button
        if st.button("\U0001f4cd Today", key="_cal_today"):
            st.session_state["_cal_year"] = _today.year
            st.session_state["_cal_month"] = _today.month
            st.rerun()

        # Get calendar data
        _cal_data = calendar_events.get_month_calendar(_cal_year, _cal_month)

        # Case-scope: filter events in each day cell
        if case_id:
            for _week in _cal_data.get("weeks", []):
                for _day_data in _week:
                    if _day_data and _day_data.get("events"):
                        _day_data["events"] = _case_filter(_day_data["events"])

        # Render calendar grid
        _day_headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        _header_cols = st.columns(7)
        for _hi, _hd in enumerate(_day_headers):
            _header_cols[_hi].markdown(f"**{_hd}**")

        for _week in _cal_data.get("weeks", []):
            _week_cols = st.columns(7)
            for _di, _day_data in enumerate(_week):
                with _week_cols[_di]:
                    if _day_data is None:
                        st.markdown("&nbsp;", unsafe_allow_html=True)
                    else:
                        _day_num = _day_data.get("day", 0)
                        _day_events = _day_data.get("events", [])
                        _is_today = _day_data.get("is_today", False)

                        if _is_today:
                            _day_label = f"**\U0001f535 {_day_num}**"
                        elif _day_events:
                            _day_label = f"**{_day_num}** \U0001f4cc"
                        else:
                            _day_label = str(_day_num)

                        st.markdown(_day_label)
                        for _de in _day_events[:2]:
                            st.caption(f"\u2022 {_de.get('title', '')[:15]}")

        st.divider()

        # Daily detail view
        _selected_date = st.date_input("View events for date:", value=_today, key="_cal_date_pick")
        _date_str = str(_selected_date)
        _day_events = _case_filter(calendar_events.get_events_for_date(_date_str))

        if _day_events:
            st.markdown(f"### \U0001f4cb Events for {_date_str} ({len(_day_events)})")
            for _evt in _day_events:
                _evt_type = _evt.get("event_type", "Other")
                _evt_icon = {"Court Date": "\u2696\ufe0f", "Filing Deadline": "\U0001f4c4", "Client Meeting": "\U0001f464",
                             "Deposition": "\U0001f4cb", "Mediation": "\U0001f91d", "Consultation": "\U0001f4ac",
                             "Internal": "\U0001f3e2"}.get(_evt_type, "\U0001f4c5")
                _evt_time = _evt.get("time", "")
                _evt_loc = _evt.get("location", "")
                _gcal_badge = " \U0001f504" if _evt.get("google_event_id") else ""

                with st.expander(f"{_evt_icon} **{_evt.get('title', 'Event')}** {f'at {_evt_time}' if _evt_time else ''} — {_evt_type}{_gcal_badge}"):
                    st.markdown(f"**Title:** {_evt.get('title', '')}")
                    st.markdown(f"**Type:** {_evt_type}")
                    st.markdown(f"**Date:** {_evt.get('date', '')}")
                    if _evt_time:
                        st.markdown(f"**Time:** {_evt_time}" + (f" \u2013 {_evt.get('end_time', '')}" if _evt.get("end_time") else ""))
                    if _evt_loc:
                        st.markdown(f"**Location:** {_evt_loc}")
                    if _evt.get("description"):
                        st.markdown(f"**Details:** {_evt['description']}")
                    if _evt.get("case_id"):
                        st.markdown(f"**Case:** `{_evt['case_id']}`")
                    st.markdown(f"**Status:** {_evt.get('status', 'scheduled').title()}")
                    if _evt.get("google_event_id"):
                        st.caption("\U0001f504 Synced to Google Calendar")

                    # Actions
                    _ea1, _ea2, _ea3 = st.columns(3)
                    with _ea1:
                        if _evt.get("status") == "scheduled" and st.button("\u2705 Complete", key=f"_evt_done_{_evt.get('id')}"):
                            calendar_events.update_event(_evt["id"], {"status": "completed"})
                            if _evt.get("google_event_id") and _user_id:
                                google_cal_sync.cancel_gcal_event(_user_id, _evt["google_event_id"])
                            st.success("Marked as completed!")
                            st.rerun()
                    with _ea2:
                        if _evt.get("status") == "scheduled" and st.button("\u274c Cancel", key=f"_evt_cancel_{_evt.get('id')}"):
                            calendar_events.update_event(_evt["id"], {"status": "cancelled"})
                            if _evt.get("google_event_id") and _user_id:
                                google_cal_sync.cancel_gcal_event(_user_id, _evt["google_event_id"])
                            st.warning("Event cancelled.")
                            st.rerun()
                    with _ea3:
                        if st.button("\U0001f5d1\ufe0f Delete", key=f"_evt_del_{_evt.get('id')}"):
                            if _evt.get("google_event_id") and _user_id:
                                google_cal_sync.delete_gcal_event(_user_id, _evt["google_event_id"])
                            calendar_events.delete_event(_evt["id"])
                            st.success("Event deleted.")
                            st.rerun()
        else:
            st.info(f"No events scheduled for {_date_str}.")

        # Upcoming events sidebar
        st.divider()
        _upcoming = _case_filter(calendar_events.get_upcoming_events(14))
        if _upcoming:
            st.markdown(f"### \U0001f4c5 Upcoming (Next 14 Days) \u2014 {len(_upcoming)} events")
            for _ue in _upcoming:
                _days_until = _ue.get("days_until", 999)
                _urgency = "\U0001f534" if _days_until == 0 else "\U0001f7e1" if _days_until <= 3 else "\U0001f7e2"
                _ue_time = f" at {_ue.get('time', '')}" if _ue.get("time") else ""
                st.markdown(f"- {_urgency} **{_ue.get('title', '')}** \u2014 {_ue.get('date', '')}{_ue_time} ({_days_until}d)")

    # -- 2. New Event -----------------------------------------------------------
    if active_tab == "\u2795 New Event":
        st.markdown("## \u2795 Create New Event")
        st.caption("Schedule hearings, meetings, deadlines, and other calendar events.")

        with st.form("cal_new_event", clear_on_submit=True):
            _ne_title = st.text_input("Event Title *", key="_ne_title", placeholder="e.g. Smith v. Jones \u2014 Motion Hearing")
            _ne1, _ne2 = st.columns(2)
            with _ne1:
                _ne_type = st.selectbox("Event Type", calendar_events.EVENT_TYPES, key="_ne_type")
                _ne_date = st.date_input("Date *", key="_ne_date")
                _ne_time = st.time_input("Start Time", value=None, key="_ne_time")
                _ne_end = st.time_input("End Time", value=None, key="_ne_end")
            with _ne2:
                _ne_location = st.text_input("Location", key="_ne_loc", placeholder="e.g. Courtroom 4B, Zoom link...")
                _ne_case = st.text_input("Case ID (optional)", value=case_id if case_id else "", key="_ne_case")
                # Client selector
                _ne_clients = crm.load_clients()
                _ne_client_options = ["\u2014 None \u2014"] + [f"{c.get('name', '')} ({c.get('id', '')})" for c in _ne_clients]
                _ne_client_sel = st.selectbox("Link to Client", _ne_client_options, key="_ne_client")
                _ne_reminder = st.multiselect("Reminder (days before)", [0, 1, 3, 7, 14, 30], default=[7, 1], key="_ne_reminder")

            _ne_desc = st.text_area("Description / Notes", key="_ne_desc", height=80)

            # Google Calendar sync toggle (inside form)
            _ne_sync = False
            if _gcal_connected:
                _ne_sync = st.checkbox("\U0001f504 Sync to Google Calendar", value=True, key="_ne_sync_gcal")

            if st.form_submit_button("\U0001f4c5 Create Event", type="primary", use_container_width=True):
                if _ne_title:
                    _ne_client_id = ""
                    if _ne_client_sel and _ne_client_sel != "\u2014 None \u2014":
                        _ne_client_id = _ne_client_sel.split("(")[-1].rstrip(")")

                    _time_str = _ne_time.strftime("%H:%M") if _ne_time else ""
                    _end_str = _ne_end.strftime("%H:%M") if _ne_end else ""

                    _new_eid = calendar_events.add_event(
                        title=_ne_title,
                        event_type=_ne_type,
                        event_date=str(_ne_date),
                        time=_time_str,
                        end_time=_end_str,
                        location=_ne_location,
                        case_id=_ne_case,
                        client_id=_ne_client_id,
                        description=_ne_desc,
                        reminder_days=_ne_reminder,
                    )

                    # Push to Google Calendar
                    if _ne_sync and _user_id:
                        _local_evt = calendar_events.get_event(_new_eid)
                        if _local_evt:
                            _gcal_id = google_cal_sync.push_event(_user_id, _local_evt)
                            if _gcal_id:
                                calendar_events.update_event(_new_eid, {"google_event_id": _gcal_id})
                                st.success(f"\u2705 **{_ne_title}** created and synced to Google Calendar!")
                            else:
                                st.warning(f"\u2705 Event created locally, but Google Calendar sync failed.")
                        else:
                            st.success(f"\u2705 Event created: **{_ne_title}** on {_ne_date}")
                    else:
                        st.success(f"\u2705 Event created: **{_ne_title}** on {_ne_date}" + (f" at {_time_str}" if _time_str else ""))
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Event title is required.")

        # Recent events
        st.divider()
        _recent_events = calendar_events.load_events()
        _recent_events = sorted(_recent_events, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
        if _recent_events:
            st.markdown("### \U0001f4cb Recently Created Events")
            for _re in _recent_events:
                _re_status_icon = {"scheduled": "\U0001f4c5", "completed": "\u2705", "cancelled": "\u274c", "rescheduled": "\U0001f504"}.get(_re.get("status", ""), "\U0001f4c5")
                _gcal_tag = " \U0001f504" if _re.get("google_event_id") else ""
                st.markdown(f"- {_re_status_icon} **{_re.get('title', '')}** \u2014 {_re.get('date', '')} ({_re.get('event_type', '')}){_gcal_tag}")

    # -- 3. Export Calendar ------------------------------------------------------
    if active_tab == "\U0001f4e4 Export Calendar":
        st.markdown("## \U0001f4e4 Export Calendar")
        st.caption("Download your calendar as an .ics file for import into Outlook, Google Calendar, Apple Calendar, etc.")

        _export_scope = st.radio("Export Scope", ["All Events", "Current Case Only"], key="_export_scope", horizontal=True)

        _export_case = case_id if _export_scope == "Current Case Only" and case_id else ""

        # Stats
        _cal_stats = calendar_events.get_calendar_stats()
        _es1, _es2, _es3, _es4 = st.columns(4)
        _es1.metric("\U0001f4c5 Total Events", _cal_stats.get("total_events", 0))
        _es2.metric("\U0001f4c6 Upcoming", _cal_stats.get("upcoming", 0))
        _es3.metric("\U0001f4c5 This Week", _cal_stats.get("this_week", 0))
        _es4.metric("\u2705 Completed", _cal_stats.get("completed", 0))

        # Type breakdown
        _type_bd = _cal_stats.get("type_breakdown", {})
        if _type_bd:
            st.markdown("### \U0001f4ca Events by Type")
            for _et, _ec in sorted(_type_bd.items(), key=lambda x: -x[1]):
                _bar = "\u2588" * min(_ec, 20)
                st.markdown(f"- **{_et}**: {_ec} {_bar}")

        st.divider()

        if st.button("\U0001f4e4 Generate .ics File", type="primary", key="_cal_export_btn", use_container_width=True):
            _ics_content = calendar_events.export_ical(case_id=_export_case)
            _event_count = _ics_content.count("BEGIN:VEVENT")
            st.session_state["_ics_data"] = _ics_content
            st.session_state["_ics_count"] = _event_count
            st.success(f"\u2705 Generated calendar with {_event_count} event(s)!")

        _ics_data = st.session_state.get("_ics_data")
        if _ics_data:
            _fname = f"tlo_calendar_{case_id or 'all'}.ics"
            st.download_button(
                "\U0001f4e5 Download .ics File",
                data=_ics_data,
                file_name=_fname,
                mime="text/calendar",
                key="_ics_download",
                use_container_width=True,
            )
            st.caption(f"Contains {st.session_state.get('_ics_count', 0)} event(s). Import into your preferred calendar application.")

        # Google Calendar connection info
        if _gcal_connected:
            st.divider()
            st.success("\U0001f517 Google Calendar is connected \u2014 new events sync automatically when you check the sync option.")
            if st.button("\U0001f50c Disconnect Google Calendar", key="_gcal_disconnect"):
                google_cal_sync.disconnect(_user_id)
                st.info("Google Calendar disconnected.")
                st.rerun()

        # Past-due events alert
        _past_due = _cal_stats.get("past_due", 0)
        if _past_due:
            st.warning(f"\u26a0\ufe0f {_past_due} event(s) are past due and still marked as 'scheduled'. Consider updating their status.")
