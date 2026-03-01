# ---- API Cases Tests -----------------------------------------------------
# Integration tests for the cases router.

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("CLERK_SECRET_KEY", "")

from httpx import AsyncClient, ASGITransport
from api.main import app
from api.auth import _create_jwt


@pytest.fixture
def admin_headers():
    token = _create_jwt(user_id="DJT", role="admin", name="Daniel Turklay")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def attorney_headers():
    token = _create_jwt(user_id="CRJ", role="attorney", name="Cody Johnson")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_check():
    """Health endpoint should be accessible without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Project Mushroom Cloud API"


@pytest.mark.asyncio
async def test_list_cases_unauthorized():
    """Listing cases without auth should return 401/403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/cases")
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_cases_with_auth(admin_headers):
    """Listing cases with valid admin auth should return 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/cases", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # Fix #3: endpoint returns PaginatedResponse, not a plain list
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data
        assert "page" in data


@pytest.mark.asyncio
async def test_create_case(admin_headers):
    """Creating a case should return 201 with case_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/cases",
            json={
                "case_name": "Test v. State",
                "case_type": "criminal",
                "description": "Test case for API",
            },
            headers=admin_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "case_id" in data


@pytest.mark.asyncio
async def test_get_providers():
    """Providers endpoint should return configured LLM providers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/providers")
        assert response.status_code == 200
        data = response.json()
        assert "default_provider" in data
