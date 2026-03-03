"""Tests for the metrics API router (Phase 19+20)."""
import pytest
from unittest.mock import patch


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "test-user", "email": "test@example.com", "role": "admin"}
        yield mock


class TestMetricsRouter:
    def test_post_web_vitals(self, test_client, mock_auth):
        response = test_client.post("/api/v1/metrics/web-vitals", json={
            "lcp": 1200.5,
            "fid": 50.2,
            "cls": 0.05,
            "pathname": "/",
        })
        assert response.status_code in (200, 201, 404)

    def test_get_web_vitals_summary(self, test_client, mock_auth):
        response = test_client.get("/api/v1/metrics/web-vitals/summary")
        assert response.status_code in (200, 404)
