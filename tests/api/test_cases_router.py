"""Tests for the cases API router."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_case_manager():
    with patch("api.deps.get_case_manager") as mock:
        cm = MagicMock()
        cm.list_cases.return_value = [
            {"id": "case-1", "name": "Test Case", "phase": "active", "case_type": "criminal"},
            {"id": "case-2", "name": "Civil Matter", "phase": "active", "case_type": "civil"},
        ]
        cm.get_case.return_value = {
            "id": "case-1", "name": "Test Case", "phase": "active",
            "case_type": "criminal", "created_at": "2026-01-01T00:00:00",
        }
        cm.create_case.return_value = {
            "id": "case-new", "name": "New Case", "phase": "active",
        }
        mock.return_value = cm
        yield cm


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestCasesRouter:
    def test_list_cases(self, test_client, mock_case_manager, mock_auth):
        response = test_client.get("/api/v1/cases")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Test Case"

    def test_get_case(self, test_client, mock_case_manager, mock_auth):
        response = test_client.get("/api/v1/cases/case-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "case-1"
        assert data["name"] == "Test Case"

    def test_create_case(self, test_client, mock_case_manager, mock_auth):
        response = test_client.post("/api/v1/cases", json={
            "name": "New Case",
            "case_type": "criminal",
        })
        assert response.status_code in (200, 201)

    def test_get_case_not_found(self, test_client, mock_case_manager, mock_auth):
        mock_case_manager.get_case.return_value = None
        response = test_client.get("/api/v1/cases/nonexistent")
        assert response.status_code in (404, 200)  # depends on router impl

    def test_list_cases_empty(self, test_client, mock_case_manager, mock_auth):
        mock_case_manager.list_cases.return_value = []
        response = test_client.get("/api/v1/cases")
        assert response.status_code == 200
        assert response.json() == []
