# ---- Environment Validation + Startup Config ----------------------------
# Validates all required env vars on boot. Crashes early with clear errors.

import os
import sys
import logging

logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    "DATABASE_URL",
    "CLERK_SECRET_KEY",
]

OPTIONAL_VARS = {
    "CORS_ORIGINS": "http://localhost:3000",
    "RATE_LIMIT_REQUESTS": "120",
    "RATE_LIMIT_WINDOW_SECONDS": "60",
    "MAX_UPLOAD_SIZE_BYTES": str(20 * 1024 * 1024 * 1024),  # 20GB
    "SESSION_TIMEOUT_MINUTES": "480",  # 8 hours
    "LOG_LEVEL": "INFO",
}


class Settings:
    """Validated application settings."""

    def __init__(self) -> None:
        missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
        if missing:
            print(f"\n❌ FATAL: Missing required environment variables: {', '.join(missing)}")
            print("   Set them in .env or docker-compose environment block.\n")
            sys.exit(1)

        self.database_url: str = os.environ["DATABASE_URL"]
        self.clerk_secret_key: str = os.environ["CLERK_SECRET_KEY"]

        # Optional with defaults
        self.cors_origins: list[str] = os.getenv("CORS_ORIGINS", OPTIONAL_VARS["CORS_ORIGINS"]).split(",")
        self.rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", OPTIONAL_VARS["RATE_LIMIT_REQUESTS"]))
        self.rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", OPTIONAL_VARS["RATE_LIMIT_WINDOW_SECONDS"]))
        self.max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", OPTIONAL_VARS["MAX_UPLOAD_SIZE_BYTES"]))
        self.session_timeout_minutes: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", OPTIONAL_VARS["SESSION_TIMEOUT_MINUTES"]))
        self.log_level: str = os.getenv("LOG_LEVEL", OPTIONAL_VARS["LOG_LEVEL"])

        logger.info("✅ Environment validated — %d required, %d optional vars loaded", len(REQUIRED_VARS), len(OPTIONAL_VARS))

    @property
    def max_upload_gb(self) -> float:
        return self.max_upload_bytes / (1024 ** 3)


# Singleton — import and use: from api.env import settings
settings = Settings()
