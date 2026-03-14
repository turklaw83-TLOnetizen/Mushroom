"""Background worker process for analysis, ingestion, and OCR tasks.

Polls the data directory for pending work requests and processes them using
the existing worker functions. Designed to run as a standalone Docker
container sharing a data volume with the API container.

Communication:
  - API writes request files to data/worker_requests/*.json
  - Worker picks them up, processes them, and removes them
  - Progress is communicated via the same JSON status files on disk
    (progress.json, ingestion_status.json, ocr_status.json)

Usage:
  python worker.py
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so core.* imports work
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env if present
from dotenv import load_dotenv
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(str(_ENV_PATH))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("worker")

# How often to check for new work (seconds)
POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))

# Graceful shutdown flag
_shutdown_requested = False


def _handle_signal(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — initiating graceful shutdown...", sig_name)
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def _get_case_manager():
    """Create a CaseManager backed by the appropriate storage backend."""
    from core.storage.json_backend import JSONStorageBackend
    from core.case_manager import CaseManager
    data_dir = os.environ.get("DATA_DIR", str(_PROJECT_ROOT / "data"))
    return CaseManager(JSONStorageBackend(data_dir))


def _load_or_ingest_documents(case_id: str, cm, model_provider: str) -> list:
    """Load documents from ingestion cache, or auto-ingest if cache is missing.

    Returns a list of LangChain Document objects ready for analysis.
    """
    from langchain_core.documents import Document

    data_dir = os.environ.get("DATA_DIR", str(_PROJECT_ROOT / "data"))
    cache_path = os.path.join(data_dir, "cases", case_id, "ingestion_cache.json")

    # Try loading from ingestion cache first
    file_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                file_cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            file_cache = {}

    if file_cache:
        docs = []
        for file_key, cached_docs in file_cache.items():
            for cd in cached_docs:
                docs.append(Document(
                    page_content=cd.get("page_content", ""),
                    metadata=cd.get("metadata", {}),
                ))
        logger.info("Loaded %d documents from ingestion cache for case %s", len(docs), case_id)
        return docs

    # No cache — auto-ingest all case files
    logger.info("No ingestion cache for case %s — auto-ingesting files", case_id)
    all_files = cm.get_case_files(case_id)
    if not all_files:
        logger.warning("No files found for case %s", case_id)
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
        try:
            docs = ingester.process_file_with_cache(
                fpath, ocr_cache, vision_model=vision_llm,
            )
            all_docs.extend(docs)
            new_cache[fname] = [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in docs
            ]
            # Store OCR text
            file_text = "\n\n".join(d.page_content for d in docs)
            if file_text.strip():
                try:
                    fsize = os.path.getsize(fpath)
                    file_key = f"{fname}:{fsize}"
                except OSError:
                    file_key = fname
                ocr_cache.store_text(file_key, file_text, fname)
        except Exception as e:
            logger.warning("Failed to ingest %s: %s", fname, e)

    # Save the cache for next time
    if new_cache:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(new_cache, f)
        except Exception as e:
            logger.warning("Failed to save ingestion cache: %s", e)

    logger.info("Auto-ingested %d documents from %d files for case %s",
                len(all_docs), len(all_files), case_id)
    return all_docs


def _process_analysis_request(request: dict):
    """Process an analysis work request."""
    from core.bg_analysis import is_analysis_running

    case_id = request["case_id"]
    prep_id = request["prep_id"]
    active_modules = request.get("active_modules")
    prep_type = request.get("prep_type", "trial")
    model_provider = request.get("model_provider", "anthropic")
    max_context_mode = request.get("max_context_mode", False)

    if is_analysis_running(case_id, prep_id):
        logger.warning(
            "Analysis already running for %s/%s — skipping request %s",
            case_id, prep_id, request["id"],
        )
        return

    # Build the state dict (same as what the API/UI passes)
    cm = _get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}

    # Enrich with metadata the analysis thread expects
    state.setdefault("case_id", case_id)
    state.setdefault("case_type", cm.get_case_type(case_id))
    state.setdefault("client_name", cm.get_client_name(case_id))
    state.setdefault("attorney_directives", cm.load_directives(case_id))
    state.setdefault("prep_type", prep_type)
    state.setdefault("_file_tags", cm.get_all_file_tags(case_id))

    # -- Load raw_documents from ingestion cache (or auto-ingest) --
    # Analysis nodes need state["raw_documents"] populated with Document objects.
    # The ingestion worker saves processed docs to ingestion_cache.json.
    state["raw_documents"] = _load_or_ingest_documents(
        case_id, cm, model_provider,
    )
    if not state["raw_documents"]:
        logger.error("No documents available for analysis — case %s has no files or ingestion failed", case_id)
        return

    if isinstance(active_modules, list):
        active_modules = set(active_modules)

    logger.info(
        "Starting analysis for case=%s prep=%s type=%s provider=%s",
        case_id, prep_id, prep_type, model_provider,
    )

    # Run in the CURRENT thread (not a daemon thread) so the worker
    # container keeps the process alive while it runs. We call the
    # internal _run_analysis_thread directly to avoid spawning another thread.
    from core.bg_analysis import _run_analysis_thread

    # Write initial progress (normally done by start_background_analysis)
    from core.bg_analysis import _write_progress
    from core.nodes.graph_builder import NODE_LABELS, get_node_count
    from datetime import datetime

    if active_modules and active_modules != set(NODE_LABELS.keys()):
        total_nodes = len(active_modules)
    else:
        total_nodes = get_node_count(prep_type)

    started_at = datetime.now().isoformat()
    _write_progress(case_id, prep_id, {
        "status": "running",
        "nodes_completed": 0,
        "total_nodes": total_nodes,
        "current_node": "Starting...",
        "current_description": "Launching analysis pipeline...",
        "started_at": started_at,
        "node_started_at": started_at,
        "est_tokens_so_far": 0,
        "per_node_times": {},
        "skipped_nodes": [],
        "completed_nodes": [],
        "stop_requested": False,
        "node_tokens": 0,
        "node_token_rate": 0,
        "node_pct": 0,
        "node_expected_tokens": 2000,
        "streamed_text": "",
    })

    _run_analysis_thread(
        case_id, prep_id, state, active_modules,
        prep_type, model_provider, max_context_mode,
    )

    logger.info("Analysis complete for case=%s prep=%s", case_id, prep_id)


def _process_ingestion_request(request: dict):
    """Process an ingestion work request."""
    from core.ingestion_worker import _run_ingestion_thread, get_ingestion_status, set_ingestion_status

    case_id = request["case_id"]
    force_ocr = request.get("force_ocr", False)
    model_provider = request.get("model_provider", "anthropic")

    status = get_ingestion_status(case_id)
    if status.get("status") == "running":
        logger.warning(
            "Ingestion already running for %s — skipping request %s",
            case_id, request["id"],
        )
        return

    cm = _get_case_manager()

    logger.info(
        "Starting ingestion for case=%s provider=%s force_ocr=%s",
        case_id, model_provider, force_ocr,
    )

    # Write initial status then run in current thread
    set_ingestion_status(case_id, "running", 0, "Initializing background ingestion...")
    _run_ingestion_thread(case_id, cm, model_provider, force_ocr)

    logger.info("Ingestion complete for case=%s", case_id)


def _process_ocr_request(request: dict):
    """Process an OCR work request."""
    from core.ocr_worker import _run_ocr_thread, get_ocr_status

    case_id = request["case_id"]
    model_provider = request.get("model_provider", "anthropic")

    status = get_ocr_status(case_id)
    if status.get("status") == "running":
        logger.warning(
            "OCR already running for %s — skipping request %s",
            case_id, request["id"],
        )
        return

    cm = _get_case_manager()

    logger.info("Starting OCR for case=%s provider=%s", case_id, model_provider)
    _run_ocr_thread(case_id, cm, model_provider)
    logger.info("OCR complete for case=%s", case_id)


# Dispatch table
_HANDLERS = {
    "analysis": _process_analysis_request,
    "ingestion": _process_ingestion_request,
    "ocr": _process_ocr_request,
}


def poll_for_work(data_dir: Path):
    """Check for pending worker requests and process them one at a time."""
    from core.worker_queue import _requests_dir

    req_dir = _requests_dir(str(data_dir))
    request_files = sorted(
        f for f in req_dir.glob("*.json")
        if f.is_file() and not f.name.startswith(".")
    )

    if not request_files:
        return

    # Process one request per poll cycle (so we can check shutdown between tasks)
    req_file = request_files[0]

    try:
        request = json.loads(req_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read request file %s: %s", req_file.name, e)
        _move_to_failed(req_file, str(e))
        return

    req_type = request.get("type", "")
    req_id = request.get("id", "unknown")
    handler = _HANDLERS.get(req_type)

    if handler is None:
        logger.error("Unknown request type '%s' in %s", req_type, req_file.name)
        _move_to_failed(req_file, f"Unknown request type: {req_type}")
        return

    logger.info(
        "Processing %s request %s from %s",
        req_type, req_id, req_file.name,
    )

    try:
        handler(request)
        # Success — remove the request file
        try:
            req_file.unlink()
        except Exception:
            pass
        logger.info("Completed %s request %s", req_type, req_id)

    except Exception as e:
        logger.exception("Error processing %s request %s: %s", req_type, req_id, e)
        _move_to_failed(req_file, str(e))


def _move_to_failed(req_file: Path, error: str):
    """Move a failed request to the failed/ subdirectory."""
    failed_dir = req_file.parent / "failed"
    failed_dir.mkdir(exist_ok=True)
    try:
        # Append error before moving
        request = json.loads(req_file.read_text(encoding="utf-8"))
        request["error"] = error
        request["failed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        dest = failed_dir / req_file.name
        dest.write_text(json.dumps(request, indent=2), encoding="utf-8")
        req_file.unlink()
    except Exception as e:
        logger.warning("Failed to move %s to failed/: %s", req_file.name, e)


def main():
    """Main worker loop — polls for work until SIGTERM."""
    global _shutdown_requested

    data_dir = Path(os.environ.get("DATA_DIR", str(_PROJECT_ROOT / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Worker starting — polling %s every %ds", data_dir, POLL_INTERVAL)
    logger.info("PID: %d, WORKER_POLL_INTERVAL: %d", os.getpid(), POLL_INTERVAL)

    while not _shutdown_requested:
        try:
            poll_for_work(data_dir)
        except Exception as e:
            logger.error("Poll cycle error: %s", e, exc_info=True)

        # Sleep in small increments so we can respond to SIGTERM quickly
        for _ in range(POLL_INTERVAL * 10):
            if _shutdown_requested:
                break
            time.sleep(0.1)

    logger.info("Worker shutting down gracefully.")


if __name__ == "__main__":
    main()
