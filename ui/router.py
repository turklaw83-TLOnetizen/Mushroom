# ---- Page Router ----------------------------------------------------------
# Two-tier dispatcher: Landing Dashboard vs Case View.
# The landing dashboard renders when no case is selected.
# The case view renders the full war room + module tabs when a case is open.

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def route():
    """Route to landing dashboard or case view based on session state.

    Includes RBAC enforcement: non-admin users can only access cases
    listed in their assigned_cases. Admins have unrestricted access.

    Persists case_id/prep_id in URL query params so the browser back button
    and page refreshes don't lose the user's position.
    """
    # --- Restore from URL query params if session state is empty ---
    case_id = st.session_state.get("current_case_id")
    if not case_id:
        qp = st.query_params
        url_case = qp.get("case")
        if url_case:
            st.session_state["current_case_id"] = url_case
            case_id = url_case
            url_prep = qp.get("prep")
            if url_prep:
                st.session_state["current_prep_id"] = url_prep

    # --- Sync session state → URL params ---
    if case_id:
        _qp_update = {"case": case_id}
        prep_id = st.session_state.get("current_prep_id")
        if prep_id:
            _qp_update["prep"] = prep_id
        try:
            st.query_params.update(_qp_update)
        except Exception:
            pass  # Older Streamlit without query_params.update
    else:
        try:
            st.query_params.clear()
        except Exception:
            pass

    if not case_id:
        from ui.case_dashboard import render_dashboard
        render_dashboard()
    else:
        # ---- Case existence check ----
        from ui.shared import get_case_manager
        try:
            if not get_case_manager().case_exists(case_id):
                st.warning(f"Case **{case_id}** no longer exists. Returning to dashboard.")
                st.session_state.current_case_id = None
                st.session_state.current_prep_id = None
                st.session_state.agent_results = None
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.rerun()
        except Exception:
            pass  # If storage check fails, let case_view handle it

        # ---- RBAC Permission Gate ----
        user = st.session_state.get("current_user")
        if user:
            from ui.shared import get_user_manager
            allowed = get_user_manager().get_cases_for_user(user["id"])
            # allowed is None for admins (unrestricted), List[str] for others
            if allowed is not None and case_id not in allowed:
                st.error(
                    "**Access Denied** -- You do not have permission to access this case. "
                    "Contact an administrator to be assigned."
                )
                logger.warning(
                    "RBAC: User %s (%s) denied access to case %s",
                    user.get("name", "?"), user.get("id", "?"), case_id,
                )
                if st.button("Back to Cases"):
                    st.session_state.current_case_id = None
                    st.session_state.current_prep_id = None
                    st.session_state.agent_results = None
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.rerun()
                st.stop()

        from ui.case_view import render_case_view
        render_case_view()
