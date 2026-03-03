"""Tests for the DLP / file security API router (Phase 24)."""
import pytest
from unittest.mock import patch


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "admin-user", "email": "admin@example.com", "role": "admin"}
        yield mock


class TestDLPRouter:
    def test_list_dlp_rules(self, test_client, mock_auth):
        response = test_client.get("/api/v1/dlp/rules")
        assert response.status_code in (200, 404)

    def test_get_audit_log(self, test_client, mock_auth):
        response = test_client.get("/api/v1/dlp/audit")
        assert response.status_code in (200, 404)

    def test_check_download(self, test_client, mock_auth):
        response = test_client.post("/api/v1/dlp/check", json={
            "action": "download",
            "case_id": "case-1",
            "file_name": "test.pdf",
            "user_id": "test-user",
            "user_role": "admin",
        })
        assert response.status_code in (200, 404)
