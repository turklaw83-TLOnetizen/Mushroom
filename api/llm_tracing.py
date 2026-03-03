"""LLM call tracing — wraps LLM calls with OpenTelemetry spans."""

import logging
import time
from typing import Optional

from api.prometheus_metrics import llm_tokens_total, llm_request_duration, llm_errors_total

logger = logging.getLogger(__name__)


def trace_llm_call(model: str, node_type: str = "unknown"):
    """Decorator that traces LLM calls with metrics and optional OTel spans."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            span = None

            # Try to create OTel span
            try:
                from api.tracing import get_tracer
                tracer = get_tracer()
                if tracer:
                    span = tracer.start_span(
                        f"llm.{node_type}",
                        attributes={"llm.model": model, "llm.node_type": node_type},
                    )
            except Exception:
                pass

            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start
                llm_request_duration.labels(model=model).observe(duration)

                # Try to extract token counts from result
                tokens_in = getattr(result, "input_tokens", 0) or kwargs.get("_tokens_in", 0)
                tokens_out = getattr(result, "output_tokens", 0) or kwargs.get("_tokens_out", 0)
                if tokens_in:
                    llm_tokens_total.labels(model=model, node_type=node_type, direction="input").inc(tokens_in)
                if tokens_out:
                    llm_tokens_total.labels(model=model, node_type=node_type, direction="output").inc(tokens_out)

                if span:
                    span.set_attribute("llm.tokens.input", tokens_in)
                    span.set_attribute("llm.tokens.output", tokens_out)
                    span.set_attribute("llm.duration_s", round(duration, 3))

                return result

            except Exception as e:
                llm_errors_total.labels(model=model, error_type=type(e).__name__).inc()
                if span:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e)[:200])
                raise
            finally:
                if span:
                    span.end()

        return wrapper
    return decorator
