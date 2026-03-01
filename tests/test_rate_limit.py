# ---- Rate Limiting Tests ----------------------------------------------------
# Tests for per-IP sliding window and per-endpoint tiered rate limiting.

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.rate_limit import (
    _SlidingWindow,
    match_endpoint,
    ENDPOINT_LIMITS,
    _COMPILED_ENDPOINT_PATTERNS,
    _compile_endpoint_patterns,
    MAX_REQUESTS,
    WINDOW_SECONDS,
)


# ---- _SlidingWindow unit tests ----

class TestSlidingWindow:
    def test_allows_first_request(self):
        w = _SlidingWindow()
        allowed, remaining = w.is_allowed("ip1", time.time(), 10, 60)
        assert allowed is True
        assert remaining == 9

    def test_allows_up_to_max(self):
        w = _SlidingWindow()
        now = time.time()
        for i in range(5):
            allowed, remaining = w.is_allowed("ip1", now, 5, 60)
        # The 5th request should be allowed (remaining=0 after it)
        assert allowed is True
        assert remaining == 0

    def test_rejects_over_max(self):
        w = _SlidingWindow()
        now = time.time()
        for _ in range(5):
            w.is_allowed("ip1", now, 5, 60)
        # 6th request should be rejected
        allowed, remaining = w.is_allowed("ip1", now, 5, 60)
        assert allowed is False
        assert remaining == 0

    def test_window_expires_old_timestamps(self):
        w = _SlidingWindow()
        old = time.time() - 120  # 2 minutes ago
        for _ in range(5):
            w.is_allowed("ip1", old, 5, 60)
        # New request should be allowed since old timestamps are outside 60s window
        allowed, remaining = w.is_allowed("ip1", time.time(), 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_separate_keys_are_independent(self):
        w = _SlidingWindow()
        now = time.time()
        for _ in range(5):
            w.is_allowed("ip1", now, 5, 60)
        # ip2 should still be allowed
        allowed, remaining = w.is_allowed("ip2", now, 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_cleanup_removes_stale(self):
        w = _SlidingWindow()
        old = time.time() - 300
        w.is_allowed("ip_stale", old, 10, 60)
        w.cleanup(time.time(), 60)
        # After cleanup, the stale key should be gone
        assert "ip_stale" not in w._buckets

    def test_cleanup_keeps_fresh(self):
        w = _SlidingWindow()
        now = time.time()
        w.is_allowed("ip_fresh", now, 10, 60)
        w.cleanup(now, 60)
        assert "ip_fresh" in w._buckets

    def test_different_max_and_window(self):
        w = _SlidingWindow()
        now = time.time()
        # Use a very small limit
        allowed, remaining = w.is_allowed("ip1", now, 1, 10)
        assert allowed is True
        assert remaining == 0
        # Second request with same limit should fail
        allowed, remaining = w.is_allowed("ip1", now, 1, 10)
        assert allowed is False


# ---- Endpoint matching tests ----

class TestEndpointMatching:
    def setup_method(self):
        # Clear compiled patterns so they rebuild
        _COMPILED_ENDPOINT_PATTERNS.clear()

    def test_matches_chat_stream(self):
        result = match_endpoint("/api/v1/cases/abc123/chat/stream")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/cases/{}/chat/stream"
        assert max_req == 10
        assert window == 60

    def test_matches_analysis_start(self):
        result = match_endpoint("/api/v1/cases/my-case-id/analysis/start")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/cases/{}/analysis/start"
        assert max_req == 5
        assert window == 60

    def test_matches_analysis_ingestion(self):
        result = match_endpoint("/api/v1/cases/case-42/analysis/ingestion")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/cases/{}/analysis/ingestion"
        assert max_req == 5

    def test_matches_documents_outline(self):
        result = match_endpoint("/api/v1/documents/outline")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/documents/outline"
        assert max_req == 10

    def test_matches_documents_draft_section(self):
        result = match_endpoint("/api/v1/documents/draft-section")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/documents/draft-section"
        assert max_req == 10

    def test_matches_documents_review(self):
        result = match_endpoint("/api/v1/documents/review")
        assert result is not None
        pattern, max_req, window = result
        assert pattern == "/api/v1/documents/review"
        assert max_req == 5

    def test_matches_with_trailing_slash(self):
        result = match_endpoint("/api/v1/documents/review/")
        assert result is not None
        pattern, _, _ = result
        assert pattern == "/api/v1/documents/review"

    def test_no_match_for_unknown_path(self):
        result = match_endpoint("/api/v1/cases/abc/files")
        assert result is None

    def test_no_match_for_partial_prefix(self):
        """Should not match a prefix that doesn't end at the right boundary."""
        result = match_endpoint("/api/v1/documents/review/extra/stuff")
        assert result is None

    def test_wildcard_matches_uuid(self):
        result = match_endpoint(
            "/api/v1/cases/550e8400-e29b-41d4-a716-446655440000/chat/stream"
        )
        assert result is not None
        assert result[0] == "/api/v1/cases/{}/chat/stream"

    def test_wildcard_does_not_match_nested_slashes(self):
        """Wildcard {} matches a single path segment, not multiple."""
        result = match_endpoint("/api/v1/cases/a/b/chat/stream")
        assert result is None

    def test_no_match_empty_path(self):
        result = match_endpoint("")
        assert result is None

    def test_no_match_root(self):
        result = match_endpoint("/")
        assert result is None


# ---- Middleware integration tests (using mock ASGI) ----

class TestRateLimitMiddleware:
    """Integration tests for the middleware dispatch logic."""

    def _make_request(self, path="/api/v1/test", client_ip="127.0.0.1"):
        request = MagicMock()
        request.url.path = path
        request.client.host = client_ip
        request.headers = {}
        return request

    def test_exempt_path_bypasses_limiting(self):
        from api.rate_limit import RateLimitMiddleware

        async def _run():
            middleware = RateLimitMiddleware(app=MagicMock())
            request = self._make_request(path="/health")
            call_next = AsyncMock(return_value=MagicMock(headers={}))
            await middleware.dispatch(request, call_next)
            call_next.assert_called_once()

        asyncio.run(_run())

    def test_normal_request_passes(self):
        from api.rate_limit import RateLimitMiddleware

        async def _run():
            middleware = RateLimitMiddleware(app=MagicMock())
            request = self._make_request(client_ip="10.0.0.99")
            mock_response = MagicMock()
            mock_response.headers = {}
            call_next = AsyncMock(return_value=mock_response)
            response = await middleware.dispatch(request, call_next)
            call_next.assert_called_once()
            assert "X-RateLimit-Limit" in response.headers

        asyncio.run(_run())

    def test_endpoint_limit_returns_429_with_endpoint_name(self):
        from api.rate_limit import RateLimitMiddleware, _endpoint_window

        async def _run():
            middleware = RateLimitMiddleware(app=MagicMock())
            path = "/api/v1/cases/test-case/analysis/start"
            client_ip = "10.99.99.99"

            # Exhaust the per-endpoint limit (5 requests)
            ep_key = f"{client_ip}:/api/v1/cases/{{}}/analysis/start"
            now = time.time()
            for _ in range(5):
                _endpoint_window.is_allowed(ep_key, now, 5, 60)

            request = self._make_request(path=path, client_ip=client_ip)
            call_next = AsyncMock()
            response = await middleware.dispatch(request, call_next)

            assert response.status_code == 429
            call_next.assert_not_called()
            # The detail message should mention the endpoint pattern
            assert "/api/v1/cases/{}/analysis/start" in response.body.decode()

        asyncio.run(_run())

    def test_global_limit_fallback_for_non_ai_endpoints(self):
        from api.rate_limit import RateLimitMiddleware, _global_window

        async def _run():
            middleware = RateLimitMiddleware(app=MagicMock())
            client_ip = "10.88.88.88"
            path = "/api/v1/some/regular/endpoint"

            # Exhaust global limit
            now = time.time()
            for _ in range(MAX_REQUESTS):
                _global_window.is_allowed(client_ip, now, MAX_REQUESTS, WINDOW_SECONDS)

            request = self._make_request(path=path, client_ip=client_ip)
            call_next = AsyncMock()
            response = await middleware.dispatch(request, call_next)

            assert response.status_code == 429
            call_next.assert_not_called()
            assert b"Rate limit exceeded" in response.body

        asyncio.run(_run())

    def test_endpoint_headers_included_on_success(self):
        from api.rate_limit import RateLimitMiddleware

        async def _run():
            _COMPILED_ENDPOINT_PATTERNS.clear()
            middleware = RateLimitMiddleware(app=MagicMock())
            client_ip = "10.77.77.77"
            path = "/api/v1/documents/outline"

            request = self._make_request(path=path, client_ip=client_ip)
            mock_response = MagicMock()
            mock_response.headers = {}
            call_next = AsyncMock(return_value=mock_response)
            response = await middleware.dispatch(request, call_next)

            call_next.assert_called_once()
            assert "X-RateLimit-Endpoint-Limit" in response.headers
            assert response.headers["X-RateLimit-Endpoint-Limit"] == "10"

        asyncio.run(_run())
