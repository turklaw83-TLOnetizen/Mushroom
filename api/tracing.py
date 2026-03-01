"""OpenTelemetry distributed tracing setup."""

import logging
import os

logger = logging.getLogger(__name__)


def init_tracing():
    """Initialize OpenTelemetry tracing. No-op if deps not installed."""
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not otlp_endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({
            "service.name": "mushroom-cloud-api",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })

        # Sampling rate
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
            sampler = TraceIdRatioBased(0.1)  # 10% in prod
        else:
            sampler = None  # 100% in dev

        provider_kwargs = {"resource": resource}
        if sampler:
            provider_kwargs["sampler"] = sampler

        provider = TracerProvider(**provider_kwargs)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        logger.info("OpenTelemetry tracing initialized -> %s", otlp_endpoint)

    except ImportError:
        logger.info("OpenTelemetry packages not installed — tracing disabled")
    except Exception as e:
        logger.error("Failed to initialize tracing: %s", e)


def get_tracer(name: str = "mushroom-cloud"):
    """Get a tracer instance."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None
