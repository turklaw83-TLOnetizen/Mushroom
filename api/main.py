# ---- FastAPI Application Entry Point --------------------------------------
# Project Mushroom Cloud API Server
#
# Run with:  uvicorn api.main:app --reload --port 8000

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Sentry error tracking (no-op if SENTRY_DSN not set)
from api.sentry_init import init_sentry
init_sentry()

# ---- Bootstrap -----------------------------------------------------------

# Ensure project root is on sys.path so core.* imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(str(_ENV_PATH))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mushroom_cloud_api")


# ---- Lifespan ------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Project Mushroom Cloud API...")

    # Initialize database if DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        from api.database import init_db, create_tables, close_db
        try:
            init_db(database_url, echo=os.getenv("DB_ECHO", "").lower() == "true")
            await create_tables()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning("Database connection failed: %s — API will run without DB", e)
    else:
        logger.warning("DATABASE_URL not set — running without PostgreSQL")

    # Ensure data directory exists
    data_dir = _PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)

    logger.info("API server ready")

    yield

    # Shutdown
    if database_url:
        from api.database import close_db
        await close_db()

    logger.info("API server shut down")


# ---- Application ---------------------------------------------------------

app = FastAPI(
    title="Project Mushroom Cloud",
    description="Legal Intelligence Suite API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/")
def root():
    """Root endpoint — API welcome + navigation."""
    return {
        "name": "Project Mushroom Cloud",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health",
        "routers": 32,
    }
# ---- Middleware (order matters: last added = outermost) -------------------

from api.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, structured_error_handler
from api.audit import AuditTrailMiddleware
from api.rate_limit import RateLimitMiddleware
from api.upload_limit import UploadSizeMiddleware
from api.input_sanitize import InputSanitizationMiddleware
from api.metrics import MetricsMiddleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditTrailMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(UploadSizeMiddleware, max_size=20 * 1024 * 1024 * 1024)  # 20GB
app.add_middleware(InputSanitizationMiddleware)
app.add_middleware(MetricsMiddleware)

# Fix #10: Global structured error handler
app.add_exception_handler(Exception, structured_error_handler)

# Encryption verification on startup
from api.encryption_check import require_encryption_in_production
try:
    require_encryption_in_production()
except RuntimeError:
    pass  # Logged; non-fatal in dev

# CORS — locked to explicit origins (no wildcards in production)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],  # Let frontend read request IDs
)


# ---- Routers -------------------------------------------------------------

from api.routers.users import router as users_router
from api.routers.cases import router as cases_router
from api.routers.files import router as files_router
from api.routers.analysis import router as analysis_router
from api.routers.export import router as export_router
from api.routers.witnesses import router as witnesses_router
from api.routers.evidence import router as evidence_router
from api.routers.strategy import router as strategy_router
from api.routers.billing import router as billing_router
from api.routers.calendar import router as calendar_router
from api.routers.compliance import router as compliance_router
from api.routers.documents import router as documents_router
from api.routers.crm import router as crm_router
from api.routers.search import router as search_router
from api.routers.notifications import router as notifications_router
from api.routers.annotations import router as annotations_router
from api.routers.exhibits import router as exhibits_router
from api.routers.esign import router as esign_router
from api.routers.email import router as email_router
from api.routers.backup import router as backup_router
from api.routers.tasks import router as tasks_router
from api.routers.workflows import router as workflows_router
from api.routers.transcription import router as transcription_router
from api.routers.quality import router as quality_router
from api.routers.gcal import router as gcal_router
from api.routers.conflicts import router as conflicts_router
from api.routers.sol import router as sol_router
from api.routers.ai_features import router as ai_features_router
from api.routers.webhooks import router as webhooks_router
from api.routers.gdpr import router as gdpr_router
from api.routers.batch import router as batch_router
from api.metrics import router as metrics_router
from api.websockets.workers_ws import router as ws_router
from api.routers.mock_exam import router as mock_exam_router
from api.websockets.mock_exam_ws import router as mock_exam_ws_router

app.include_router(users_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(witnesses_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(strategy_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(crm_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(annotations_router, prefix="/api/v1")
app.include_router(exhibits_router, prefix="/api/v1")
app.include_router(esign_router, prefix="/api/v1")
app.include_router(email_router, prefix="/api/v1")
app.include_router(backup_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(transcription_router, prefix="/api/v1")
app.include_router(quality_router, prefix="/api/v1")
app.include_router(gcal_router, prefix="/api/v1")
app.include_router(conflicts_router, prefix="/api/v1")
app.include_router(sol_router, prefix="/api/v1")
app.include_router(ai_features_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(gdpr_router, prefix="/api/v1")
app.include_router(batch_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(mock_exam_router, prefix="/api/v1")
app.include_router(mock_exam_ws_router, prefix="/api/v1")


# ---- Health Check (Fix #12: actually pings DB) ---------------------------

@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns database connectivity status alongside the service status.
    """
    db_status = "not_configured"
    db_latency_ms = None

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            import time
            from api.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            if engine:
                start = time.perf_counter()
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                db_latency_ms = round((time.perf_counter() - start) * 1000, 1)
                db_status = "connected"
            else:
                db_status = "engine_not_initialized"
        except Exception as e:
            logger.warning("Health check DB ping failed: %s", e)
            db_status = "error"

    return {
        "status": "healthy" if db_status in ("connected", "not_configured") else "degraded",
        "service": "Project Mushroom Cloud API",
        "version": "1.0.0",
        "database": db_status,
        "db_latency_ms": db_latency_ms,
    }


@app.get("/api/v1/config/providers", tags=["System"])
def get_providers():
    """Return configured LLM providers (no secrets)."""
    from api.deps import get_config
    config = get_config()
    llm = config.get("llm", {})
    return {
        "default_provider": llm.get("default_provider", "anthropic"),
        "fallback_provider": llm.get("fallback_provider", "xai"),
        "providers": {
            name: {"model": p.get("model", ""), "temperature": p.get("temperature", 0.3)}
            for name, p in llm.items()
            if isinstance(p, dict) and "model" in p
        },
    }
