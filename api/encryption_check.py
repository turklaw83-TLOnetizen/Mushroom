# ---- Encryption at Rest Verification -------------------------------------
# Startup check that validates encrypted storage backend is active.

import logging
import os

logger = logging.getLogger(__name__)


def verify_encryption() -> dict:
    """
    Verify that the encryption-at-rest layer is configured and operational.
    Returns a status dict for health checks.
    """
    status = {
        "encryption_at_rest": False,
        "backend": "unknown",
        "key_configured": False,
    }

    # Check for encryption key
    enc_key = os.getenv("ENCRYPTION_KEY") or os.getenv("DATA_ENCRYPTION_KEY")
    status["key_configured"] = bool(enc_key)

    try:
        from core.storage.encrypted_backend import EncryptedStorageBackend
        status["backend"] = "EncryptedStorageBackend"
        status["encryption_at_rest"] = True

        if not enc_key:
            logger.warning(
                "⚠️ EncryptedStorageBackend available but ENCRYPTION_KEY not set. "
                "Data will NOT be encrypted at rest. Set ENCRYPTION_KEY env var."
            )
            status["encryption_at_rest"] = False
        else:
            logger.info("✅ Encryption at rest: active (EncryptedStorageBackend)")

    except ImportError:
        logger.warning(
            "⚠️ EncryptedStorageBackend not available. "
            "Falling back to unencrypted storage."
        )
        status["backend"] = "PostgresStorageBackend (unencrypted)"

    return status


def require_encryption_in_production():
    """Call on startup in production to enforce encryption."""
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        result = verify_encryption()
        if not result["encryption_at_rest"]:
            logger.critical(
                "🚨 PRODUCTION: Encryption at rest is NOT active! "
                "Set ENCRYPTION_KEY and ensure EncryptedStorageBackend is configured. "
                "Refusing to start without encryption in production."
            )
            raise RuntimeError("Encryption at rest required in production")
    return verify_encryption()
