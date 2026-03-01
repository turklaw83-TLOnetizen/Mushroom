# ---- Sentry Integration (Backend) ----------------------------------------
# Error tracking + performance monitoring for FastAPI.
# Install: pip install sentry-sdk[fastapi]
# Set SENTRY_DSN env var to enable.

import os
import logging

logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN", "")


def init_sentry():
    """Initialize Sentry SDK for the FastAPI backend."""
    if not SENTRY_DSN:
        logger.info("ℹ️ SENTRY_DSN not set — Sentry disabled")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=os.getenv("ENVIRONMENT", "development"),
            release=os.getenv("APP_VERSION", "1.0.0"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_RATE", "0.1")),
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            # Don't send PII (client names, case data) to Sentry
            send_default_pii=False,
            # Scrub sensitive data from breadcrumbs
            before_breadcrumb=_scrub_breadcrumb,
            before_send=_before_send,
        )

        logger.info("✅ Sentry initialized (env: %s, traces: %.0f%%)",
                    os.getenv("ENVIRONMENT", "dev"),
                    float(os.getenv("SENTRY_TRACES_RATE", "0.1")) * 100)
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed — run: pip install sentry-sdk[fastapi]")
        return False
    except Exception as e:
        logger.error("Sentry init failed: %s", e)
        return False


def _scrub_breadcrumb(crumb, hint):
    """Remove sensitive data from Sentry breadcrumbs."""
    if crumb.get("category") == "http":
        url = crumb.get("data", {}).get("url", "")
        # Don't log full request bodies
        if "data" in crumb:
            crumb["data"].pop("body", None)
    return crumb


def _before_send(event, hint):
    """Scrub PII before sending to Sentry."""
    # Remove user email/name from events
    if "user" in event:
        event["user"] = {"id": event["user"].get("id", "unknown")}

    # Remove request body data (may contain case/client info)
    if "request" in event:
        event["request"].pop("data", None)

    return event
