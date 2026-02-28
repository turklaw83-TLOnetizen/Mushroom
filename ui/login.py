# ---- Authentication / Login Gate ------------------------------------------
# Handles Google OIDC and PIN-based authentication.

import logging

import streamlit as st

from ui.shared import get_user_manager, init_session_state

logger = logging.getLogger(__name__)


def check_login() -> bool:
    """
    Run the login gate. Returns True if user is authenticated, False otherwise.
    When False, this function renders the login UI and calls st.stop().
    """
    init_session_state()
    user_mgr = get_user_manager()

    # Already logged in?
    if st.session_state.current_user is not None:
        return True

    # ---- Path A: Google OIDC auto-match ----
    google_configured = False
    try:
        google_configured = bool(st.secrets.get("auth", {}).get("client_id", ""))
    except Exception:
        pass

    if google_configured and st.user.is_logged_in:
        matched_user = user_mgr.find_by_google_email(st.user.email)
        if matched_user:
            st.session_state.current_user = matched_user
            st.session_state.login_method = "google"
            user_mgr.record_login(matched_user["id"])
            st.rerun()
        else:
            # Unauthorized Google account
            st.markdown("""<div style='text-align:center; padding: 80px 20px;'>
                <h2 style='margin:0;'>Access Denied</h2>
                <p style='opacity:0.7; margin:8px 0 24px;'>Your Google account is not authorized.<br>
                Contact your administrator to link your Google email to a profile.</p>
            </div>""", unsafe_allow_html=True)
            if st.button("Back to Login", use_container_width=True):
                st.logout()
            st.stop()
            return False

    # ---- Path B: Login page ----
    st.markdown("""<div style='text-align:center; padding: 60px 20px 20px;'>
        <h1 style='margin:0; font-size:2.2rem;'>AllRise Beta</h1>
        <p style='opacity:0.6; font-size:1rem; margin:4px 0 32px;'>Legal Intelligence Suite</p>
    </div>""", unsafe_allow_html=True)

    if google_configured:
        tab_google, tab_pin = st.tabs(["Sign in with Google", "Sign in with PIN"])
    else:
        tab_pin = st.container()
        tab_google = None

    # Google tab
    if tab_google is not None:
        with tab_google:
            st.markdown("""<div style='text-align:center; padding:24px 0;'>
                <p style='opacity:0.6;'>Sign in with your authorized Google account.</p>
            </div>""", unsafe_allow_html=True)
            st.button("Sign in with Google", on_click=st.login,
                       use_container_width=True, type="primary")

    # PIN tab
    with tab_pin:
        users = user_mgr.list_users()
        if not users:
            st.error("No user profiles found. Check data/users/profiles.json")
            st.stop()
            return False

        user_names = [u["name"] for u in users]
        selected_name = st.selectbox("Select your profile", user_names, key="_login_select")
        selected_user = next((u for u in users if u["name"] == selected_name), None)

        if selected_user:
            has_pin = bool(selected_user.get("pin_hash", ""))
            if has_pin:
                pin_input = st.text_input("Enter PIN", type="password",
                                           max_chars=6, key="_login_pin")
            else:
                pin_input = ""

            if st.button("Sign In", use_container_width=True, type="primary"):
                if user_mgr.authenticate(selected_user["id"], pin_input):
                    st.session_state.current_user = selected_user
                    st.session_state.login_method = "pin"
                    user_mgr.record_login(selected_user["id"])
                    st.rerun()
                else:
                    st.error("Incorrect PIN")

    st.stop()
    return False
