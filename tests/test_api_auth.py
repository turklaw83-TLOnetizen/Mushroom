# ---- API Auth Tests ------------------------------------------------------
# Tests for authentication, JWT, and RBAC.

import os
import sys
from pathlib import Path

import pytest

# Ensure project root on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("CLERK_SECRET_KEY", "")


class TestJWT:
    """Test JWT creation and verification."""

    def test_create_and_verify_jwt(self):
        from api.auth import _create_jwt, _verify_jwt

        token = _create_jwt(user_id="user1", role="admin", name="Test User")
        assert token is not None
        assert isinstance(token, str)

        claims = _verify_jwt(token)
        assert claims is not None
        assert claims["sub"] == "user1"
        assert claims["role"] == "admin"
        assert claims["name"] == "Test User"

    def test_verify_invalid_jwt(self):
        from api.auth import _verify_jwt

        result = _verify_jwt("invalid.token.here")
        assert result is None

    def test_verify_empty_jwt(self):
        from api.auth import _verify_jwt

        result = _verify_jwt("")
        assert result is None


class TestPinHash:
    """Test PIN hashing."""

    def test_hash_pin(self):
        from api.auth import hash_pin

        h1 = hash_pin("1234")
        h2 = hash_pin("1234")
        h3 = hash_pin("5678")

        assert h1 == h2  # Same PIN → same hash
        assert h1 != h3  # Different PIN → different hash
        assert len(h1) == 64  # SHA-256 hex digest

    def test_hash_pin_empty(self):
        from api.auth import hash_pin

        h = hash_pin("")
        assert isinstance(h, str)
        assert len(h) == 64


class TestRBAC:
    """Test role-based access control."""

    def test_require_role_creates_dependency(self):
        from api.auth import require_role

        checker = require_role("admin")
        assert callable(checker)

    def test_require_role_multiple_roles(self):
        from api.auth import require_role

        checker = require_role("admin", "attorney")
        assert callable(checker)
