# ---- Database Configuration -----------------------------------------------
# Async SQLAlchemy engine and session management for PostgreSQL.

import logging
import ssl
from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Module-level engine and session factory — initialized by init_db()
_engine = None
_async_session_factory = None


def _clean_url(database_url: str) -> tuple[str, dict]:
    """Strip sslmode from URL (asyncpg uses ssl context instead) and return cleaned URL + connect args."""
    parsed = urlparse(database_url)
    params = parse_qs(parsed.query)
    connect_args = {}

    if "sslmode" in params:
        mode = params.pop("sslmode")[0]
        if mode in ("require", "verify-ca", "verify-full"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = mode == "verify-full"
            ctx.verify_mode = ssl.CERT_REQUIRED if mode != "require" else ssl.CERT_NONE
            connect_args["ssl"] = ctx
        new_query = urlencode(params, doseq=True)
        parsed = parsed._replace(query=new_query)

    return urlunparse(parsed), connect_args


def init_db(database_url: str, echo: bool = False):
    """
    Initialize the async database engine and session factory.

    Call this once at startup (e.g., in FastAPI lifespan).
    database_url should use the asyncpg driver:
        postgresql+asyncpg://user:pass@host:5432/dbname
    """
    global _engine, _async_session_factory

    clean_url, connect_args = _clean_url(database_url)

    _engine = create_async_engine(
        clean_url,
        echo=echo,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
    )

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Database engine initialized: %s", database_url.split("@")[-1])


async def close_db():
    """Dispose the engine. Call on shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed.")


def get_session_factory() -> async_sessionmaker:
    """Return the session factory. Raises if not initialized."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory


def get_engine():
    """Return the async engine, or None if not initialized."""
    return _engine


@asynccontextmanager
async def get_session():
    """Async context manager for a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    """Create all tables (for development/testing). Use Alembic in production."""
    from api.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")
