"""
google_cal_sync.py -- Google Calendar One-Way Push Sync
Handles OAuth2 flow for Calendar API scope, token storage,
and pushing/updating/deleting events on the user's Google Calendar.

Uses the same client_id/client_secret from .streamlit/secrets.toml [auth].
Stores per-user refresh tokens in data/users/gcal_tokens/{user_id}.json.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

import streamlit as st

logger = logging.getLogger(__name__)

# -- Paths --
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "users", "gcal_tokens")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Manual copy-paste flow for desktop apps


def _ensure_dir():
    os.makedirs(TOKEN_DIR, exist_ok=True)


def _get_client_config() -> Dict:
    """Build client config from Streamlit secrets."""
    try:
        auth = st.secrets.get("auth", {})
        return {
            "installed": {
                "client_id": auth.get("client_id", ""),
                "client_secret": auth.get("client_secret", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        }
    except Exception:
        return {}


def _token_path(user_id: str) -> str:
    _ensure_dir()
    return os.path.join(TOKEN_DIR, f"{user_id}.json")


# -- Connection Status --

def is_connected(user_id: str) -> bool:
    """Check if a user has stored Google Calendar credentials."""
    path = _token_path(user_id)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        return bool(data.get("refresh_token"))
    except Exception:
        return False


def get_connected_email(user_id: str) -> str:
    """Return the Google email associated with the Calendar connection."""
    path = _token_path(user_id)
    if not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return json.load(f).get("email", "")
    except Exception:
        return ""


# -- OAuth2 Flow --

def get_auth_url(user_id: str) -> str:
    """
    Generate an OAuth2 authorization URL for the Calendar API.
    The user visits this URL, grants access, and copies the auth code back.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = _get_client_config()
    if not client_config.get("installed", {}).get("client_id"):
        return ""

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        login_hint=st.session_state.get("current_user", {}).get("google_email", ""),
    )
    # Store flow state for later
    st.session_state[f"_gcal_flow_{user_id}"] = flow
    return auth_url


def handle_callback(user_id: str, auth_code: str, email: str = "") -> bool:
    """
    Exchange the authorization code for tokens and store them.
    Returns True on success.
    """
    flow = st.session_state.get(f"_gcal_flow_{user_id}")
    if not flow:
        # Recreate flow
        from google_auth_oauthlib.flow import InstalledAppFlow
        client_config = _get_client_config()
        if not client_config.get("installed", {}).get("client_id"):
            return False
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = REDIRECT_URI

    try:
        flow.fetch_token(code=auth_code)
        creds = flow.credentials

        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES),
            "email": email,
            "connected_at": datetime.now().isoformat(),
        }

        path = _token_path(user_id)
        with open(path, "w") as f:
            json.dump(token_data, f, indent=2)

        # Clean up session state
        st.session_state.pop(f"_gcal_flow_{user_id}", None)
        logger.info("Google Calendar connected for user %s", user_id)
        return True
    except Exception as e:
        logger.error("Failed to complete Google Calendar OAuth: %s", e)
        return False


def disconnect(user_id: str) -> bool:
    """Remove stored credentials for a user."""
    path = _token_path(user_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# -- Calendar Service --

def _get_service(user_id: str):
    """Build an authorized Google Calendar API service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    path = _token_path(user_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path) as f:
            data = json.load(f)

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", SCOPES),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Save refreshed token
            data["token"] = creds.token
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.error("Failed to build Calendar service for user %s: %s", user_id, e)
        return None


# -- Push / Update / Delete --

def _build_gcal_body(event: Dict) -> Dict:
    """Convert a local event dict into a Google Calendar event body."""
    body: Dict = {
        "summary": event.get("title", ""),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
    }

    event_date = event.get("date", event.get("event_date", ""))
    start_time = event.get("time", "")
    end_time = event.get("end_time", "")

    if event_date and start_time:
        # Timed event
        body["start"] = {"dateTime": f"{event_date}T{start_time}:00", "timeZone": "America/Chicago"}
        if end_time:
            body["end"] = {"dateTime": f"{event_date}T{end_time}:00", "timeZone": "America/Chicago"}
        else:
            # Default 1-hour duration
            body["end"] = {"dateTime": f"{event_date}T{start_time}:00", "timeZone": "America/Chicago"}
    elif event_date:
        # All-day event
        body["start"] = {"date": event_date}
        body["end"] = {"date": event_date}

    # Add case/client info to description
    extras = []
    if event.get("case_id"):
        extras.append(f"Case: {event['case_id']}")
    if event.get("client_id"):
        extras.append(f"Client ID: {event['client_id']}")
    if event.get("event_type"):
        extras.append(f"Type: {event['event_type']}")
    if extras:
        prefix = " | ".join(extras)
        body["description"] = f"[{prefix}]\n\n{body.get('description', '')}"

    # Color mapping (Google Calendar color IDs)
    _type_to_color = {
        "Court Date": "11",       # Tomato
        "Filing Deadline": "6",   # Tangerine
        "Client Meeting": "9",    # Blueberry
        "Deposition": "3",        # Grape
        "Mediation": "7",         # Peacock
        "Consultation": "10",     # Basil
        "Internal": "8",          # Graphite
    }
    color_id = _type_to_color.get(event.get("event_type", ""))
    if color_id:
        body["colorId"] = color_id

    return body


def push_event(user_id: str, event: Dict) -> Optional[str]:
    """
    Create an event on the user's primary Google Calendar.
    Returns the Google event ID on success, None on failure.
    """
    service = _get_service(user_id)
    if not service:
        return None

    body = _build_gcal_body(event)
    try:
        result = service.events().insert(calendarId="primary", body=body).execute()
        google_id = result.get("id", "")
        logger.info("Pushed event to Google Calendar: %s -> %s", event.get("title"), google_id)
        return google_id
    except Exception as e:
        logger.error("Failed to push event to Google Calendar: %s", e)
        return None


def update_gcal_event(user_id: str, google_event_id: str, event: Dict) -> bool:
    """Update an existing Google Calendar event. Returns True on success."""
    service = _get_service(user_id)
    if not service or not google_event_id:
        return False

    body = _build_gcal_body(event)
    try:
        service.events().update(
            calendarId="primary",
            eventId=google_event_id,
            body=body,
        ).execute()
        logger.info("Updated Google Calendar event: %s", google_event_id)
        return True
    except Exception as e:
        logger.error("Failed to update Google Calendar event %s: %s", google_event_id, e)
        return False


def delete_gcal_event(user_id: str, google_event_id: str) -> bool:
    """Delete a Google Calendar event. Returns True on success."""
    service = _get_service(user_id)
    if not service or not google_event_id:
        return False

    try:
        service.events().delete(calendarId="primary", eventId=google_event_id).execute()
        logger.info("Deleted Google Calendar event: %s", google_event_id)
        return True
    except Exception as e:
        logger.error("Failed to delete Google Calendar event %s: %s", google_event_id, e)
        return False


def cancel_gcal_event(user_id: str, google_event_id: str) -> bool:
    """Mark a Google Calendar event as cancelled."""
    service = _get_service(user_id)
    if not service or not google_event_id:
        return False

    try:
        service.events().patch(
            calendarId="primary",
            eventId=google_event_id,
            body={"status": "cancelled"},
        ).execute()
        logger.info("Cancelled Google Calendar event: %s", google_event_id)
        return True
    except Exception as e:
        logger.error("Failed to cancel Google Calendar event %s: %s", google_event_id, e)
        return False
