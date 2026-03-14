# ---- Analysis Router -----------------------------------------------------
# Start/stop background analysis, ingestion, and check status.
#
# Analysis/ingestion start endpoints use async because they call
# asyncio.to_thread for long-running operations. Status endpoints use sync.
#
# WORKER_MODE env var controls how background work is dispatched:
#   "thread" (default) — daemon threads (local dev / single-process API)
#   "queue"            — file-based queue for the worker container (Docker prod)

import asyncio
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_config, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/analysis", tags=["Analysis"])


def _load_excluded_files(case_id: str, data_dir: str) -> set:
    """Load the set of filenames excluded from analysis."""
    import json as _json
    path = os.path.join(data_dir, "cases", case_id, "excluded_files.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(_json.load(f))
    except (ValueError, IOError):
        return set()


def _load_documents_from_cache(case_id: str, cm, data_dir: str, model_provider: str) -> list:
    """Load documents from the ingestion cache, or auto-ingest if missing.

    Respects excluded_files.json — excluded files are skipped.
    """
    import json as _json
    from langchain_core.documents import Document

    cache_path = os.path.join(data_dir, "cases", case_id, "ingestion_cache.json")
    excluded = _load_excluded_files(case_id, data_dir)
    file_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                file_cache = _json.load(f)
        except (ValueError, IOError):
            file_cache = {}

    if file_cache:
        docs = []
        for file_key, cached_docs in file_cache.items():
            base_name = file_key.split(":")[0] if ":" in file_key else file_key
            if base_name in excluded or file_key in excluded:
                continue
            for cd in cached_docs:
                docs.append(Document(
                    page_content=cd.get("page_content", ""),
                    metadata=cd.get("metadata", {}),
                ))
        logger.info("Loaded %d documents from ingestion cache for case %s (excluded %d files)",
                     len(docs), case_id, len(excluded))
        return docs

    # No cache — auto-ingest
    logger.info("No ingestion cache for case %s — auto-ingesting", case_id)
    all_files = cm.get_case_files(case_id)
    if not all_files:
        return []

    from core.ingest import DocumentIngester, OCRCache
    from core.llm import get_llm

    ingester = DocumentIngester()
    ocr_cache = OCRCache(os.path.join(data_dir, "cases", case_id))
    vision_llm = get_llm(model_provider) if model_provider else None
    all_docs = []
    new_cache = {}

    for fpath in all_files:
        fname = os.path.basename(fpath)
        if fname in excluded:
            continue
        try:
            docs = ingester.process_file_with_cache(fpath, ocr_cache, vision_model=vision_llm)
            all_docs.extend(docs)
            new_cache[fname] = [
                {"page_content": d.page_content, "metadata": d.metadata} for d in docs
            ]
        except Exception as e:
            logger.warning("Failed to ingest %s: %s", fname, e)

    if new_cache:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                _json.dump(new_cache, f)
        except Exception:
            pass

    logger.info("Auto-ingested %d docs for case %s", len(all_docs), case_id)
    return all_docs

# Worker dispatch mode
WORKER_MODE = os.environ.get("WORKER_MODE", "thread")


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
        from core.bg_analysis import is_analysis_running

        if is_analysis_running(case_id, body.prep_id):
            raise HTTPException(
                status_code=409,
                detail="Analysis is already running for this preparation",
            )

        prep = cm.get_preparation(case_id, body.prep_id) or {}
        prep_type = prep.get("type", "trial")

        if WORKER_MODE == "queue":
            # Production: write a request file for the worker container
            from core.worker_queue import queue_worker_request
            request_id = queue_worker_request(
                get_data_dir(),
                "analysis",
                case_id=case_id,
                prep_id=body.prep_id,
                active_modules=list(body.active_modules) if body.active_modules else None,
                prep_type=prep_type,
                model_provider=provider,
            )
            return {
                "status": "queued",
                "request_id": request_id,
                "case_id": case_id,
                "prep_id": body.prep_id,
            }
        else:
            # Development: daemon thread (existing behavior)
            from core.bg_analysis import start_background_analysis

            state = cm.load_prep_state(case_id, body.prep_id) or {}

            # Load raw_documents from ingestion cache if not already present
            if not state.get("raw_documents"):
                state["raw_documents"] = _load_documents_from_cache(
                    case_id, cm, get_data_dir(), provider,
                )

            await asyncio.to_thread(
                start_background_analysis,
                case_id,
                body.prep_id,
                state,
                set(body.active_modules) if body.active_modules else None,
                prep_type,
                provider,
            )

            return {"status": "started", "case_id": case_id, "prep_id": body.prep_id}
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Analysis module not available: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to start analysis")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Failed to stop analysis")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Analysis status check failed")
        return {"status": "error", "error": "Failed to check status"}


# ---- Ingestion Endpoints -------------------------------------------------

@router.post("/ingestion/start")
async def start_ingestion(
    case_id: str,
    body: StartIngestionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Start background document ingestion."""
    config = get_config()
    provider = config.get("llm", {}).get("default_provider", "anthropic")

    try:
        if WORKER_MODE == "queue":
            # Production: write a request file for the worker container
            from core.worker_queue import queue_worker_request
            request_id = queue_worker_request(
                get_data_dir(),
                "ingestion",
                case_id=case_id,
                force_ocr=body.force_ocr,
                model_provider=provider,
            )
            return {
                "status": "queued",
                "request_id": request_id,
                "case_id": case_id,
            }
        else:
            # Development: daemon thread (existing behavior)
            cm = get_case_manager()
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
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.exception("Analysis status check failed")
        return {"status": "error", "error": "Failed to check status"}
