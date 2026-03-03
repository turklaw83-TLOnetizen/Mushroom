"""Tests for the analysis API router."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_case_manager():
    with patch("api.deps.get_case_manager") as mock:
        cm = MagicMock()
        cm.get_case.return_value = {"id": "case-1", "name": "Test"}
        cm.case_exists.return_value = True
        cm.get_preparation.return_value = {
            "id": "prep-1",
            "type": "trial",
            "results": {
                "case_summary": "Test summary",
                "strategy_notes": "Strategy notes here",
            },
        }
        mock.return_value = cm
        yield cm


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestAnalysisRouter:
    def test_get_analysis_status(self, test_client, mock_case_manager, mock_auth):
        response = test_client.get("/api/v1/cases/case-1/analysis/status")
        assert response.status_code in (200, 404)

    def test_get_preparation_results(self, test_client, mock_case_manager, mock_auth):
        response = test_client.get("/api/v1/cases/case-1/preparations/prep-1")
        assert response.status_code == 200
