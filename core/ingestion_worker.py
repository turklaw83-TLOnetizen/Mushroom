import atexit
import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime

from pathlib import Path

from core.config import CONFIG
from core.llm import get_llm
from core.ingest import DocumentIngester, OCRCache

# Resolve data directory (same layout as original case_manager.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = str(_PROJECT_ROOT / "data" / "cases")

logger = logging.getLogger(__name__)


def _save_file_cache(cache_path: str, file_cache: dict):
    """Atomically save the ingestion file cache to disk.

    Called after each file is processed so progress is never lost on crash.
    """
    try:
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(file_cache, f)
        os.replace(tmp, cache_path)
    except Exception as e:
        logger.warning("Incremental cache write failed: %s", e)


# --- Status Management ---

def _status_path(case_id: str) -> str:
    """Returns the path to the current ingestion status file."""
    return os.path.join(DATA_DIR, case_id, "ingestion_status.json")

def set_ingestion_status(case_id: str, status: str, progress: int = 0, message: str = "",
                         error=None, failed_file: str = "", error_detail: str = ""):
    """
    Writes the current ingestion status to disk.
    status can be: "running", "completed", "error", "file_error", or "none"
    "file_error" means a single file failed and the worker is paused waiting
    for the user to choose Skip or Retry.
    """
    # If starting a new run, clear out any old errors and decisions
    if status == "running" and progress == 0:
        error = None
        _clear_decision(case_id)

    data = {
        "status": status,
        "progress": progress,
        "message": message,
        "updated_at": datetime.now().isoformat(),
        "error": error,
        "failed_file": failed_file,
        "error_detail": error_detail,
    }

    path = _status_path(case_id)
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Write atomically-ish by writing then renaming
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp_path, path)
    except Exception as e:
        logger.warning(f"Error saving ingestion status: {e}")

def get_ingestion_status(case_id: str) -> dict:
    """Reads the current ingestion status from disk.
    Includes stale detection: auto-resets to 'none' if status is 'running'
    but hasn't been updated in over 5 minutes (dead worker thread).
    """
    path = _status_path(case_id)
    if not os.path.exists(path):
        return {"status": "none", "progress": 0, "message": ""}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Error reading ingestion status: {e}")
        return {"status": "none", "progress": 0, "message": ""}

    # Stale detection: if "running" but no update in 5 min, the worker thread is dead
    if data.get("status") == "running":
        updated_at = data.get("updated_at", "")
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at)
                age_secs = (datetime.now() - last_update).total_seconds()
                if age_secs > 300:  # 5 minutes
                    logger.warning(
                        f"Ingestion status stale for {case_id} ({int(age_secs)}s). "
                        f"Auto-resetting from 'running' to 'none'."
                    )
                    clear_ingestion_status(case_id)
                    return {"status": "none", "progress": 0, "message": ""}
            except Exception as e:
                logger.warning("Failed to parse ingestion status timestamp for %s: %s", case_id, e)

    return data

def clear_ingestion_status(case_id: str):
    """Deletes the ingestion status file."""
    path = _status_path(case_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.debug("Failed to remove ingestion status file for %s: %s", case_id, e)


# --- Decision File (UI → Worker communication) ---

def _decision_path(case_id: str) -> str:
    return os.path.join(DATA_DIR, case_id, "ingestion_decision.json")


def _clear_decision(case_id: str):
    path = _decision_path(case_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.debug("Failed to remove ingestion decision file for %s: %s", case_id, e)


def write_ingestion_decision(case_id: str, action: str):
    """Called by the UI when the user clicks Skip or Retry on a failed file.
    action: "skip" or "retry"
    """
    path = _decision_path(case_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"action": action}, f)
    except Exception as e:
        logger.warning(f"Error writing ingestion decision: {e}")


def _read_decision(case_id: str) -> str | None:
    """Returns the user's decision ("skip" or "retry") or None if not yet decided."""
    path = _decision_path(case_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("action")
    except Exception:
        return None


def _wait_for_user_decision(case_id: str, fname: str, error_msg: str,
                            base_pct: int, timeout: int = 600) -> str:
    """Pause the worker and wait for the user to decide Skip or Retry.
    Sets status to 'file_error' and polls for a decision file.
    Returns 'skip' or 'retry'. Defaults to 'skip' on timeout.
    """
    _clear_decision(case_id)
    set_ingestion_status(
        case_id, "file_error", base_pct,
        f"Error processing {fname}. Waiting for your decision...",
        error=error_msg, failed_file=fname, error_detail=error_msg,
    )

    start = time.time()
    while time.time() - start < timeout:
        decision = _read_decision(case_id)
        if decision in ("skip", "retry"):
            _clear_decision(case_id)
            return decision
        time.sleep(1)

    # Timeout — treat as skip but log it
    logger.warning(f"Timed out waiting for user decision on {fname} (waited {timeout}s). Skipping.")
    _clear_decision(case_id)
    return "skip"


# --- Background Worker Thread ---

def _run_ingestion_thread(case_id: str, case_mgr, model_provider: str, force_ocr: bool):
    """
    The actual worker thread.
    Takes the monolithic block of code from app.py and runs it safely in the background.
    """
    try:
        set_ingestion_status(case_id, "running", 0, "Initializing ingestion engine...")

        all_case_files = case_mgr.get_case_files(case_id)
        if not all_case_files:
            set_ingestion_status(case_id, "completed", 100, "No files found to ingest.")
            return

        ingester = DocumentIngester()
        all_docs = []           # flushed to vectorstore periodically to limit memory
        _total_embedded = 0
        vision_llm = get_llm(model_provider) if model_provider else None

        # We need the OCRCache initialized with the correct case directory footprint just like in ingest.py
        ocr_cache = OCRCache(os.path.join(DATA_DIR, case_id))

        # Load per-file ingestion cache
        cache_path = os.path.join(DATA_DIR, case_id, "ingestion_cache.json")
        file_cache = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as cf:
                    file_cache = json.load(cf)
            except Exception:
                file_cache = {}

        skipped_count = 0
        total_files = len(all_case_files)

        for fi, fpath in enumerate(all_case_files):
            # Calculate base progress (up to 90% for file processing)
            base_pct = int((90 * fi) / max(total_files, 1))
            fname = os.path.basename(fpath)

            # Compute file key for cache lookup
            try:
                fsize = os.path.getsize(fpath)
                file_key = f"{fname}:{fsize}"
            except OSError:
                file_key = fname

            if file_key in file_cache and type(file_cache) is dict and not force_ocr:
                set_ingestion_status(case_id, "running", base_pct, f"{fname} -- cached ({fi+1}/{total_files})")

                cached_docs = file_cache[file_key]
                from langchain_core.documents import Document as Doc
                for cd in cached_docs:
                    all_docs.append(Doc(page_content=cd["page_content"], metadata=cd.get("metadata", {})))

                # Backfill OCR cache if missing
                if ocr_cache.get_status(file_key) != "done":
                    cached_text = "\n\n".join(cd["page_content"] for cd in cached_docs if cd.get("page_content"))
                    if cached_text:
                        ocr_cache.store_text(file_key, cached_text, fname)

                # Auto-classify cached files with no tags
                try:
                    from core.ingest import auto_classify_file
                    _existing_tags = case_mgr.get_file_tags(case_id, fname)
                    if not _existing_tags:
                        _first_text = cached_docs[0].get("page_content", "")[:500] if cached_docs else ""
                        _auto_tag = auto_classify_file(fname, _first_text)
                        if _auto_tag:
                            case_mgr.set_file_tags(case_id, fname, [_auto_tag])
                            logger.info("Auto-classified cached %s as '%s'", fname, _auto_tag)
                except Exception as _cls_err:
                    logger.warning("Auto-classification failed for cached file %s: %s", fname, _cls_err)

                skipped_count += 1

                # Periodic vectorstore flush to limit memory pressure
                if len(all_docs) >= 200:
                    try:
                        ingester.add_to_vectorstore(case_id, all_docs)
                        _total_embedded += len(all_docs)
                        all_docs.clear()
                    except Exception as _vs_err:
                        logger.warning("Periodic vectorstore flush failed: %s", _vs_err)

                continue

            # Check transcription cache for media files (pre-transcribed on upload)
            _media_exts = {".mp4", ".mp3", ".wav", ".m4a", ".mpeg", ".mpga",
                           ".webm", ".avi", ".mov", ".mkv", ".ogg", ".flac", ".aac"}
            _file_ext = os.path.splitext(fname)[1].lower()
            if _file_ext in _media_exts:
                try:
                    from core.transcription_worker import get_cached_transcript
                    _tcached = get_cached_transcript(case_id, file_key)
                    if _tcached and _tcached.get("text"):
                        set_ingestion_status(
                            case_id, "running", base_pct,
                            f"{fname} -- using pre-transcribed ({fi+1}/{total_files})",
                        )
                        _tr_text = _tcached["text"]
                        from langchain_core.documents import Document as _TrDoc
                        _tr_meta = {
                            "source": fname,
                            "page": 1,
                            "file_path": fpath,
                            "type": "media_transcription",
                            "media_type": _tcached.get("media_type", "audio"),
                            "from_transcription_cache": True,
                        }
                        if _tcached.get("segments"):
                            _tr_meta["segments"] = json.dumps(_tcached["segments"])
                        if _tcached.get("duration_seconds"):
                            _tr_meta["duration_seconds"] = _tcached["duration_seconds"]

                        _tr_docs = ingester.text_splitter.create_documents(
                            [_tr_text], metadatas=[_tr_meta]
                        )
                        serializable_docs = [
                            {"page_content": d.page_content, "metadata": d.metadata}
                            for d in _tr_docs
                        ]
                        file_cache[file_key] = serializable_docs
                        _save_file_cache(cache_path, file_cache)
                        all_docs.extend(_tr_docs)
                        logger.info("Used pre-transcribed cache for %s", fname)
                        continue
                except ImportError:
                    pass
                except Exception as _tr_err:
                    logger.debug("Transcription cache miss for %s: %s", fname, _tr_err)

            # NEW OR MODIFIED FILE: Needs full Processing
            set_ingestion_status(case_id, "running", base_pct, f"Processing {fname} ({fi+1}/{total_files})...")

            # Heartbeat: refresh updated_at every 15s so UI knows worker is alive
            _heartbeat_stop = threading.Event()
            def _heartbeat():
                while not _heartbeat_stop.is_set():
                    _heartbeat_stop.wait(15)
                    if not _heartbeat_stop.is_set():
                        set_ingestion_status(
                            case_id, "running", base_pct,
                            f"Processing {fname} ({fi+1}/{total_files})...",
                        )
            _hb_thread = threading.Thread(target=_heartbeat, daemon=True)
            _hb_thread.start()

            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pf_executor:
                    _pf_future = _pf_executor.submit(
                        ingester.process_file_with_cache, fpath, ocr_cache,
                        vision_model=vision_llm, force_ocr=force_ocr,
                    )
                    # 30-minute timeout per file (OCR is usually cached; fallback is generous)
                    docs = _pf_future.result(timeout=1800)

                # Update OCR Cache for full-text search
                file_text = "\n\n".join(d.page_content for d in docs)
                if file_text.strip():
                    ocr_cache.store_text(file_key, file_text, fname)
                else:
                    ocr_cache.set_skipped(file_key, fname)

                # Update Ingestion File Cache (save immediately so no data lost on crash)
                serializable_docs = [
                    {"page_content": d.page_content, "metadata": d.metadata}
                    for d in docs
                ]
                file_cache[file_key] = serializable_docs
                _save_file_cache(cache_path, file_cache)
                all_docs.extend(docs)

                # Auto-classify newly processed files with no tags
                try:
                    from core.ingest import auto_classify_file
                    _existing_tags = case_mgr.get_file_tags(case_id, fname)
                    if not _existing_tags:
                        _first_text = docs[0].page_content[:500] if docs and hasattr(docs[0], "page_content") else ""
                        _auto_tag = auto_classify_file(fname, _first_text)
                        if _auto_tag:
                            case_mgr.set_file_tags(case_id, fname, [_auto_tag])
                            logger.info("Auto-classified %s as '%s'", fname, _auto_tag)
                except Exception as _cls_err:
                    logger.warning("Auto-classification failed for file %s: %s", fname, _cls_err)

            except concurrent.futures.TimeoutError:
                logger.warning(f"Processing {fname} timed out after 30 minutes -- auto-skipping")
                set_ingestion_status(case_id, "running", base_pct, f"Skipped {fname} (timed out after 30 min)")
                ocr_cache.set_status(file_key, "error", fname)
                continue
            except Exception as e:
                error_msg = f"Failed extracting {fname}: {e}"
                logger.warning(error_msg)
                ocr_cache.set_status(file_key, "error", fname)

                # Pause and ask the user what to do
                decision = _wait_for_user_decision(case_id, fname, str(e), base_pct)

                if decision == "retry":
                    # Re-attempt this file once
                    set_ingestion_status(case_id, "running", base_pct, f"Retrying {fname}...")
                    try:
                        docs = ingester.process_file(fpath, vision_model=vision_llm, force_ocr=force_ocr)
                        file_text = "\n\n".join(d.page_content for d in docs)
                        if file_text.strip():
                            ocr_cache.store_text(file_key, file_text, fname)
                        else:
                            ocr_cache.set_skipped(file_key, fname)
                        serializable_docs = [
                            {"page_content": d.page_content, "metadata": d.metadata}
                            for d in docs
                        ]
                        file_cache[file_key] = serializable_docs
                        _save_file_cache(cache_path, file_cache)
                        all_docs.extend(docs)
                    except Exception as retry_err:
                        retry_msg = f"Retry also failed for {fname}: {retry_err}"
                        logger.warning(retry_msg)
                        ocr_cache.set_status(file_key, "error", fname)
                        # Ask again after retry failure
                        decision2 = _wait_for_user_decision(case_id, fname, retry_msg, base_pct)
                        if decision2 == "skip":
                            set_ingestion_status(case_id, "running", base_pct, f"Skipped {fname} (user choice).")
                        else:
                            # Second retry — last attempt
                            set_ingestion_status(case_id, "running", base_pct, f"Final retry for {fname}...")
                            try:
                                docs = ingester.process_file(fpath, vision_model=vision_llm, force_ocr=force_ocr)
                                file_text = "\n\n".join(d.page_content for d in docs)
                                if file_text.strip():
                                    ocr_cache.store_text(file_key, file_text, fname)
                                else:
                                    ocr_cache.set_skipped(file_key, fname)
                                serializable_docs = [
                                    {"page_content": d.page_content, "metadata": d.metadata}
                                    for d in docs
                                ]
                                file_cache[file_key] = serializable_docs
                                _save_file_cache(cache_path, file_cache)
                                all_docs.extend(docs)
                            except Exception:
                                set_ingestion_status(case_id, "running", base_pct, f"Skipped {fname} after 2 retries.")
                else:
                    set_ingestion_status(case_id, "running", base_pct, f"Skipped {fname} (user choice).")
            finally:
                # Stop heartbeat for this file
                _heartbeat_stop.set()
                _hb_thread.join(timeout=2)

            # Periodic vectorstore flush to limit memory pressure (after processed files)
            if len(all_docs) >= 200:
                try:
                    ingester.add_to_vectorstore(case_id, all_docs)
                    _total_embedded += len(all_docs)
                    all_docs.clear()
                except Exception as _vs_err:
                    logger.warning("Periodic vectorstore flush failed: %s", _vs_err)

        # Final cache save (safety net — each file is already saved incrementally)
        set_ingestion_status(case_id, "running", 92, "Finalizing cache...")
        _save_file_cache(cache_path, file_cache)

        # Flush any remaining docs to vectorstore
        if all_docs:
            set_ingestion_status(
                case_id, "running", 95,
                f"Embedding final batch... ({len(all_docs)} docs)"
            )
            try:
                ingester.add_to_vectorstore(case_id, all_docs)
                _total_embedded += len(all_docs)
            except Exception as _vs_err:
                logger.warning("Final vectorstore flush failed: %s", _vs_err)
            all_docs.clear()

        # Finish
        set_ingestion_status(case_id, "completed", 100, f"Processing complete! {total_files} files ready.")

    except Exception as e:
        error_tb = traceback.format_exc()
        logger.warning(f"Ingestion Error: {error_tb}")
        set_ingestion_status(case_id, "error", 100, f"Critical error during ingestion.", error=str(e))

# --- Active Thread Tracking & Graceful Shutdown ---

_active_ingestion_threads: dict = {}  # {case_id: threading.Thread}


def _cleanup_ingestion_threads():
    """atexit handler: wait briefly for running ingestion threads to finish."""
    for cid, thr in list(_active_ingestion_threads.items()):
        if thr.is_alive():
            logger.info("Waiting for ingestion thread %s to finish...", cid)
            thr.join(timeout=5)
            if thr.is_alive():
                logger.warning("Ingestion thread %s still running at exit.", cid)


atexit.register(_cleanup_ingestion_threads)


def start_background_ingestion(case_id: str, case_mgr, model_provider: str, force_ocr: bool = False):
    """
    Entry point to spawn the background thread.
    Returns True if started, False if already running.
    """
    status = get_ingestion_status(case_id)
    if status.get("status") == "running":
        return False

    set_ingestion_status(case_id, "running", 0, "Initializing background ingestion...")
    thread = threading.Thread(
        target=_run_ingestion_thread,
        args=(case_id, case_mgr, model_provider, force_ocr),
        daemon=True,
        name=f"ingestion-{case_id}",
    )
    _active_ingestion_threads[case_id] = thread
    thread.start()
    return True
