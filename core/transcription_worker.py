"""
Background transcription worker.

Transcribes audio/video files using OpenAI Whisper immediately after upload,
so transcripts are pre-cached when full analysis ingestion runs later.

Follows the same daemon-thread + JSON-status pattern as ocr_worker.py.
"""
import atexit
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from core.ingest import DocumentIngester

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = str(_PROJECT_ROOT / "data" / "cases")

# Singleton guard: one worker thread per case
_active_workers: dict = {}   # {case_id: threading.Thread}
_stop_flags: dict = {}       # {case_id: threading.Event}

# Media extensions that Whisper can process
MEDIA_EXTENSIONS = {
    ".mp4", ".mp3", ".wav", ".m4a", ".mpeg", ".mpga",
    ".webm", ".avi", ".mov", ".mkv", ".ogg", ".flac", ".aac",
}


# --- Transcription Cache ---

def _cache_path(case_id: str) -> str:
    return os.path.join(DATA_DIR, case_id, "transcription_cache.json")


def _load_cache(case_id: str) -> dict:
    path = _cache_path(case_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(case_id: str, cache: dict):
    path = _cache_path(case_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = f"{path}.tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(temp, path)
    except Exception as e:
        logger.warning(f"Error writing transcription cache: {e}")


def get_cached_transcript(case_id: str, file_key: str) -> dict | None:
    """Returns cached transcript dict or None if not cached."""
    cache = _load_cache(case_id)
    return cache.get(file_key)


# --- Status Management ---

def _status_path(case_id: str) -> str:
    return os.path.join(DATA_DIR, case_id, "transcription_status.json")


def _set_status(case_id: str, **kwargs):
    """Write transcription worker status to disk."""
    path = _status_path(case_id)
    existing = get_transcription_status(case_id)
    existing.update(kwargs)
    existing["updated_at"] = datetime.now().isoformat()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = f"{path}.tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(existing, f)
        os.replace(temp, path)
    except Exception as e:
        logger.warning(f"Error writing transcription status: {e}")


def get_transcription_status(case_id: str) -> dict:
    """Read transcription worker status. Includes stale detection."""
    path = _status_path(case_id)
    if not os.path.exists(path):
        return {"status": "idle", "files_done": 0, "files_total": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"status": "idle", "files_done": 0, "files_total": 0}

    # Stale detection: 5 min with no update = dead thread
    if data.get("status") == "running":
        updated = data.get("updated_at", "")
        if updated:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
                if age > 300:
                    logger.warning(f"Transcription worker stale for {case_id} ({int(age)}s). Resetting.")
                    data["status"] = "idle"
            except Exception:
                pass

    return data


# --- Worker Thread ---

def _run_transcription_thread(case_id: str, case_mgr, file_paths: list):
    """The background transcription worker thread."""
    try:
        total = len(file_paths)
        _set_status(case_id, status="running", files_done=0, files_total=total,
                    current_file="", error=None)

        ingester = DocumentIngester()
        cache = _load_cache(case_id)
        stop_event = _stop_flags.get(case_id)
        done = 0

        for fpath in file_paths:
            if stop_event and stop_event.is_set():
                _set_status(case_id, status="idle", message="Stopped by user.")
                return

            fname = os.path.basename(fpath)
            try:
                fsize = os.path.getsize(fpath)
                file_key = f"{fname}:{fsize}"
            except OSError:
                file_key = fname

            # Skip if already cached
            if file_key in cache:
                done += 1
                _set_status(case_id, files_done=done, current_file=f"{fname} (cached)")
                continue

            _set_status(case_id, current_file=fname, files_done=done)

            # Heartbeat thread to keep status fresh
            _hb_stop = threading.Event()

            def _heartbeat():
                while not _hb_stop.is_set():
                    _hb_stop.wait(15)
                    if not _hb_stop.is_set():
                        _set_status(case_id, current_file=fname, files_done=done)

            _hb = threading.Thread(target=_heartbeat, daemon=True)
            _hb.start()

            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(ingester._process_media, fpath)
                    docs = future.result(timeout=1800)  # 30 min per file

                # Extract text and metadata from Documents
                text = "\n\n".join(d.page_content for d in docs)
                segments = []
                duration = 0
                media_type = "audio"
                if docs:
                    meta = docs[0].metadata
                    media_type = meta.get("media_type", "audio")
                    duration = meta.get("duration_seconds", 0)
                    seg_json = meta.get("segments", "")
                    if seg_json:
                        try:
                            segments = json.loads(seg_json)
                        except Exception:
                            pass

                cache[file_key] = {
                    "text": text,
                    "segments": segments,
                    "media_type": media_type,
                    "duration_seconds": duration,
                    "transcribed_at": datetime.now().isoformat(),
                }
                _save_cache(case_id, cache)
                logger.info(f"Transcribed {fname} ({len(text)} chars)")

            except concurrent.futures.TimeoutError:
                logger.warning(f"Transcription timeout on {fname} after 30 min")
                _set_status(case_id, error=f"Timeout on {fname}")
            except Exception as e:
                logger.warning(f"Transcription error on {fname}: {e}")
                _set_status(case_id, error=f"Error on {fname}: {e}")
            finally:
                _hb_stop.set()
                _hb.join(timeout=2)

            done += 1
            _set_status(case_id, files_done=done)

        _set_status(case_id, status="idle", files_done=done, files_total=total,
                    current_file="", message=f"Transcribed {done}/{total} files.")

    except Exception as e:
        logger.warning(f"Transcription worker error for {case_id}: {e}")
        _set_status(case_id, status="idle", error=str(e))
    finally:
        _active_workers.pop(case_id, None)
        _stop_flags.pop(case_id, None)


# --- Public API ---

def start_transcription_worker(case_id: str, case_mgr, file_paths: list) -> bool:
    """Start background transcription for a list of media files. Returns True if started."""
    existing = _active_workers.get(case_id)
    if existing and existing.is_alive():
        return False

    status = get_transcription_status(case_id)
    if status.get("status") == "running":
        return False

    # Filter to only media files
    media_paths = [
        fp for fp in file_paths
        if os.path.splitext(fp)[1].lower() in MEDIA_EXTENSIONS
    ]
    if not media_paths:
        return False

    stop_event = threading.Event()
    _stop_flags[case_id] = stop_event

    thread = threading.Thread(
        target=_run_transcription_thread,
        args=(case_id, case_mgr, media_paths),
        daemon=True,
    )
    _active_workers[case_id] = thread
    thread.start()
    return True


def stop_transcription_worker(case_id: str):
    """Request the transcription worker to stop."""
    stop_event = _stop_flags.get(case_id)
    if stop_event:
        stop_event.set()
    _set_status(case_id, status="idle", message="Stopping...")


def is_media_file(filename: str) -> bool:
    """Check if a filename is a media file that can be transcribed."""
    return os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS


# --- Graceful Shutdown ---

def _cleanup_transcription_threads():
    """atexit handler: signal all transcription workers to stop."""
    for cid in list(_stop_flags.keys()):
        stop_transcription_worker(cid)
    for cid, thr in list(_active_workers.items()):
        if thr.is_alive():
            logger.info("Waiting for transcription thread %s to finish...", cid)
            thr.join(timeout=5)


atexit.register(_cleanup_transcription_threads)
