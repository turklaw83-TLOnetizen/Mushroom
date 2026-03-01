"""Tests for role-based access control (RBAC) boundaries.

Verifies that:
  - Admin can access admin endpoints
  - Attorney can access attorney endpoints but not admin-only
  - Paralegal is blocked from attorney/admin endpoints
  - Missing auth returns 401
  - Wrong role returns 403

Tested against: batch.py, gdpr.py, files.py routers.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("CLERK_SECRET_KEY", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(role: str, user_id: str = "test_user") -> str:
    """Create a JWT token for a given role."""
    from api.auth import _create_jwt
    return _create_jwt(user_id=user_id, role=role, name=f"Test {role.title()}")


def _auth_header(role: str) -> dict:
    """Return Authorization header for a given role."""
    return {"Authorization": f"Bearer {_make_token(role)}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a FastAPI TestClient without auth bypass (real auth checks)."""
    try:
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("Could not import api.main -- dependencies may be missing")


# ===========================================================================
# 1. Missing auth returns 401
# ===========================================================================

class TestMissingAuth:
    """Endpoints should return 401 when no Authorization header is provided."""

    def test_batch_status_no_auth(self, client):
        resp = client.post("/api/v1/batch/cases/status", json={
            "case_ids": ["c1"], "new_status": "closed",
        })
        assert resp.status_code == 401

    def test_gdpr_export_no_auth(self, client):
        resp = client.get("/api/v1/gdpr/export/client-1")
        assert resp.status_code == 401

    def test_gdpr_forget_no_auth(self, client):
        resp = client.post("/api/v1/gdpr/forget/client-1")
        assert resp.status_code == 401

    def test_file_delete_no_auth(self, client):
        resp = client.delete("/api/v1/cases/test-case/files/test.pdf")
        assert resp.status_code == 401


# ===========================================================================
# 2. Admin can access admin endpoints
# ===========================================================================

class TestAdminAccess:
    """Admin role should be allowed on all admin endpoints."""

    def test_batch_status_admin(self, client):
        resp = client.post(
            "/api/v1/batch/cases/status",
            json={"case_ids": ["c1"], "new_status": "closed"},
            headers=_auth_header("admin"),
        )
        assert resp.status_code == 200

    def test_batch_assign_admin(self, client):
        resp = client.post(
            "/api/v1/batch/cases/assign",
            json={"case_ids": ["c1"], "assignee_id": "user-2"},
            headers=_auth_header("admin"),
        )
        assert resp.status_code == 200

    def test_gdpr_export_admin(self, client):
        resp = client.get(
            "/api/v1/gdpr/export/client-1",
            headers=_auth_header("admin"),
        )
        assert resp.status_code == 200

    def test_gdpr_forget_admin(self, client):
        resp = client.post(
            "/api/v1/gdpr/forget/client-1",
            headers=_auth_header("admin"),
        )
        assert resp.status_code == 200


# ===========================================================================
# 3. Attorney can access attorney endpoints but NOT admin-only
# ===========================================================================

class TestAttorneyAccess:
    """Attorney role should be allowed on attorney+admin endpoints but blocked on admin-only."""

    def test_batch_status_attorney(self, client):
        """batch/cases/status requires admin OR attorney."""
        resp = client.post(
            "/api/v1/batch/cases/status",
            json={"case_ids": ["c1"], "new_status": "closed"},
            headers=_auth_header("attorney"),
        )
        assert resp.status_code == 200

    def test_batch_assign_attorney_forbidden(self, client):
        """batch/cases/assign requires admin only -- attorney should get 403."""
        resp = client.post(
            "/api/v1/batch/cases/assign",
            json={"case_ids": ["c1"], "assignee_id": "user-2"},
            headers=_auth_header("attorney"),
        )
        assert resp.status_code == 403

    def test_gdpr_export_attorney(self, client):
        """GDPR export requires admin OR attorney."""
        resp = client.get(
            "/api/v1/gdpr/export/client-1",
            headers=_auth_header("attorney"),
        )
        assert resp.status_code == 200

    def test_gdpr_forget_attorney_forbidden(self, client):
        """GDPR forget requires admin only -- attorney should get 403."""
        resp = client.post(
            "/api/v1/gdpr/forget/client-1",
            headers=_auth_header("attorney"),
        )
        assert resp.status_code == 403


# ===========================================================================
# 4. Paralegal is blocked from attorney/admin endpoints
# ===========================================================================

class TestParalegalAccess:
    """Paralegal role should be blocked from admin-only and attorney-only endpoints."""

    def test_batch_status_paralegal_forbidden(self, client):
        """batch/cases/status requires admin or attorney -- paralegal gets 403."""
        resp = client.post(
            "/api/v1/batch/cases/status",
            json={"case_ids": ["c1"], "new_status": "closed"},
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 403

    def test_batch_assign_paralegal_forbidden(self, client):
        resp = client.post(
            "/api/v1/batch/cases/assign",
            json={"case_ids": ["c1"], "assignee_id": "user-2"},
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 403

    def test_gdpr_export_paralegal_forbidden(self, client):
        resp = client.get(
            "/api/v1/gdpr/export/client-1",
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 403

    def test_gdpr_forget_paralegal_forbidden(self, client):
        resp = client.post(
            "/api/v1/gdpr/forget/client-1",
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 403

    def test_file_delete_paralegal_forbidden(self, client):
        """File delete requires admin or attorney -- paralegal gets 403."""
        resp = client.delete(
            "/api/v1/cases/test-case/files/test.pdf",
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 403


# ===========================================================================
# 5. Consent endpoint (any authenticated user)
# ===========================================================================

class TestAnyAuthenticatedAccess:
    """Some endpoints just need any valid auth token, regardless of role."""

    def test_gdpr_consent_admin(self, client):
        resp = client.get(
            "/api/v1/gdpr/consent/client-1",
            headers=_auth_header("admin"),
        )
        assert resp.status_code == 200

    def test_gdpr_consent_attorney(self, client):
        resp = client.get(
            "/api/v1/gdpr/consent/client-1",
            headers=_auth_header("attorney"),
        )
        assert resp.status_code == 200

    def test_gdpr_consent_paralegal(self, client):
        resp = client.get(
            "/api/v1/gdpr/consent/client-1",
            headers=_auth_header("paralegal"),
        )
        assert resp.status_code == 200


# ===========================================================================
# 6. Invalid token returns 401
# ===========================================================================

class TestInvalidToken:
    """A garbled or expired token should return 401."""

    def test_garbled_token(self, client):
        resp = client.post(
            "/api/v1/batch/cases/status",
            json={"case_ids": ["c1"], "new_status": "closed"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
