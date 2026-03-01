"""Notification service — create, store, query, and manage notifications."""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

NOTIFICATION_TYPES = {
    "deadline_approaching", "deadline_overdue", "analysis_complete",
    "analysis_failed", "case_assigned", "document_uploaded",
    "mention", "system_update", "phase_changed", "file_uploaded",
}

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
EXPIRY_DAYS = 30


class NotificationService:
    """Per-user JSON-file notification storage."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base = (data_dir or DATA_DIR) / "notifications"
        self.base.mkdir(parents=True, exist_ok=True)

    def _user_file(self, user_id: str) -> Path:
        return self.base / f"{user_id}.json"

    def _load(self, user_id: str) -> list[dict]:
        p = self._user_file(user_id)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, user_id: str, notifications: list[dict]):
        p = self._user_file(user_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(notifications, default=str), encoding="utf-8")
        os.replace(tmp, p)

    def create_notification(
        self,
        user_id: str,
        notif_type: str,
        title: str,
        body: str,
        case_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        notif = {
            "id": uuid.uuid4().hex[:12],
            "type": notif_type,
            "title": title,
            "body": body,
            "case_id": case_id,
            "metadata": metadata or {},
            "read": False,
            "created_at": time.time(),
        }
        items = self._load(user_id)
        items.insert(0, notif)
        # Purge expired
        cutoff = time.time() - EXPIRY_DAYS * 86400
        items = [n for n in items if n.get("created_at", 0) > cutoff]
        self._save(user_id, items)
        return notif

    def get_notifications(
        self, user_id: str, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        items = self._load(user_id)
        if unread_only:
            items = [n for n in items if not n.get("read")]
        return items[offset : offset + limit]

    def get_unread_count(self, user_id: str) -> int:
        return sum(1 for n in self._load(user_id) if not n.get("read"))

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        items = self._load(user_id)
        for n in items:
            if n["id"] == notification_id:
                n["read"] = True
                self._save(user_id, items)
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        items = self._load(user_id)
        count = 0
        for n in items:
            if not n.get("read"):
                n["read"] = True
                count += 1
        self._save(user_id, items)
        return count

    def delete_notification(self, user_id: str, notification_id: str) -> bool:
        items = self._load(user_id)
        before = len(items)
        items = [n for n in items if n["id"] != notification_id]
        if len(items) < before:
            self._save(user_id, items)
            return True
        return False


# Singleton
_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
