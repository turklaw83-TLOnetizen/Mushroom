"""
Passive background OCR worker.

Automatically processes uploaded PDFs and images using the AI vision model,
storing results in OCRCache so that analysis ingestion can use cached text
instead of re-running OCR.

Runs as a daemon thread — one per case, started on file upload or case open.
"""
import atexit
import json
import logging
import os
import threading
import time
import base64
from datetime import datetime
from pathlib import Path

from core.config import CONFIG
from core.llm import get_llm
from core.ingest import DocumentIngester, OCRCache

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = str(_PROJECT_ROOT / "data" / "cases")

# Singleton guard: one worker thread per case
_active_workers: dict = {}  # {case_id: threading.Thread}
_stop_flags: dict = {}  # {case_id: threading.Event}

# Priority queue: files the user wants OCR'd immediately
_priority_files: dict = {}  # {case_id: [file_key, ...]}
_priority_lock = threading.Lock()

# File extensions that may need AI vision OCR
_OCR_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
# File extensions that never need OCR (text-extractable)
_SKIP_EXTENSIONS = {".docx", ".txt", ".csv", ".xlsx", ".xls",
                    ".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga",
                    ".webm", ".avi", ".mov", ".mkv", ".ogg", ".flac", ".aac"}


# --- Status Management ---

def _status_path(case_id: str) -> str:
    return os.path.join(DATA_DIR, case_id, "ocr_status.json")


def _set_status(case_id: str, **kwargs):
    """Write OCR worker status to disk (atomic-ish)."""
    path = _status_path(case_id)
    # Read existing, merge
    existing = get_ocr_status(case_id)
    existing.update(kwargs)
    existing["updated_at"] = datetime.now().isoformat()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = f"{path}.tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(existing, f)
        os.replace(temp, path)
    except Exception as e:
        logger.warning(f"Error writing OCR status: {e}")


def get_ocr_status(case_id: str) -> dict:
    """Read OCR worker status from disk. Includes stale detection."""
    path = _status_path(case_id)
    if not os.path.exists(path):
        return {"status": "idle", "files_done": 0, "files_total": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"status": "idle", "files_done": 0, "files_total": 0}

    # Stale detection
    if data.get("status") == "running":
        updated = data.get("updated_at", "")
        if updated:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
                if age > 600:  # 10 minutes with no update = dead thread
                    logger.warning(f"OCR worker stale for {case_id} ({int(age)}s). Resetting.")
                    data["status"] = "idle"
            except Exception:
                pass

    return data


def prioritize_file(case_id: str, file_key: str):
    """Push a file to the front of the OCR priority queue."""
    with _priority_lock:
        q = _priority_files.setdefault(case_id, [])
        if file_key not in q:
            q.insert(0, file_key)


def _get_priority_files(case_id: str) -> list:
    """Get and clear priority files for a case."""
    with _priority_lock:
        return _priority_files.pop(case_id, [])


# --- Worker Thread ---

def _run_ocr_thread(case_id: str, case_mgr, model_provider: str):
    """The actual passive OCR worker thread."""
    try:
        import pymupdf
        import concurrent.futures

        _set_status(case_id, status="running", current_file="", files_done=0,
                    files_total=0, current_page=0, total_pages=0, error=None)

        # Get vision model
        vision_llm = get_llm(model_provider) if model_provider else None
        if not vision_llm:
            _set_status(case_id, status="idle",
                        message="No AI model configured — OCR requires an API key.")
            return

        ingester = DocumentIngester()
        ocr_cache = OCRCache(os.path.join(DATA_DIR, case_id))

        all_files = case_mgr.get_case_files(case_id)
        if not all_files:
            _set_status(case_id, status="idle", files_done=0, files_total=0)
            return

        # Build work list: files that need OCR
        work_list = []
        skipped = 0
        for fpath in all_files:
            fname = os.path.basename(fpath)
            ext = os.path.splitext(fname)[1].lower()
            try:
                fsize = os.path.getsize(fpath)
                file_key = OCRCache.file_key(fname, fsize)
            except OSError:
                continue

            status = ocr_cache.get_status(file_key)
            if status == "done":
                skipped += 1
                continue
            if ext in _SKIP_EXTENSIONS:
                # Mark text-based files as skipped so they show a badge
                if status is None:
                    ocr_cache.set_skipped(file_key, fname)
                skipped += 1
                continue
            if ext in _OCR_EXTENSIONS:
                work_list.append((fpath, fname, file_key, ext))

        total = len(work_list)
        _set_status(case_id, status="running", files_done=skipped,
                    files_total=skipped + total, files_needing_ocr=total)

        if total == 0:
            _set_status(case_id, status="idle", files_done=skipped,
                        files_total=skipped, message="All files processed.")
            return

        stop_event = _stop_flags.get(case_id)
        done_count = 0

        for fpath, fname, file_key, ext in work_list:
            if stop_event and stop_event.is_set():
                _set_status(case_id, status="idle", message="Stopped by user.")
                return

            # Check for priority files — if there are priority items, process them first
            priority = _get_priority_files(case_id)
            if priority:
                # Re-order: put priority files at front
                priority_set = set(priority)
                remaining = [(fp, fn, fk, ex) for fp, fn, fk, ex in work_list[done_count:]
                             if fk in priority_set]
                non_priority = [(fp, fn, fk, ex) for fp, fn, fk, ex in work_list[done_count:]
                                if fk not in priority_set]
                # Process priority file(s) immediately
                for p_fpath, p_fname, p_fkey, p_ext in remaining:
                    _process_single_file(
                        case_id, p_fpath, p_fname, p_fkey, p_ext,
                        ocr_cache, ingester, vision_llm, stop_event,
                        skipped + done_count, skipped + total,
                    )
                    done_count += 1

            # Skip if already processed (might have been done as priority)
            if ocr_cache.get_status(file_key) == "done":
                done_count += 1
                continue

            _process_single_file(
                case_id, fpath, fname, file_key, ext,
                ocr_cache, ingester, vision_llm, stop_event,
                skipped + done_count, skipped + total,
            )
            done_count += 1

        _set_status(case_id, status="idle", files_done=skipped + done_count,
                    files_total=skipped + total, message="All files processed.",
                    current_file="")

    except Exception as e:
        logger.warning(f"OCR worker error for {case_id}: {e}")
        _set_status(case_id, status="idle", error=str(e))
    finally:
        _active_workers.pop(case_id, None)
        _stop_flags.pop(case_id, None)


def _process_single_file(case_id, fpath, fname, file_key, ext,
                          ocr_cache, ingester, vision_llm, stop_event,
                          done_so_far, total_files):
    """Process a single file for OCR."""
    import pymupdf
    import concurrent.futures

    _set_status(case_id, status="running", current_file=fname,
                files_done=done_so_far, files_total=total_files,
                current_page=0, total_pages=0)

    try:
        if ext == ".pdf":
            # Use context manager to guarantee file handle release even on exception
            with pymupdf.open(fpath) as doc:
                num_pages = doc.page_count
                pages_done = ocr_cache.get_pages_done(file_key)

                ocr_cache.set_in_progress(file_key, fname, pages_done, num_pages)
                _set_status(case_id, current_page=pages_done, total_pages=num_pages)

                for page_num in range(num_pages):
                    if stop_event and stop_event.is_set():
                        return

                    # Skip pages already cached (resumption)
                    if page_num < pages_done and ocr_cache.get_page_text(file_key, page_num) is not None:
                        continue

                    page = doc[page_num]
                    text = page.get_text().strip()
                    needs_ocr = False

                    if len(text) < 50:
                        needs_ocr = True
                    else:
                        quality = ingester._assess_text_quality(text)
                        if quality["score"] < 60:
                            needs_ocr = True

                    if needs_ocr:
                        # Render page and send to vision model
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                        image_data = base64.b64encode(pix.tobytes("png")).decode("utf-8")

                        try:
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(
                                    ingester._transcribe_image_content,
                                    image_data, "image/png", vision_llm,
                                )
                                ocr_text = future.result(timeout=300)  # 5 min per page
                        except concurrent.futures.TimeoutError:
                            logger.warning(f"OCR timeout on {fname} page {page_num + 1}")
                            ocr_text = text or "[OCR timeout]"
                        except Exception as e:
                            logger.warning(f"OCR error on {fname} page {page_num + 1}: {e}")
                            ocr_text = text or ""

                        page_text = ocr_text if ocr_text else text
                    else:
                        page_text = text

                    ocr_cache.store_page_text(file_key, page_num, page_text)
                    # Update manifest progress
                    ocr_cache.set_in_progress(file_key, fname, page_num + 1, num_pages)
                    _set_status(case_id, current_page=page_num + 1, total_pages=num_pages)

            # Finalize: concatenate all pages → single .txt
            ocr_cache.finalize_file(file_key, fname, num_pages)

        elif ext in (".jpg", ".jpeg", ".png"):
            # Image files — always OCR
            _set_status(case_id, current_page=0, total_pages=1)

            with open(fpath, "rb") as img_f:
                image_data = base64.b64encode(img_f.read()).decode("utf-8")

            img_ext = ext.replace(".", "")
            if img_ext == "jpg":
                img_ext = "jpeg"
            media_type = f"image/{img_ext}"

            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        ingester._transcribe_image_content,
                        image_data, media_type, vision_llm,
                    )
                    text = future.result(timeout=300)
            except concurrent.futures.TimeoutError:
                logger.warning(f"OCR timeout on image {fname}")
                text = "[OCR timeout]"
            except Exception as e:
                logger.warning(f"OCR error on image {fname}: {e}")
                text = ""

            if text and text.strip():
                ocr_cache.store_text(file_key, text, fname)
            else:
                ocr_cache.set_skipped(file_key, fname)

            _set_status(case_id, current_page=1, total_pages=1)

    except Exception as e:
        logger.warning(f"OCR worker failed on {fname}: {e}")
        ocr_cache.set_status(file_key, "error", fname)


# --- Public API ---

def start_ocr_worker(case_id: str, case_mgr, model_provider: str) -> bool:
    """Start passive OCR worker for a case. Returns True if started."""
    # Check if already running
    existing = _active_workers.get(case_id)
    if existing and existing.is_alive():
        return False

    # Check status for stale detection
    status = get_ocr_status(case_id)
    if status.get("status") == "running":
        return False  # Already running (or stale — get_ocr_status auto-resets after 10 min)

    stop_event = threading.Event()
    _stop_flags[case_id] = stop_event

    thread = threading.Thread(
        target=_run_ocr_thread,
        args=(case_id, case_mgr, model_provider),
        daemon=True,
    )
    _active_workers[case_id] = thread
    thread.start()
    return True


def stop_ocr_worker(case_id: str):
    """Request the OCR worker to stop."""
    stop_event = _stop_flags.get(case_id)
    if stop_event:
        stop_event.set()
    _set_status(case_id, status="idle", message="Stopping...")


# --- Graceful Shutdown ---

def _cleanup_ocr_workers():
    """atexit handler: signal all OCR workers to stop."""
    for cid in list(_stop_flags.keys()):
        stop_ocr_worker(cid)
    for cid, thr in list(_active_workers.items()):
        if thr.is_alive():
            logger.info("Waiting for OCR thread %s to finish...", cid)
            thr.join(timeout=5)


atexit.register(_cleanup_ocr_workers)
