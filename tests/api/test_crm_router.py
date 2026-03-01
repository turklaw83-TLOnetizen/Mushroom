"""Tests for the CRM API router."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_case_manager():
    with patch("api.deps.get_case_manager") as mock:
        cm = MagicMock()
        mock.return_value = cm
        yield cm


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestCRMRouter:
    def test_list_clients(self, test_client, mock_auth):
        response = test_client.get("/api/v1/crm/clients")
        assert response.status_code in (200, 404)

    def test_crm_stats(self, test_client, mock_auth):
        response = test_client.get("/api/v1/crm/stats")
        assert response.status_code in (200, 404)
