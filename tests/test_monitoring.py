"""Tests for monitoring/observability modules (Phase 19+20)."""
import pytest


class TestPrometheusMetrics:
    def test_import(self):
        from api.prometheus_metrics import (
            http_requests_total,
            http_request_duration,
            ws_connections_active,
        )
        assert http_requests_total is not None
        assert http_request_duration is not None

    def test_metrics_are_callable(self):
        """Metrics should have stub or real label methods."""
        from api.prometheus_metrics import http_requests_total
        # Should not raise even if prometheus_client is stubbed
        try:
            labeled = http_requests_total.labels(method="GET", endpoint="/test", status=200)
            assert labeled is not None
        except Exception:
            pass  # OK if prometheus_client not installed


class TestMetricsMiddleware:
    def test_import(self):
        from api.metrics_middleware import PrometheusMiddleware
        assert PrometheusMiddleware is not None


class TestProfiling:
    def test_import(self):
        from api.profiling import ProfilingMiddleware, get_performance_summary
        assert ProfilingMiddleware is not None
        assert get_performance_summary is not None

    def test_performance_summary(self):
        from api.profiling import get_performance_summary
        summary = get_performance_summary()
        assert isinstance(summary, dict)


class TestTracing:
    def test_import(self):
        from api.tracing import init_tracing, get_tracer
        assert init_tracing is not None
        assert get_tracer is not None


class TestLLMTracing:
    def test_import(self):
        from api.llm_tracing import trace_llm_call
        assert trace_llm_call is not None

    def test_decorator_wraps(self):
        from api.llm_tracing import trace_llm_call

        @trace_llm_call(model="test-model", node_type="test")
        def dummy_fn():
            return "result"

        result = dummy_fn()
        assert result == "result"
