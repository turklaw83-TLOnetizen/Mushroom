"""
email_integration.py -- Gmail API Integration with Manual Approval Queue
Fetches emails via Gmail API, stores in approval queue, user classifies to cases.
No auto-classification -- every email requires manual approval.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data")
_QUEUE_FILE = os.path.join(_DATA_DIR, "email_queue.json")

EMAIL_STATUSES = ["pending", "approved", "dismissed"]


# ---- Queue Management -------------------------------------------------------

def _load_queue() -> List[Dict]:
    if not os.path.exists(_QUEUE_FILE):
        return []
    try:
        with open(_QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_queue(queue: List[Dict]):
    os.makedirs(os.path.dirname(_QUEUE_FILE), exist_ok=True)
    with open(_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False, default=str)


def get_pending_emails() -> List[Dict]:
    """Load emails awaiting classification."""
    return [e for e in _load_queue() if e.get("status") == "pending"]


def get_all_emails(status_filter: str = "") -> List[Dict]:
    """Load all emails, optionally filtered by status."""
    queue = _load_queue()
    if status_filter:
        return [e for e in queue if e.get("status") == status_filter]
    return queue


def add_email_to_queue(
    gmail_id: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    date: str,
    snippet: str = "",
    body: str = "",
    attachments: List[Dict] = None,
    suggested_case_id: str = "",
) -> str:
    """Add a fetched email to the approval queue. Returns queue entry ID."""
    queue = _load_queue()

    # Check for duplicate gmail_id
    existing_ids = {e.get("gmail_id") for e in queue}
    if gmail_id in existing_ids:
        return ""  # Already in queue

    entry_id = uuid.uuid4().hex[:8]
    queue.append({
        "id": entry_id,
        "gmail_id": gmail_id,
        "from": from_addr,
        "to": to_addr,
        "subject": subject,
        "date": date,
        "snippet": snippet,
        "body": body,
        "attachments": attachments or [],
        "status": "pending",
        "suggested_case_id": suggested_case_id,
        "assigned_case_id": "",
        "tags": [],
        "added_at": datetime.now().isoformat(),
        "processed_at": "",
    })
    _save_queue(queue)
    return entry_id


def classify_email(
    email_id: str,
    case_id: str,
    case_mgr=None,
    tags: List[str] = None,
) -> bool:
    """
    Approve an email into a case.
    Saves attachments to case files if case_mgr provided.
    Returns True on success.
    """
    queue = _load_queue()
    for entry in queue:
        if entry.get("id") == email_id:
            entry["status"] = "approved"
            entry["assigned_case_id"] = case_id
            entry["tags"] = tags or []
            entry["processed_at"] = datetime.now().isoformat()

            # Save attachments to case if case_mgr provided
            if case_mgr and entry.get("attachments"):
                for att in entry["attachments"]:
                    att_data = att.get("data")
                    att_name = att.get("filename", "attachment.bin")
                    if att_data and isinstance(att_data, bytes):
                        try:
                            case_mgr.save_file(case_id, att_data, att_name)
                        except Exception as e:
                            logger.warning("Failed to save attachment %s: %s", att_name, e)

            # Log the email body as a contact note
            if case_mgr:
                try:
                    case_mgr.log_activity(
                        case_id,
                        action="email_imported",
                        detail=f"Email from {entry.get('from', '?')}: {entry.get('subject', '')}",
                        category="document",
                    )
                except Exception:
                    pass

            _save_queue(queue)
            return True
    return False


def dismiss_email(email_id: str, reason: str = "") -> bool:
    """Mark an email as not relevant / dismissed. Returns True if found."""
    queue = _load_queue()
    for entry in queue:
        if entry.get("id") == email_id:
            entry["status"] = "dismissed"
            entry["processed_at"] = datetime.now().isoformat()
            if reason:
                entry["dismiss_reason"] = reason
            _save_queue(queue)
            return True
    return False


def get_email_queue_stats() -> Dict:
    """Count of pending, approved, dismissed."""
    queue = _load_queue()
    return {
        "total": len(queue),
        "pending": sum(1 for e in queue if e.get("status") == "pending"),
        "approved": sum(1 for e in queue if e.get("status") == "approved"),
        "dismissed": sum(1 for e in queue if e.get("status") == "dismissed"),
    }


def suggest_case_for_email(from_addr: str, crm_clients: List[Dict]) -> str:
    """
    Try to match sender email to a CRM client, return their linked case_id.
    Returns empty string if no match.
    """
    from_lower = from_addr.lower().strip()
    for client in crm_clients:
        client_email = client.get("email", "").lower().strip()
        if client_email and client_email == from_lower:
            linked = client.get("linked_case_ids", [])
            if linked:
                return linked[0]  # Return first linked case
    return ""


# ---- Gmail API Client -------------------------------------------------------

class GmailClient:
    """Gmail API wrapper. Requires google-api-python-client and valid OAuth credentials."""

    def __init__(self, credentials):
        """Initialize with google.oauth2.credentials.Credentials."""
        try:
            from googleapiclient.discovery import build
            self.service = build("gmail", "v1", credentials=credentials)
        except ImportError:
            raise ImportError(
                "google-api-python-client is required for Gmail integration. "
                "Install with: pip install google-api-python-client google-auth"
            )

    def fetch_recent_emails(self, max_results: int = 50, after_date: str = "") -> List[Dict]:
        """
        Fetch recent emails from inbox.
        Returns list of email summaries with id, from, subject, date, snippet.
        """
        query = "in:inbox"
        if after_date:
            query += f" after:{after_date}"

        try:
            results = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            emails = []
            for msg_meta in messages:
                msg = self.service.users().messages().get(
                    userId="me", id=msg_meta["id"], format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                emails.append({
                    "gmail_id": msg["id"],
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                })

            return emails
        except Exception as e:
            logger.error("Gmail fetch error: %s", e)
            return []

    def get_email_detail(self, email_id: str) -> Dict:
        """Get full email with body text."""
        try:
            msg = self.service.users().messages().get(
                userId="me", id=email_id, format="full"
            ).execute()

            body = _extract_body(msg.get("payload", {}))
            attachments = _extract_attachment_info(msg.get("payload", {}))

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

            return {
                "gmail_id": email_id,
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "body": body,
                "attachments": attachments,
            }
        except Exception as e:
            logger.error("Gmail detail error: %s", e)
            return {}

    def download_attachment(self, email_id: str, attachment_id: str) -> bytes:
        """Download an email attachment. Returns bytes."""
        import base64
        try:
            att = self.service.users().messages().attachments().get(
                userId="me", messageId=email_id, id=attachment_id
            ).execute()
            return base64.urlsafe_b64decode(att.get("data", ""))
        except Exception as e:
            logger.error("Attachment download error: %s", e)
            return b""

    def mark_as_processed(self, email_id: str, label_name: str = "TLO-Processed"):
        """Add a label to mark email as processed."""
        try:
            # Try to find or create the label
            labels = self.service.users().labels().list(userId="me").execute()
            label_id = None
            for lbl in labels.get("labels", []):
                if lbl["name"] == label_name:
                    label_id = lbl["id"]
                    break

            if not label_id:
                label_body = {
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                }
                created = self.service.users().labels().create(userId="me", body=label_body).execute()
                label_id = created["id"]

            self.service.users().messages().modify(
                userId="me", id=email_id,
                body={"addLabelIds": [label_id]},
            ).execute()
        except Exception as e:
            logger.warning("Could not add label: %s", e)


# ---- Gmail Body Extraction Helpers ------------------------------------------

def _extract_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    import base64

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Recurse into multipart
        if part.get("parts"):
            result = _extract_body(part)
            if result:
                return result

    return ""


def _extract_attachment_info(payload: dict) -> List[Dict]:
    """Extract attachment metadata from Gmail message payload."""
    attachments = []
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("filename"):
            attachments.append({
                "filename": part["filename"],
                "mime_type": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId", ""),
            })
        if part.get("parts"):
            attachments.extend(_extract_attachment_info(part))
    return attachments
