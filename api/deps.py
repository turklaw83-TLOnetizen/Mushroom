# ---- Dependency Injection ------------------------------------------------
# FastAPI dependencies for database sessions, CaseManager, UserManager.
#
# Key design: PostgresStorageBackend is a SINGLETON — its engine and
# session factory are created once and reused across all requests.

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, HTTPException

from api.auth import get_current_user
from api.database import get_session_factory

logger = logging.getLogger(__name__)

# Project root (one level up from api/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = str(PROJECT_ROOT / "data")


async def get_db() -> AsyncGenerator:
    """Yield an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


def get_data_dir() -> str:
    """Return the data directory path (for file storage on disk)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


@lru_cache(maxsize=1)
def _get_postgres_backend():
    """
    Create a SINGLETON PostgresStorageBackend.

    Uses @lru_cache so the engine/session factory are created once
    and reused for the lifetime of the process. This prevents
    opening a new connection pool on every HTTP request.
    """
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None
    from core.storage.postgres_backend import PostgresStorageBackend
    data_dir = get_data_dir()
    backend = PostgresStorageBackend(database_url, data_dir)
    logger.info("PostgresStorageBackend singleton created")
    return backend


@lru_cache(maxsize=1)
def _get_json_backend():
    """Singleton JSONStorageBackend fallback."""
    from core.storage.json_backend import JSONStorageBackend
    data_dir = get_data_dir()
    backend = JSONStorageBackend(data_dir)
    logger.info("JSONStorageBackend singleton created (no DATABASE_URL)")
    return backend


def get_storage_backend():
    """Return the singleton storage backend (Postgres or JSON)."""
    pg = _get_postgres_backend()
    if pg is not None:
        return pg
    return _get_json_backend()


def get_case_manager():
    """
    Return a CaseManager wrapping the singleton storage backend.

    CaseManager itself is lightweight (just holds a reference to storage),
    so it's fine to create per-request. The storage backend underneath
    is a singleton with a shared connection pool.
    """
    from core.case_manager import CaseManager
    return CaseManager(get_storage_backend())


def get_user_manager():
    """Return a UserManager instance."""
    from core.user_profiles import UserManager
    return UserManager()


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Load and return config.yaml (cached after first read)."""
    import yaml
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# ---- Path Parameter Validation -------------------------------------------
# Rejects traversal and injection attempts in case_id / prep_id path params.

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")


def validate_path_id(value: str, label: str = "id") -> str:
    """Validate a path parameter is a safe identifier.

    Rejects: '../', '..\\', null bytes, slashes, and anything
    that doesn't match [a-zA-Z0-9_-]{1,200}.
    """
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}: must be 1-200 alphanumeric, dash, or underscore characters",
        )
    return value


def valid_case_id(case_id: str) -> str:
    """FastAPI dependency — validates case_id path parameter."""
    return validate_path_id(case_id, "case_id")


def valid_prep_id(prep_id: str) -> str:
    """FastAPI dependency — validates prep_id path parameter."""
    return validate_path_id(prep_id, "prep_id")
