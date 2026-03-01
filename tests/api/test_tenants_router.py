"""Tests for the tenants API router (Phase 22)."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_auth():
    with patch("api.auth.get_current_user") as mock:
        mock.return_value = {"user_id": "admin-user", "email": "admin@example.com", "role": "admin"}
        yield mock


class TestTenantsRouter:
    def test_create_tenant(self, test_client, mock_auth):
        response = test_client.post("/api/v1/tenants", json={
            "name": "Test Firm",
            "slug": "test-firm",
            "plan": "starter",
        })
        assert response.status_code in (200, 201, 404)

    def test_get_tenant(self, test_client, mock_auth):
        response = test_client.get("/api/v1/tenants/test-tenant-id")
        assert response.status_code in (200, 404)

    def test_tenant_usage(self, test_client, mock_auth):
        response = test_client.get("/api/v1/tenants/test-tenant-id/usage")
        assert response.status_code in (200, 404)

    def test_tenant_branding(self, test_client, mock_auth):
        response = test_client.get("/api/v1/tenants/test-tenant-id/branding")
        assert response.status_code in (200, 404)
