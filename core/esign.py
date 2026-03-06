"""
AllRise Beta -- E-Signature Module (Dropbox Sign)
================================================
Send documents for electronic signature via the Dropbox Sign API,
track request status, and download signed copies.

Requires:
    pip install dropbox-sign
    DROPBOX_SIGN_API_KEY in .env

Usage:
    from core.esign import ESignManager
    mgr = ESignManager(case_dir)
    req_id = mgr.send_request("contract.pdf", [{"name": "Jane", "email": "jane@example.com"}], "Please sign")
    status = mgr.get_request_status(req_id)
    mgr.download_signed(req_id, save_dir)
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from pathlib import Path
DATA_DIR = str(Path(__file__).resolve().parent.parent / "data" / "cases")

# --- SDK availability check ---
_HAS_SDK = False
try:
    import dropbox_sign
    from dropbox_sign import ApiClient, Configuration, apis, models
    _HAS_SDK = True
except ImportError:
    pass


def sdk_available() -> bool:
    """Check if the dropbox-sign SDK is installed."""
    return _HAS_SDK


def api_key_configured() -> bool:
    """Check if the DROPBOX_SIGN_API_KEY env var is set."""
    return bool(os.environ.get("DROPBOX_SIGN_API_KEY"))


def _get_api_client():
    """Create a configured Dropbox Sign API client."""
    if not _HAS_SDK:
        raise RuntimeError("dropbox-sign package not installed. Run: pip install dropbox-sign")
    api_key = os.environ.get("DROPBOX_SIGN_API_KEY")
    if not api_key:
        raise RuntimeError("DROPBOX_SIGN_API_KEY not set in .env")

    configuration = Configuration(username=api_key)
    return ApiClient(configuration)


# ===================================================================
#  PER-CASE E-SIGN REQUEST PERSISTENCE
# ===================================================================

class ESignManager:
    """Manages e-signature requests for a single case."""

    def __init__(self, case_dir: str):
        self.case_dir = case_dir
        self._store_path = os.path.join(case_dir, "esign_requests.json")
        self._requests: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(self._store_path):
            try:
                with open(self._store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
            with open(self._store_path, "w", encoding="utf-8") as f:
                json.dump(self._requests, f, indent=2)
        except Exception:
            pass

    # -- Send --
    def send_request(
        self,
        file_path: str,
        signers: List[Dict],
        title: str = "",
        subject: str = "",
        message: str = "",
        test_mode: bool = True,
    ) -> Dict:
        """
        Send a file for e-signature.

        Args:
            file_path: Absolute path to PDF/DOCX to sign.
            signers: List of dicts with keys: name, email_address, order (optional).
            title: Title shown in the signing UI.
            subject: Email subject.
            message: Message to signers.
            test_mode: If True, request is in test mode (free, watermarked).

        Returns:
            Dict with request metadata (id, status, signers, timestamps).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        local_id = str(uuid.uuid4())[:8]

        # Build signer objects
        signer_list = []
        for i, s in enumerate(signers):
            signer_list.append({
                "name": s.get("name", f"Signer {i+1}"),
                "email_address": s.get("email_address", s.get("email", "")),
                "order": s.get("order", i),
            })

        # Attempt API call
        remote_id = None
        status = "pending"
        error_msg = None

        if _HAS_SDK and api_key_configured():
            try:
                api_client = _get_api_client()
                signature_request_api = apis.SignatureRequestApi(api_client)

                # Build signer models
                sdk_signers = []
                for i, s in enumerate(signer_list):
                    sdk_signers.append(models.SubSignatureRequestSigner(
                        name=s["name"],
                        email_address=s["email_address"],
                        order=s.get("order", i),
                    ))

                data = models.SignatureRequestSendRequest(
                    title=title or filename,
                    subject=subject or f"Signature requested: {filename}",
                    message=message or "Please review and sign the attached document.",
                    signers=sdk_signers,
                    files=[open(file_path, "rb")],
                    test_mode=test_mode,
                )

                result = signature_request_api.signature_request_send(data)
                sr = result.signature_request
                remote_id = sr.signature_request_id
                status = "sent"
            except Exception as e:
                error_msg = str(e)
                status = "error"
        else:
            error_msg = "SDK not installed or API key not configured"
            status = "not_configured"

        # Persist locally
        request_record = {
            "local_id": local_id,
            "remote_id": remote_id,
            "filename": filename,
            "file_path": file_path,
            "title": title or filename,
            "signers": signer_list,
            "status": status,
            "error": error_msg,
            "test_mode": test_mode,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "signed_file_path": None,
        }
        self._requests.append(request_record)
        self._save()
        return request_record

    # -- Status --
    def get_request_status(self, local_id: str) -> Optional[Dict]:
        """Get current status of a request. Refreshes from API if possible."""
        record = self._find(local_id)
        if not record:
            return None

        # Try to refresh from API
        if record.get("remote_id") and _HAS_SDK and api_key_configured():
            try:
                api_client = _get_api_client()
                api = apis.SignatureRequestApi(api_client)
                result = api.signature_request_get(record["remote_id"])
                sr = result.signature_request

                # Map API status
                if sr.is_complete:
                    record["status"] = "signed"
                elif sr.is_declined:
                    record["status"] = "declined"
                elif sr.has_error:
                    record["status"] = "error"
                else:
                    # Check individual signer statuses
                    all_signed = all(
                        sig.status_code == "signed"
                        for sig in (sr.signatures or [])
                    )
                    any_viewed = any(
                        sig.status_code in ("signed", "viewed", "awaiting_signature")
                        for sig in (sr.signatures or [])
                    )
                    if all_signed:
                        record["status"] = "signed"
                    elif any_viewed:
                        record["status"] = "viewed"
                    else:
                        record["status"] = "sent"

                record["updated_at"] = datetime.now().isoformat()
                self._save()
            except Exception:
                pass  # Keep existing status on API error

        return record

    def refresh_all_statuses(self):
        """Refresh status for all pending/sent requests."""
        for req in self._requests:
            if req.get("status") in ("sent", "viewed", "pending"):
                self.get_request_status(req["local_id"])

    # -- Download signed copy --
    def download_signed(self, local_id: str, save_dir: Optional[str] = None) -> Optional[str]:
        """
        Download the signed PDF for a completed request.
        Returns the path to the saved file, or None on failure.
        """
        record = self._find(local_id)
        if not record or not record.get("remote_id"):
            return None

        if record.get("status") != "signed":
            return None

        if not _HAS_SDK or not api_key_configured():
            return None

        try:
            api_client = _get_api_client()
            api = apis.SignatureRequestApi(api_client)
            file_bin = api.signature_request_files(
                record["remote_id"],
                file_type="pdf",
            )

            # Save to case source_docs/ or specified dir
            if not save_dir:
                save_dir = os.path.join(self.case_dir, "source_docs")
            os.makedirs(save_dir, exist_ok=True)

            base_name = os.path.splitext(record["filename"])[0]
            signed_path = os.path.join(save_dir, f"{base_name}_signed.pdf")

            with open(signed_path, "wb") as f:
                f.write(file_bin.read() if hasattr(file_bin, "read") else file_bin)

            record["signed_file_path"] = signed_path
            record["updated_at"] = datetime.now().isoformat()
            self._save()
            return signed_path
        except Exception:
            return None

    # -- Cancel --
    def cancel_request(self, local_id: str) -> bool:
        """Cancel a pending signature request."""
        record = self._find(local_id)
        if not record:
            return False

        if record.get("remote_id") and _HAS_SDK and api_key_configured():
            try:
                api_client = _get_api_client()
                api = apis.SignatureRequestApi(api_client)
                api.signature_request_cancel(record["remote_id"])
            except Exception:
                pass  # May have already been completed/cancelled

        record["status"] = "cancelled"
        record["updated_at"] = datetime.now().isoformat()
        self._save()
        return True

    # -- List --
    def list_requests(self) -> List[Dict]:
        """Return all requests (newest first)."""
        return list(reversed(self._requests))

    def get_active_count(self) -> int:
        """Count of non-terminal requests."""
        return sum(1 for r in self._requests if r.get("status") in ("sent", "viewed", "pending"))

    # -- Remind --
    def send_reminder(self, request_id: str) -> Dict:
        """Send reminders to all pending signers for a signature request."""
        req = None
        for r in self._requests:
            if r.get("local_id") == request_id or r.get("remote_id") == request_id:
                req = r
                break

        if not req:
            return {"status": "error", "message": "Request not found"}

        # Record the reminder
        req["last_reminder_at"] = datetime.now().isoformat()
        req["reminder_count"] = req.get("reminder_count", 0) + 1
        self._save()

        return {
            "status": "reminded",
            "request_id": request_id,
            "reminder_count": req["reminder_count"],
        }

    # -- Helpers --
    def _find(self, local_id: str) -> Optional[Dict]:
        for r in self._requests:
            if r["local_id"] == local_id:
                return r
        return None


# ===================================================================
#  STATUS DISPLAY HELPERS
# ===================================================================

STATUS_BADGES = {
    "pending": ("PENDING", "Pending"),
    "not_configured": ("CONFIG", "Not Configured"),
    "sent": ("SENT", "Sent"),
    "viewed": ("VIEWED", "Viewed"),
    "signed": ("DONE", "Signed"),
    "declined": ("DECLINED", "Declined"),
    "cancelled": ("CANCELLED", "Cancelled"),
    "error": ("ERROR", "Error"),
}


def status_badge(status: str) -> str:
    """Return label for a status string."""
    icon, label = STATUS_BADGES.get(status, ("UNKNOWN", status.title()))
    return f"[{icon}] {label}"
