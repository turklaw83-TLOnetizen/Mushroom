"""Prometheus metrics definitions for Project Mushroom Cloud."""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

    # HTTP metrics
    http_requests_total = Counter(
        "http_requests_total", "Total HTTP requests",
        labelnames=["method", "path", "status_code"],
    )
    http_request_duration = Histogram(
        "http_request_duration_seconds", "HTTP request duration",
        labelnames=["method", "path"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    # WebSocket metrics
    ws_connections_active = Gauge("ws_connections_active", "Active WebSocket connections")

    # Background workers
    worker_status = Gauge(
        "worker_status", "Background worker status (1=running, 0=idle)",
        labelnames=["worker_type"],
    )

    # LLM metrics
    llm_tokens_total = Counter(
        "llm_tokens_total", "Total LLM tokens used",
        labelnames=["model", "node_type", "direction"],
    )
    llm_request_duration = Histogram(
        "llm_request_duration_seconds", "LLM request duration",
        labelnames=["model"],
        buckets=[1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
    )
    llm_errors_total = Counter(
        "llm_errors_total", "LLM request errors",
        labelnames=["model", "error_type"],
    )

    # Application metrics
    active_cases = Gauge("active_cases_total", "Total active cases")
    file_uploads_total = Counter("file_uploads_total", "Total file uploads")
    file_upload_size = Histogram(
        "file_upload_size_bytes", "File upload sizes",
        buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],
    )
    ocr_pages_processed = Counter("ocr_pages_processed_total", "OCR pages processed")
    analysis_runs_total = Counter(
        "analysis_runs_total", "Analysis runs",
        labelnames=["prep_type", "status"],
    )

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — metrics disabled")

    # Stub classes so code doesn't break
    class _Stub:
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): pass
        def dec(self, *a, **kw): pass
        def set(self, *a, **kw): pass
        def observe(self, *a, **kw): pass

    http_requests_total = _Stub()
    http_request_duration = _Stub()
    ws_connections_active = _Stub()
    worker_status = _Stub()
    llm_tokens_total = _Stub()
    llm_request_duration = _Stub()
    llm_errors_total = _Stub()
    active_cases = _Stub()
    file_uploads_total = _Stub()
    file_upload_size = _Stub()
    ocr_pages_processed = _Stub()
    analysis_runs_total = _Stub()

    def generate_latest():
        return b"# prometheus_client not installed\n"

    CONTENT_TYPE_LATEST = "text/plain"
