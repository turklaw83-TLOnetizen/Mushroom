# ---- LLM Factory & Retry ---------------------------------------------------
# Provides get_llm(), invoke_with_retry(), invoke_with_retry_streaming().
# Ported from backend/llm.py with logging fixes (no emoji print statements).

import logging
import os
import threading
import time
from typing import Optional

from core.config import CONFIG
from core.state import get_stream_callback

logger = logging.getLogger(__name__)


# ---- Per-Thread Token Usage Accumulator -----------------------------------
# Captures actual token usage from every LLM API call for accurate billing.
# Uses threading.local() so concurrent analysis runs on different cases
# each track their own usage independently (no cross-case pollution).

_usage_local = threading.local()
_context_local = threading.local()


def set_max_context_mode(enabled: bool):
    """Set per-thread max context mode. Call at the start of an analysis run."""
    _context_local.max_context_mode = enabled


def get_max_context_mode() -> bool:
    """Read per-thread max context mode (defaults to False)."""
    return getattr(_context_local, "max_context_mode", False)


def reset_usage_accumulator():
    """Clear the per-thread usage accumulator. Call at the start of an analysis run."""
    _usage_local.entries = []


def get_accumulated_usage() -> dict:
    """Return total accumulated token usage for the current thread since last reset."""
    entries = getattr(_usage_local, "entries", [])
    total_in = sum(u.get("input_tokens", 0) for u in entries)
    total_out = sum(u.get("output_tokens", 0) for u in entries)
    return {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "calls": len(entries),
        "breakdown": list(entries),
    }


def _record_usage(response, model_name=""):
    """Extract and record usage metadata from a LangChain response (per-thread)."""
    # LangChain models return usage_metadata as a dict with input_tokens/output_tokens
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        # Some models put it in response_metadata
        rmeta = getattr(response, "response_metadata", None)
        if rmeta and isinstance(rmeta, dict):
            usage = rmeta.get("usage", rmeta.get("token_usage"))
    if usage and isinstance(usage, dict):
        entry = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "model": model_name,
        }
        if entry["input_tokens"] or entry["output_tokens"]:
            if not hasattr(_usage_local, "entries"):
                _usage_local.entries = []
            _usage_local.entries.append(entry)


# ---- LLM Factory ---------------------------------------------------------

def get_llm(provider: str = None, max_output_tokens: int = 4096, max_context_mode: bool = None):
    """
    Build and return a LangChain chat model for the given provider.

    Supported providers:
        - "xai"               -> ChatXAI (Grok)
        - "anthropic"         -> ChatAnthropic (Claude, config default model)
        - "claude-sonnet-4.5" -> Claude Sonnet 4.5
        - "claude-sonnet-4"   -> Claude Sonnet 4
        - "claude-sonnet-4.6" -> Claude Sonnet 4.6
        - "claude-opus-4.6"   -> Claude Opus 4.6
        - "custom:<model_id>" -> Anthropic with custom model ID
        - "gemini"            -> Google Gemini

    Args:
        provider: LLM provider key. Falls back to config default if None.
        max_output_tokens: Maximum output tokens for the response.
        max_context_mode: When True, enables 1M context window for supported
            models (opus-4.6, sonnet-4.6). When False, uses default 200K window.
            When None (default), reads from thread-local set by set_max_context_mode().

    Returns None if the API key is missing or the provider is unknown.
    """
    # Resolve max_context_mode: explicit param > thread-local > False
    if max_context_mode is None:
        max_context_mode = get_max_context_mode()
    if not provider:
        provider = CONFIG.get("llm", {}).get("default_provider", "xai")

    # -- XAI / Grok --
    if provider == "xai":
        api_key = os.getenv("XAI_API_KEY") or CONFIG.get("api_keys", {}).get("xai")
        if not api_key:
            return None
        try:
            from langchain_xai import ChatXAI
        except ImportError:
            logger.warning("langchain-xai not installed")
            return None
        return ChatXAI(
            model=CONFIG.get("llm", {}).get("xai", {}).get("model", "grok-4"),
            xai_api_key=api_key,
            temperature=0.3,
        )

    # -- Anthropic (Claude) --
    if "anthropic" in provider or "claude" in provider.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY") or CONFIG.get("api_keys", {}).get("anthropic")
        if not api_key:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            logger.warning("langchain-anthropic not installed")
            return None

        # Determine model ID
        config_default = CONFIG.get("llm", {}).get("anthropic", {}).get("model", "claude-sonnet-4-5")
        model_id = config_default
        if provider == "claude-sonnet-4.5":
            model_id = "claude-sonnet-4-5"
        elif provider == "claude-sonnet-4":
            model_id = "claude-sonnet-4"
        elif provider == "claude-sonnet-4.6":
            model_id = "claude-sonnet-4-6"
        elif provider == "claude-opus-4.6":
            model_id = "claude-opus-4-6"
        elif provider.startswith("custom:"):
            model_id = provider.replace("custom:", "")

        # Enable extended context window for large-context models when max_context_mode is ON
        extra_kwargs = {}
        if max_context_mode and model_id in ("claude-opus-4-6", "claude-sonnet-4-6"):
            extra_kwargs["default_headers"] = {
                "anthropic-beta": "context-1m-2025-08-07",
            }
            logger.info("1M context window enabled for model %s", model_id)

        return ChatAnthropic(
            model=model_id,
            anthropic_api_key=api_key,
            temperature=0.3,
            max_tokens=max_output_tokens,
            **extra_kwargs,
        )

    # -- Google Gemini --
    if "gemini" in provider:
        api_key = os.getenv("GOOGLE_API_KEY") or CONFIG.get("api_keys", {}).get("google")
        if not api_key:
            return None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            logger.warning("langchain-google-genai not installed")
            return None
        return ChatGoogleGenerativeAI(
            model="gemini-3.1-pro-preview",
            google_api_key=api_key,
            temperature=0.3,
            max_output_tokens=max_output_tokens,
        )

    logger.warning("Unknown LLM provider: %s", provider)
    return None


# ---- Streamed Response Wrapper -------------------------------------------

class _StreamedResponse:
    """Mimics a LangChain response object for compatibility with node functions."""

    def __init__(self, content: str):
        self.content = content


# ---- Retry with Exponential Backoff --------------------------------------

_RETRYABLE_CODES = ("429", "500", "503", "529", "overloaded", "rate_limit")


def invoke_with_retry(llm, messages, max_retries: int = 3):
    """
    Wraps llm.invoke() with exponential backoff for transient API errors.
    When a stream callback is set, uses llm.stream() to pipe tokens live.
    Handles 429 (rate limit), 500, 503, 529 (overloaded), and connection errors.
    """
    for attempt in range(max_retries + 1):
        try:
            cb = get_stream_callback()
            if cb is not None:
                # Streaming mode — capture usage from last chunk
                full_text = ""
                _last_chunk = None
                for chunk in llm.stream(messages):
                    _last_chunk = chunk
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    full_text += token
                    try:
                        cb(token)
                    except Exception:
                        pass  # UI callback errors must not kill the LLM call
                # Record usage from the stream's last chunk or aggregate
                if _last_chunk is not None:
                    _record_usage(_last_chunk)
                return _StreamedResponse(full_text)
            else:
                response = llm.invoke(messages)
                _record_usage(response)
                return response
        except Exception as exc:
            error_str = str(exc)
            retryable = any(code in error_str for code in _RETRYABLE_CODES)
            if not retryable and "Connection" not in type(exc).__name__:
                raise
            if attempt == max_retries:
                raise
            wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
            logger.warning(
                "API error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1, max_retries, error_str[:100], wait_time,
            )
            time.sleep(wait_time)


def invoke_with_retry_streaming(llm, messages, max_retries: int = 3):
    """
    Streaming version of invoke_with_retry.
    Yields (event_type, data) tuples:
        ("token", token_text)  -- for each streamed token
        ("done", full_text)    -- when complete
    """
    for attempt in range(max_retries + 1):
        try:
            full_text = ""
            _last_chunk = None
            for chunk in llm.stream(messages):
                _last_chunk = chunk
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_text += token
                yield ("token", token)
            # Record usage from stream's last chunk
            if _last_chunk is not None:
                _record_usage(_last_chunk)
            yield ("done", full_text)
            return
        except Exception as exc:
            error_str = str(exc)
            retryable = any(code in error_str for code in _RETRYABLE_CODES)
            if not retryable and "Connection" not in type(exc).__name__:
                raise
            if attempt == max_retries:
                raise
            wait_time = 2 ** (attempt + 1)
            logger.warning(
                "Stream API error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1, max_retries, error_str[:100], wait_time,
            )
            time.sleep(wait_time)
