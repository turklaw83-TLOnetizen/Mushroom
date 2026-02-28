"""
tasks_ui.py -- Task Assignment System UI
Task board view with create, filter, and status management.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

_DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data")


def render(case_id=None, case_mgr=None, **kwargs):
    """Render the task management interface."""
    from core.tasks import (
        add_task, load_tasks, update_task, delete_task,
        get_task_stats, TASK_STATUSES, TASK_PRIORITIES, TASK_CATEGORIES,
    )
    from ui.shared import get_user_manager, get_current_user

    if not case_id:
        st.info("Open a case to manage tasks.")
        return

    st.markdown("### \u2611\ufe0f Task Board")

    # Stats bar
    stats = get_task_stats(_DATA_DIR, case_id)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total", stats["total"])
    s2.metric("Pending", stats["pending"])
    s3.metric("In Progress", stats["in_progress"])
    s4.metric("Completed", stats["completed"])
    s5.metric("Overdue", stats["overdue"])

    st.divider()

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        _status_filter = st.selectbox(
            "Status", ["All"] + TASK_STATUSES,
            key="_task_status_filter",
        )
    with f2:
        _priority_filter = st.selectbox(
            "Priority", ["All"] + TASK_PRIORITIES,
            key="_task_priority_filter",
        )
    with f3:
        # User filter
        um = get_user_manager()
        users = um.list_users()
        user_names = {u["id"]: u.get("name", u["id"]) for u in users}
        user_options = ["All"] + [u["id"] for u in users]
        _assignee_filter = st.selectbox(
            "Assignee",
            user_options,
            format_func=lambda x: user_names.get(x, x) if x != "All" else "All",
            key="_task_assignee_filter",
        )

    # Load filtered tasks
    tasks = load_tasks(
        _DATA_DIR, case_id,
        status_filter=_status_filter if _status_filter != "All" else None,
        assigned_to=_assignee_filter if _assignee_filter != "All" else None,
        priority_filter=_priority_filter if _priority_filter != "All" else None,
    )

    # Create task form
    with st.expander("\u2795 **Create New Task**", expanded=False):
        _t_col1, _t_col2 = st.columns(2)
        with _t_col1:
            _t_title = st.text_input("Title *", key="_task_title")
            _t_category = st.selectbox("Category", TASK_CATEGORIES, key="_task_cat")
            _t_priority = st.selectbox("Priority", TASK_PRIORITIES, index=1, key="_task_pri")
        with _t_col2:
            _t_assignee = st.selectbox(
                "Assign to",
                [u["id"] for u in users],
                format_func=lambda x: user_names.get(x, x),
                key="_task_assignee",
            )
            _t_due = st.date_input(
                "Due date",
                value=datetime.now().date() + timedelta(days=7),
                key="_task_due",
            )
        _t_desc = st.text_area("Description", key="_task_desc", height=80)

        if st.button("\u2795 Create Task", type="primary", disabled=not _t_title):
            current_user = get_current_user()
            add_task(
                _DATA_DIR, case_id,
                title=_t_title,
                description=_t_desc,
                assigned_to=_t_assignee,
                assigned_by=current_user.get("id", "") if current_user else "",
                priority=_t_priority,
                due_date=str(_t_due),
                category=_t_category,
            )
            st.toast(f"\u2705 Task created: {_t_title}")
            st.rerun()

    # Task list
    if not tasks:
        st.info("No tasks found. Create one above!")
        return

    _priority_icons = {"urgent": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
    _status_icons = {"pending": "\u23f3", "in_progress": "\U0001f504", "completed": "\u2705", "cancelled": "\u274c"}
    today = datetime.now().strftime("%Y-%m-%d")

    for task in tasks:
        _tid = task.get("id", "")
        _is_overdue = (
            task.get("due_date", "") and task["due_date"] < today
            and task.get("status") not in ("completed", "cancelled")
        )

        with st.container(border=True):
            _tc1, _tc2, _tc3, _tc4 = st.columns([0.4, 0.2, 0.2, 0.2])
            with _tc1:
                _pri_icon = _priority_icons.get(task.get("priority", ""), "")
                _overdue_tag = " \U0001f6a8 **OVERDUE**" if _is_overdue else ""
                st.markdown(
                    f"{_pri_icon} **{task.get('title', 'Untitled')}**{_overdue_tag}"
                )
                if task.get("description"):
                    st.caption(task["description"][:100])
            with _tc2:
                _assignee_name = user_names.get(task.get("assigned_to", ""), task.get("assigned_to", ""))
                st.caption(f"\U0001f464 {_assignee_name}")
                if task.get("due_date"):
                    st.caption(f"\U0001f4c5 {task['due_date']}")
            with _tc3:
                _new_status = st.selectbox(
                    "Status",
                    TASK_STATUSES,
                    index=TASK_STATUSES.index(task.get("status", "pending")),
                    key=f"_ts_{_tid}",
                    label_visibility="collapsed",
                )
                if _new_status != task.get("status"):
                    update_task(_DATA_DIR, case_id, _tid, {"status": _new_status})
                    st.rerun()
            with _tc4:
                st.caption(f"`{task.get('category', '')}`")
                if st.button("\U0001f5d1\ufe0f", key=f"_tdel_{_tid}", help="Delete task"):
                    delete_task(_DATA_DIR, case_id, _tid)
                    st.toast("Task deleted")
                    st.rerun()
