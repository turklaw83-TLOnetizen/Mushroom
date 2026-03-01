"""Tests for health and system endpoints."""
import pytest


class TestHealthEndpoints:
    def test_root(self, test_client):
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Project Mushroom Cloud"
        assert "version" in data
        assert data["status"] == "running"

    def test_health_check(self, test_client):
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "database" in data
        assert "llm" in data

    def test_config_providers(self, test_client):
        response = test_client.get("/api/v1/config/providers")
        assert response.status_code == 200
        data = response.json()
        assert "default_provider" in data
        assert "providers" in data

    def test_api_key_status(self, test_client):
        response = test_client.get("/api/v1/config/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "anthropic" in data["providers"]
