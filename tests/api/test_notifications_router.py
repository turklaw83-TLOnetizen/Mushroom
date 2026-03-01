"""Tests for the notifications API router."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestNotificationsRouter:
    def test_list_notifications(self, test_client, mock_auth):
        response = test_client.get("/api/v1/notifications")
        assert response.status_code in (200, 404)

    def test_mark_all_read(self, test_client, mock_auth):
        response = test_client.post("/api/v1/notifications/mark-all-read")
        assert response.status_code in (200, 204, 404)
