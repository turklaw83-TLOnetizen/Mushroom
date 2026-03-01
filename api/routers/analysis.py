# ---- Analysis Router -----------------------------------------------------
# Start/stop background analysis, ingestion, and check status.
#
# Analysis/ingestion start endpoints use async because they call
# asyncio.to_thread for long-running operations. Status endpoints use sync.

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/analysis", tags=["Analysis"])


# ---- Schemas -------------------------------------------------------------

class StartAnalysisRequest(BaseModel):
    prep_id: str
    force_rerun: bool = False
    active_modules: Optional[List[str]] = None


class StartIngestionRequest(BaseModel):
    force_ocr: bool = False


class AnalysisStatusResponse(BaseModel):
    status: str = "idle"
    progress: float = 0.0
    current_module: str = ""
    error: str = ""

    model_config = {"extra": "allow"}


# ---- Analysis Endpoints --------------------------------------------------

@router.post("/start")
async def start_analysis(
    case_id: str,
    body: StartAnalysisRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Start background analysis for a case preparation."""
    cm = get_case_manager()
    config = get_config()
    provider = config.get("llm", {}).get("default_provider", "anthropic")

    try:
        from core.bg_analysis import start_background_analysis, is_analysis_running

        if is_analysis_running(case_id, body.prep_id):
            raise HTTPException(
                status_code=409,
                detail="Analysis is already running for this preparation",
            )

        await asyncio.to_thread(
            start_background_analysis,
            case_id,
            body.prep_id,
            cm,
            provider,
            force_rerun=body.force_rerun,
            active_modules=body.active_modules,
        )

        # Trigger notification
        from api.notify import notify_analysis_started
        notify_analysis_started(user["id"], case_id, body.prep_id, body.active_modules)

        return {"status": "started", "case_id": case_id, "prep_id": body.prep_id}
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Analysis module not available: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to start analysis")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
def stop_analysis(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Stop a running background analysis."""
    try:
        from core.bg_analysis import stop_background_analysis
        stop_background_analysis(case_id, prep_id)
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=AnalysisStatusResponse)
def analysis_status(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the current analysis progress."""
    try:
        from core.bg_analysis import get_analysis_progress
        progress = get_analysis_progress(case_id, prep_id)
        return progress or {"status": "idle"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---- Ingestion Endpoints -------------------------------------------------

@router.post("/ingestion/start")
async def start_ingestion(
    case_id: str,
    body: StartIngestionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Start background document ingestion."""
    cm = get_case_manager()
    config = get_config()
    provider = config.get("llm", {}).get("default_provider", "anthropic")

    try:
        from core.ingestion_worker import start_background_ingestion

        await asyncio.to_thread(
            start_background_ingestion,
            case_id,
            cm,
            provider,
            force_ocr=body.force_ocr,
        )

        return {"status": "started", "case_id": case_id}
    except Exception as e:
        logger.exception("Failed to start ingestion")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion/status", response_model=AnalysisStatusResponse)
def ingestion_status(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Get ingestion worker status."""
    try:
        from core.ingestion_worker import get_ingestion_status
        return get_ingestion_status(case_id) or {"status": "idle"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
