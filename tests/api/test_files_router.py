"""Tests for the files API router."""
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO


@pytest.fixture
def mock_case_manager():
    with patch("api.deps.get_case_manager") as mock:
        cm = MagicMock()
        cm.list_files.return_value = [
            {"name": "test.pdf", "size": 1024, "uploaded_at": "2026-01-01T00:00:00"},
            {"name": "evidence.docx", "size": 2048, "uploaded_at": "2026-01-02T00:00:00"},
        ]
        cm.get_case.return_value = {"id": "case-1", "name": "Test"}
        cm.case_exists.return_value = True
        mock.return_value = cm
        yield cm


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestFilesRouter:
    def test_list_files(self, test_client, mock_case_manager, mock_auth):
        response = test_client.get("/api/v1/cases/case-1/files")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_files_empty(self, test_client, mock_case_manager, mock_auth):
        mock_case_manager.list_files.return_value = []
        response = test_client.get("/api/v1/cases/case-1/files")
        assert response.status_code == 200
        assert response.json() == []
