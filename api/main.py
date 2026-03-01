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
        "routers": 39,
    }
# ---- Middleware (order matters: last added = outermost) -------------------

from api.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, structured_error_handler
from api.audit import AuditTrailMiddleware
from api.rate_limit import RateLimitMiddleware
from api.upload_limit import UploadSizeMiddleware
from api.input_sanitize import InputSanitizationMiddleware
from api.metrics import MetricsMiddleware

# Phase 19: Prometheus metrics middleware (graceful if not installed)
try:
    from api.metrics_middleware import PrometheusMiddleware
    app.add_middleware(PrometheusMiddleware)
except ImportError:
    pass

# Phase 20: Profiling middleware (opt-in via ENABLE_PROFILING=true)
try:
    from api.profiling import ProfilingMiddleware
    if os.getenv("ENABLE_PROFILING", "").lower() == "true":
        app.add_middleware(ProfilingMiddleware)
except ImportError:
    pass

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
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
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
from api.routers.chat import router as chat_router
from api.routers.module_notes import router as module_notes_router
from api.routers.journal import router as journal_router
from api.routers.snapshots import router as snapshots_router
from api.metrics import router as metrics_router
from api.websockets.workers_ws import router as ws_router

# Phase 19+20: Web Vitals / performance metrics router
try:
    from api.routers.metrics_router import router as web_vitals_router
except ImportError:
    web_vitals_router = None

# Phase 22: Multi-tenancy router
try:
    from api.routers.tenants import router as tenants_router
except ImportError:
    tenants_router = None

# Phase 24: DLP / file security router
try:
    from api.routers.dlp import router as dlp_router
except ImportError:
    dlp_router = None

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
app.include_router(chat_router, prefix="/api/v1")
app.include_router(module_notes_router, prefix="/api/v1")
app.include_router(journal_router, prefix="/api/v1")
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")

# Phase 19+20: Web Vitals router
if web_vitals_router:
    app.include_router(web_vitals_router, prefix="/api/v1")

# Phase 22: Tenant management
if tenants_router:
    app.include_router(tenants_router, prefix="/api/v1")

# Phase 24: DLP / file security
if dlp_router:
    app.include_router(dlp_router, prefix="/api/v1")

# Phase 12: WebSocket endpoints for real-time features
from api.websockets.notifications_ws import websocket_notifications
from api.websockets.presence import websocket_presence
from api.websockets.collab import websocket_collab

app.add_api_websocket_route("/ws/notifications", websocket_notifications)
app.add_api_websocket_route("/ws/presence/{case_id}", websocket_presence)
app.add_api_websocket_route("/ws/collab/{case_id}", websocket_collab)

# Phase 19: Prometheus /metrics endpoint
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    @app.get("/metrics", tags=["System"])
    async def prometheus_metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
except ImportError:
    pass

# Phase 20: OpenTelemetry tracing init
try:
    from api.tracing import init_tracing
    init_tracing()
except ImportError:
    pass


# ---- Health Check (Fix #12: actually pings DB + LLM/disk/data checks) ----

@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns database connectivity, LLM provider availability, disk space,
    and data directory status alongside the service status.
    """
    import shutil
    import time

    db_status = "not_configured"
    db_latency_ms = None

    # ---- Database check ----
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
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
            db_status = f"error: {e}"

    # ---- LLM provider check ----
    llm_status = (
        "configured"
        if os.getenv("ANTHROPIC_API_KEY") or os.getenv("XAI_API_KEY")
        else "no_api_keys"
    )

    # ---- Disk space check ----
    data_dir = _PROJECT_ROOT / "data"
    disk_free_gb = None
    try:
        disk = shutil.disk_usage(str(data_dir) if data_dir.exists() else str(_PROJECT_ROOT))
        disk_free_gb = round(disk.free / (1024 ** 3), 1)
    except OSError:
        pass  # disk_free_gb stays None

    # ---- Data directory check ----
    if not data_dir.exists():
        data_dir_status = "missing"
    else:
        # Verify writable by attempting to create and remove a temp file
        try:
            probe = data_dir / ".health_probe"
            probe.write_text("ok")
            probe.unlink()
            data_dir_status = "ok"
        except OSError:
            data_dir_status = "not_writable"

    # ---- Overall status ----
    degraded = (
        db_status not in ("connected", "not_configured")
        or llm_status != "configured"
        or data_dir_status != "ok"
    )
    unhealthy = data_dir_status == "missing"

    if unhealthy:
        overall = "unhealthy"
    elif degraded:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "service": "Project Mushroom Cloud API",
        "version": "1.0.0",
        "database": db_status,
        "db_latency_ms": db_latency_ms,
        "llm": llm_status,
        "disk_free_gb": disk_free_gb,
        "data_dir": data_dir_status,
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


@app.get("/api/v1/config/api-keys", tags=["System"])
def get_api_key_status():
    """Return which API keys are configured (boolean status only, no secrets)."""
    providers = {
        "anthropic": {
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "env_var": "ANTHROPIC_API_KEY",
        },
        "openai": {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "env_var": "OPENAI_API_KEY",
        },
        "xai": {
            "configured": bool(os.getenv("XAI_API_KEY")),
            "env_var": "XAI_API_KEY",
        },
        "google": {
            "configured": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
            "env_var": "GOOGLE_API_KEY",
        },
    }
    return {"providers": providers}


@app.put("/api/v1/config/providers", tags=["System"])
def update_providers(body: dict):
    """Update default/fallback provider selection (saves to config.yaml)."""
    import yaml
    from api.auth import require_role
    config_path = _PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        return {"status": "error", "detail": "config.yaml not found"}
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    llm = config.setdefault("llm", {})
    if "default_provider" in body:
        llm["default_provider"] = body["default_provider"]
    if "fallback_provider" in body:
        llm["fallback_provider"] = body["fallback_provider"]
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)
    # Clear cached config so next request sees updated values
    from api.deps import get_config
    get_config.cache_clear()
    return {"status": "updated"}
