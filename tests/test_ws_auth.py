"""Tests for WebSocket authentication.

Unit tests for verify_ws_token() from api/websockets/connection_manager.py.
These test the token verification logic without needing a full WebSocket connection.

Uses asyncio.run() to call async functions from sync tests, avoiding a
pytest-asyncio dependency.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("CLERK_SECRET_KEY", "")


def _run(coro):
    """Run an async coroutine from a sync test."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===========================================================================
# verify_ws_token tests
# ===========================================================================


class TestVerifyWsToken:
    """Unit tests for verify_ws_token()."""

    def test_empty_token_returns_none(self):
        """An empty string token should immediately return None."""
        from api.websockets.connection_manager import verify_ws_token
        result = _run(verify_ws_token(""))
        assert result is None

    def test_none_token_returns_none(self):
        """A None-ish falsy token should return None."""
        from api.websockets.connection_manager import verify_ws_token
        result = _run(verify_ws_token(None))
        assert result is None

    def test_invalid_token_returns_none(self):
        """A garbled token should return None (not raise)."""
        from api.websockets.connection_manager import verify_ws_token
        result = _run(verify_ws_token("not-a-valid-jwt-token"))
        assert result is None

    def test_valid_legacy_jwt_returns_user(self):
        """A properly signed legacy JWT should return a user dict."""
        from api.auth import _create_jwt
        from api.websockets.connection_manager import verify_ws_token

        token = _create_jwt(user_id="ws_user_1", role="attorney", name="WS Attorney")

        # Ensure Clerk is disabled so it falls through to legacy JWT
        # _get_clerk_secret_key is imported inside verify_ws_token from api.auth
        with patch("api.auth._get_clerk_secret_key", return_value=""):
            result = _run(verify_ws_token(token))

        assert result is not None
        assert result["id"] == "ws_user_1"
        assert result["role"] == "attorney"
        assert result["name"] == "WS Attorney"

    def test_valid_admin_jwt_returns_admin_role(self):
        """Admin JWTs should preserve the admin role through verification."""
        from api.auth import _create_jwt
        from api.websockets.connection_manager import verify_ws_token

        token = _create_jwt(user_id="admin_1", role="admin", name="Admin User")

        with patch("api.auth._get_clerk_secret_key", return_value=""):
            result = _run(verify_ws_token(token))

        assert result is not None
        assert result["role"] == "admin"

    def test_expired_jwt_returns_none(self):
        """An expired JWT should return None."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from api.websockets.connection_manager import verify_ws_token

        secret = os.environ.get("JWT_SECRET", "test-secret-key")
        expired_payload = {
            "sub": "expired_user",
            "role": "attorney",
            "name": "Expired",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = pyjwt.encode(expired_payload, secret, algorithm="HS256")

        with patch("api.auth._get_clerk_secret_key", return_value=""):
            result = _run(verify_ws_token(expired_token))

        assert result is None

    def test_wrong_secret_returns_none(self):
        """A JWT signed with a different secret should return None."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from api.websockets.connection_manager import verify_ws_token

        wrong_secret_payload = {
            "sub": "wrong_secret_user",
            "role": "attorney",
            "name": "Wrong",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        token = pyjwt.encode(wrong_secret_payload, "completely-different-secret", algorithm="HS256")

        with patch("api.auth._get_clerk_secret_key", return_value=""):
            result = _run(verify_ws_token(token))

        assert result is None
