# ---- AllRise Beta Legal Intelligence Suite ----------------------------------
# Main Streamlit entry point.
#
# This file is intentionally small (~80 lines). All logic lives in:
#   ui/    -- UI components (splash, login, navigation, router, shared, theme)
#   core/  -- Business logic (case_manager, llm, nodes, storage, export, etc.)
#
# Run with:  streamlit run app.py

import logging
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ---- Bootstrap -----------------------------------------------------------
# Ensure project root is on sys.path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env before any local imports that read environment variables
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(str(_ENV_PATH))

# Configure logging (ASCII-only, no emoji)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("allrise_beta")

# ---- Page Config ---------------------------------------------------------
st.set_page_config(
    page_title="AllRise Beta",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Splash Screen -------------------------------------------------------
from ui.splash import render_splash
render_splash()

# ---- Theme ---------------------------------------------------------------
from ui.shared import init_session_state
init_session_state()

# ---- Encryption Gate -----------------------------------------------------
from core.storage.encrypted_backend import (
    is_encryption_enabled,
    verify_passphrase,
    derive_encryption_key,
    get_or_create_salt,
)

_DATA_DIR = str(_PROJECT_ROOT / "data")
if is_encryption_enabled(_DATA_DIR) and "_encryption_key" not in st.session_state:
    st.markdown("### Data Encryption Active")
    st.info("Your data is encrypted at rest. Enter your passphrase to unlock.")
    _passphrase = st.text_input("Encryption passphrase:", type="password", key="_unlock_passphrase")
    if st.button("Unlock", type="primary"):
        if _passphrase and verify_passphrase(_DATA_DIR, _passphrase):
            _salt = get_or_create_salt(_DATA_DIR)
            st.session_state._encryption_key = derive_encryption_key(_passphrase, _salt)
            st.rerun()
        else:
            st.error("Incorrect passphrase. Please try again.")
    st.stop()

from ui.theme import get_theme_css
st.markdown(get_theme_css(st.session_state.theme), unsafe_allow_html=True)

# ---- Authentication Gate -------------------------------------------------
from ui.login import check_login
if not check_login():
    st.stop()

# ---- Deadline Toast Notifications ----------------------------------------
if "_deadline_toasts_shown" not in st.session_state:
    st.session_state._deadline_toasts_shown = True
    try:
        from ui.shared import get_case_manager
        _dm = get_case_manager()
        _urgent_deadlines = [
            d for d in _dm.get_all_deadlines()
            if d.get("days_remaining", 999) <= 3
        ]
        for _ud in _urgent_deadlines[:5]:  # cap at 5 toasts
            _ud_days = _ud.get("days_remaining", 999)
            _ud_label = _ud.get("label", "Untitled")
            _ud_case = _ud.get("case_name", "")
            if _ud_days < 0:
                st.toast(f"OVERDUE: {_ud_label} ({_ud_case}) -- {abs(_ud_days)}d overdue", icon="\U0001f6a8")
            elif _ud_days == 0:
                st.toast(f"DUE TODAY: {_ud_label} ({_ud_case})", icon="\U0001f534")
            elif _ud_days == 1:
                st.toast(f"Due TOMORROW: {_ud_label} ({_ud_case})", icon="\U0001f7e0")
            else:
                st.toast(f"Due in {_ud_days}d: {_ud_label} ({_ud_case})", icon="\U0001f7e1")
    except Exception:
        pass

# ---- Main Application ----------------------------------------------------
from ui.navigation import render_sidebar
from ui.router import route

# Render sidebar (no return value — nav moved into case view)
render_sidebar()

# Route to landing dashboard or case view
route()
