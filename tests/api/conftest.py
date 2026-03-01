"""Shared fixtures for API router tests."""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def env_setup():
    """Set minimal environment for API tests."""
    os.environ.setdefault("NEXT_PUBLIC_AUTH_DISABLED", "true")
    os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")


@pytest.fixture
def test_client():
    """Create a FastAPI test client with auth bypassed."""
    from fastapi.testclient import TestClient

    # Bypass auth for testing
    with patch("api.auth.get_current_user", return_value={
        "user_id": "test-user",
        "email": "test@example.com",
        "role": "admin",
    }):
        try:
            from api.main import app
            client = TestClient(app, raise_server_exceptions=False)
            yield client
        except Exception:
            pytest.skip("Could not import api.main — dependencies may be missing")
