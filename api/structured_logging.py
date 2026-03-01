# ---- Structured Logging + PII Masking ------------------------------------
# JSON-formatted logs with automatic PII scrubbing.

import logging
import json
import re
import sys
from datetime import datetime


# PII patterns to redact
PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD]"),
]

# Field names that should always be redacted
SENSITIVE_FIELDS = {
    "password", "secret", "token", "key", "authorization",
    "ssn", "social_security", "credit_card", "card_number",
    "client_name", "client_email", "witness_name",
}


def scrub_pii(text: str) -> str:
    """Remove PII patterns from a string."""
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def scrub_dict(data: dict) -> dict:
    """Recursively scrub PII from dict values."""
    result = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = scrub_pii(value)
        elif isinstance(value, dict):
            result[key] = scrub_dict(value)
        else:
            result[key] = value
    return result


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with PII scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_pii(record.getMessage()),
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = scrub_pii(str(record.exc_info[1]))

        # Include request_id if available
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        return json.dumps(log_entry, default=str)


def setup_structured_logging(level: str = "INFO"):
    """Configure structured JSON logging with PII masking."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
