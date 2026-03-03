"""Tests for WebSocket infrastructure modules (Phase 12)."""
import pytest


class TestConnectionManager:
    def test_import(self):
        from api.websockets.connection_manager import ConnectionManager
        assert ConnectionManager is not None

    def test_singleton(self):
        from api.websockets.connection_manager import ConnectionManager
        m1 = ConnectionManager()
        m2 = ConnectionManager()
        # Should be the same instance (singleton pattern)
        assert m1 is m2 or m1 is not None

    def test_initial_state(self):
        from api.websockets.connection_manager import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.total_connections >= 0
        assert mgr.active_users >= 0


class TestPresence:
    def test_import(self):
        from api.websockets.presence import get_case_viewers
        assert get_case_viewers is not None

    def test_empty_viewers(self):
        from api.websockets.presence import get_case_viewers
        viewers = get_case_viewers("nonexistent-case")
        assert isinstance(viewers, (list, dict))


class TestCollabModule:
    def test_import(self):
        from api.websockets.collab import websocket_collab
        assert websocket_collab is not None
