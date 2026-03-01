"""Tests for the notification service (Phase 14)."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_data_dir(tmp_path):
    with patch.dict("os.environ", {"DATA_DIR": str(tmp_path)}):
        yield tmp_path


class TestNotificationService:
    def test_import(self):
        """NotificationService module can be imported."""
        from core.notification_service import NotificationService
        assert NotificationService is not None

    def test_create_notification(self, tmp_data_dir):
        from core.notification_service import NotificationService
        svc = NotificationService(str(tmp_data_dir))
        notif = svc.create_notification(
            user_id="user-1",
            notification_type="analysis_complete",
            title="Analysis Done",
            message="Your analysis is complete",
        )
        assert notif["id"]
        assert notif["title"] == "Analysis Done"
        assert notif["read"] is False

    def test_get_notifications(self, tmp_data_dir):
        from core.notification_service import NotificationService
        svc = NotificationService(str(tmp_data_dir))
        svc.create_notification("user-1", "info", "Test 1", "Msg 1")
        svc.create_notification("user-1", "info", "Test 2", "Msg 2")
        notifs = svc.get_notifications("user-1")
        assert len(notifs) == 2

    def test_mark_read(self, tmp_data_dir):
        from core.notification_service import NotificationService
        svc = NotificationService(str(tmp_data_dir))
        notif = svc.create_notification("user-1", "info", "Test", "Msg")
        svc.mark_read("user-1", notif["id"])
        notifs = svc.get_notifications("user-1")
        assert notifs[0]["read"] is True

    def test_unread_count(self, tmp_data_dir):
        from core.notification_service import NotificationService
        svc = NotificationService(str(tmp_data_dir))
        svc.create_notification("user-1", "info", "Test 1", "Msg")
        svc.create_notification("user-1", "info", "Test 2", "Msg")
        assert svc.get_unread_count("user-1") == 2
        notifs = svc.get_notifications("user-1")
        svc.mark_read("user-1", notifs[0]["id"])
        assert svc.get_unread_count("user-1") == 1

    def test_delete_notification(self, tmp_data_dir):
        from core.notification_service import NotificationService
        svc = NotificationService(str(tmp_data_dir))
        notif = svc.create_notification("user-1", "info", "Test", "Msg")
        svc.delete_notification("user-1", notif["id"])
        assert len(svc.get_notifications("user-1")) == 0
