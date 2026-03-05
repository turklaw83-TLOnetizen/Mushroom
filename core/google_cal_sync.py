"""
google_cal_sync.py -- Google Calendar Sync
Handles OAuth2 flow for Calendar API scope, token storage,
calendar listing/selection, and pushing/updating/deleting events.

Reads OAuth client credentials from env vars:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

Stores per-user refresh tokens in data/users/gcal_tokens/{user_id}.json.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# -- Paths --
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "users", "gcal_tokens")
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Manual copy-paste flow

# Default user ID when caller doesn't specify (single-tenant deployment)
_DEFAULT_USER = "default"


def _ensure_dir():
    os.makedirs(TOKEN_DIR, exist_ok=True)


def _get_client_config() -> Dict:
    """Build OAuth client config from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return {}
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def _token_path(user_id: str = _DEFAULT_USER) -> str:
    _ensure_dir()
    return os.path.join(TOKEN_DIR, f"{user_id}.json")


def _load_token_data(user_id: str = _DEFAULT_USER) -> Dict:
    """Load stored token data for a user."""
    path = _token_path(user_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_token_data(data: Dict, user_id: str = _DEFAULT_USER):
    """Save token data for a user."""
    path = _token_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -- Connection Status --

def is_connected(user_id: str = _DEFAULT_USER) -> bool:
    """Check if a user has stored Google Calendar credentials."""
    data = _load_token_data(user_id)
    return bool(data.get("refresh_token"))


def get_connected_email(user_id: str = _DEFAULT_USER) -> str:
    """Return the Google email associated with the Calendar connection."""
    data = _load_token_data(user_id)
    return data.get("email", "")


def get_sync_status(user_id: str = _DEFAULT_USER) -> Dict:
    """Return connection status, email, and selected calendar for the API."""
    connected = is_connected(user_id)
    data = _load_token_data(user_id)
    return {
        "connected": connected,
        "email": data.get("email", ""),
        "calendar_id": data.get("target_calendar_id", "primary"),
        "calendar_name": data.get("target_calendar_name", "Primary"),
        "connected_at": data.get("connected_at", ""),
        "has_credentials": bool(os.environ.get("GOOGLE_CLIENT_ID")),
    }


# -- OAuth2 Flow --

def initiate_oauth(user_id: str = _DEFAULT_USER) -> str:
    """Generate an OAuth2 authorization URL. Alias for get_auth_url."""
    return get_auth_url(user_id)


def get_auth_url(user_id: str = _DEFAULT_USER) -> str:
    """
    Generate an OAuth2 authorization URL for the Calendar API.
    The user visits this URL, grants access, and copies the auth code back.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error("google_auth_oauthlib not installed")
        return ""

    client_config = _get_client_config()
    if not client_config.get("installed", {}).get("client_id"):
        return ""

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def handle_callback(user_id: str, auth_code: str, email: str = "") -> bool:
    """
    Exchange the authorization code for tokens and store them.
    Returns True on success.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error("google_auth_oauthlib not installed")
        return False

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
            "target_calendar_id": "primary",
            "target_calendar_name": "Primary",
        }

        _save_token_data(token_data, user_id)
        logger.info("Google Calendar connected for user %s", user_id)
        return True
    except Exception as e:
        logger.error("Failed to complete Google Calendar OAuth: %s", e)
        return False


def disconnect(user_id: str = _DEFAULT_USER) -> bool:
    """Remove stored credentials for a user."""
    path = _token_path(user_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# -- Calendar Service --

def _get_service(user_id: str = _DEFAULT_USER):
    """Build an authorized Google Calendar API service."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("google-api-python-client or google-auth not installed")
        return None

    data = _load_token_data(user_id)
    if not data.get("refresh_token"):
        return None

    try:
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
            data["token"] = creds.token
            _save_token_data(data, user_id)

        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.error("Failed to build Calendar service for user %s: %s", user_id, e)
        return None


# -- Calendar List & Selection --

def get_target_calendar(user_id: str = _DEFAULT_USER) -> str:
    """Get the selected target calendar ID (defaults to 'primary')."""
    data = _load_token_data(user_id)
    return data.get("target_calendar_id", "primary")


def set_target_calendar(user_id: str, calendar_id: str, calendar_name: str = "") -> bool:
    """Save the selected target calendar ID."""
    data = _load_token_data(user_id)
    if not data:
        return False
    data["target_calendar_id"] = calendar_id
    data["target_calendar_name"] = calendar_name
    _save_token_data(data, user_id)
    logger.info("Set target calendar for user %s: %s (%s)", user_id, calendar_id, calendar_name)
    return True


def list_calendars(user_id: str = _DEFAULT_USER) -> List[Dict]:
    """List all calendars the user has access to."""
    service = _get_service(user_id)
    if not service:
        return []

    try:
        result = service.calendarList().list().execute()
        calendars = []
        for item in result.get("items", []):
            calendars.append({
                "id": item.get("id", ""),
                "summary": item.get("summary", ""),
                "description": item.get("description", ""),
                "primary": item.get("primary", False),
                "access_role": item.get("accessRole", ""),
                "background_color": item.get("backgroundColor", ""),
            })
        return calendars
    except Exception as e:
        logger.error("Failed to list calendars for user %s: %s", user_id, e)
        return []


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
        body["start"] = {"dateTime": f"{event_date}T{start_time}:00", "timeZone": "America/Chicago"}
        if end_time:
            body["end"] = {"dateTime": f"{event_date}T{end_time}:00", "timeZone": "America/Chicago"}
        else:
            body["end"] = {"dateTime": f"{event_date}T{start_time}:00", "timeZone": "America/Chicago"}
    elif event_date:
        body["start"] = {"date": event_date}
        body["end"] = {"date": event_date}

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

    _type_to_color = {
        "Court Date": "11",
        "Filing Deadline": "6",
        "Client Meeting": "9",
        "Deposition": "3",
        "Mediation": "7",
        "Consultation": "10",
        "Internal": "8",
    }
    color_id = _type_to_color.get(event.get("event_type", ""))
    if color_id:
        body["colorId"] = color_id

    return body


def push_event(user_id: str, event: Dict) -> Optional[str]:
    """
    Create an event on the user's selected Google Calendar.
    Returns the Google event ID on success, None on failure.
    """
    service = _get_service(user_id)
    if not service:
        return None

    calendar_id = get_target_calendar(user_id)
    body = _build_gcal_body(event)
    try:
        result = service.events().insert(calendarId=calendar_id, body=body).execute()
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

    calendar_id = get_target_calendar(user_id)
    body = _build_gcal_body(event)
    try:
        service.events().update(
            calendarId=calendar_id,
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

    calendar_id = get_target_calendar(user_id)
    try:
        service.events().delete(calendarId=calendar_id, eventId=google_event_id).execute()
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

    calendar_id = get_target_calendar(user_id)
    try:
        service.events().patch(
            calendarId=calendar_id,
            eventId=google_event_id,
            body={"status": "cancelled"},
        ).execute()
        logger.info("Cancelled Google Calendar event: %s", google_event_id)
        return True
    except Exception as e:
        logger.error("Failed to cancel Google Calendar event %s: %s", google_event_id, e)
        return False


# -- Sync & List --

def sync_events(
    user_id: str = _DEFAULT_USER,
    case_id: Optional[str] = None,
    direction: str = "both",
) -> Dict:
    """
    Push local events to Google Calendar.
    Returns a summary of pushed/skipped/failed counts.
    """
    from core.calendar_events import load_events

    events = load_events()
    if case_id:
        events = [e for e in events if e.get("case_id") == case_id]

    pushed, skipped, failed = 0, 0, 0
    for evt in events:
        if evt.get("google_event_id"):
            skipped += 1
            continue
        google_id = push_event(user_id, evt)
        if google_id:
            pushed += 1
        else:
            failed += 1

    return {"pushed": pushed, "skipped": skipped, "failed": failed, "total": len(events)}


def list_upcoming_events(
    user_id: str = _DEFAULT_USER,
    days_ahead: int = 30,
) -> List[Dict]:
    """List upcoming events from the user's Google Calendar."""
    service = _get_service(user_id)
    if not service:
        return []

    calendar_id = get_target_calendar(user_id)
    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            timeMax=end,
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        items = []
        for item in result.get("items", []):
            start = item.get("start", {})
            items.append({
                "google_id": item.get("id", ""),
                "title": item.get("summary", ""),
                "date": start.get("date", start.get("dateTime", "")[:10]),
                "time": start.get("dateTime", "")[11:16] if "dateTime" in start else "",
                "location": item.get("location", ""),
                "description": item.get("description", ""),
                "status": item.get("status", ""),
            })
        return items
    except Exception as e:
        logger.error("Failed to list upcoming Google Calendar events: %s", e)
        return []
