# ---- Analysis Router -----------------------------------------------------
# Start/stop background analysis, ingestion, and check status.
#
# Analysis/ingestion start endpoints use async because they call
# asyncio.to_thread for long-running operations. Status endpoints use sync.

import asyncio
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/analysis", tags=["Analysis"])

DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data")


# ---- Schemas -------------------------------------------------------------

class StartAnalysisRequest(BaseModel):
    prep_id: str
    force_rerun: bool = False
    active_modules: Optional[List[str]] = None
    model: Optional[str] = None
    max_context_mode: bool = True


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

    # Determine model provider: request override > config default
    provider = body.model or config.get("llm", {}).get("default_provider", "anthropic")

    try:
        from core.bg_analysis import start_background_analysis, is_analysis_running

        if is_analysis_running(case_id, body.prep_id):
            raise HTTPException(
                status_code=409,
                detail="Analysis is already running for this preparation",
            )

        # -- Build the state dict (mirrors Streamlit's case_view.py) --
        # Load prep metadata for type info
        prep_meta = cm.get_preparation(case_id, body.prep_id) or {}
        prep_type = prep_meta.get("type", "trial")
        prep_name = prep_meta.get("name", "Trial Preparation")

        # Load cached documents from ingestion cache
        all_docs = []
        all_paths = cm.get_case_files(case_id)
        cache_path = os.path.join(DATA_DIR, "cases", case_id, "ingestion_cache.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                for _key, doc_list in cache_data.items():
                    for doc in doc_list:
                        all_docs.append(
                            SimpleNamespace(
                                page_content=doc["page_content"],
                                metadata=doc.get("metadata", {}),
                            )
                        )
            except Exception as e:
                logger.warning("Failed to load ingestion cache: %s", e)

        if not all_docs and not body.force_rerun:
            raise HTTPException(
                status_code=400,
                detail="No cached documents found. Run ingestion first or use force_rerun.",
            )

        state = {
            "case_files": all_paths,
            "raw_documents": all_docs,
            "current_model": provider,
            "max_context_mode": body.max_context_mode,
            "case_id": case_id,
            "case_type": cm.get_case_type(case_id),
            "client_name": cm.get_client_name(case_id),
            "attorney_directives": cm.load_directives(case_id),
            "prep_type": prep_type,
            "prep_name": prep_name,
            "_file_tags": cm.get_all_file_tags(case_id),
        }

        # Convert active_modules list to set (as expected by bg_analysis)
        active_modules = set(body.active_modules) if body.active_modules else None

        await asyncio.to_thread(
            start_background_analysis,
            case_id,
            body.prep_id,
            state,
            active_modules,
            prep_type,
            provider,
            body.max_context_mode,
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
