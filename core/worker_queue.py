"""Queue work requests for the background worker container.

In production Docker deployment (WORKER_MODE=queue), API endpoints write
JSON request files instead of spawning daemon threads. The standalone worker
container polls for these files and processes them using the existing worker
functions.

In development (WORKER_MODE=thread, the default), this module is not used
and the existing daemon-thread approach continues unchanged.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _requests_dir(data_dir: str) -> Path:
    """Return (and ensure) the worker requests directory."""
    d = Path(data_dir) / "worker_requests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def queue_worker_request(data_dir: str, request_type: str, **kwargs) -> str:
    """Write a worker request file. Returns request ID.

    Parameters
    ----------
    data_dir : str
        Root data directory (e.g. /app/data).
    request_type : str
        One of "analysis", "ingestion", "ocr".
    **kwargs
        Arbitrary parameters forwarded to the worker (case_id, prep_id, etc.).
    """
    req_dir = _requests_dir(data_dir)
    request_id = uuid.uuid4().hex[:12]

    # Timestamp prefix ensures sorted() processing order matches creation order
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")

    request = {
        "id": request_id,
        "type": request_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    # Write atomically: tmp -> rename
    filename = f"{ts}_{request_id}.json"
    req_file = req_dir / filename
    tmp_file = req_dir / f".{filename}.tmp"

    try:
        tmp_file.write_text(json.dumps(request, indent=2), encoding="utf-8")
        tmp_file.rename(req_file)
        logger.info("Queued %s request %s: %s", request_type, request_id, req_file.name)
    except Exception:
        # Fallback: write directly (less atomic but still works)
        req_file.write_text(json.dumps(request, indent=2), encoding="utf-8")
        logger.info("Queued %s request %s (direct write)", request_type, request_id)

    return request_id


def list_pending_requests(data_dir: str) -> list[dict]:
    """List pending worker requests, sorted by creation time."""
    req_dir = _requests_dir(data_dir)
    results = []
    for f in sorted(req_dir.glob("*.json")):
        if f.name.startswith("."):
            continue  # skip tmp files
        try:
            results.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning("Failed to read request file %s: %s", f.name, e)
    return results


def remove_request(data_dir: str, request_id: str) -> bool:
    """Remove a processed request file by ID. Returns True if found and removed."""
    req_dir = _requests_dir(data_dir)
    for f in req_dir.glob(f"*_{request_id}.json"):
        try:
            f.unlink()
            return True
        except Exception as e:
            logger.warning("Failed to remove request %s: %s", f.name, e)
    return False


def move_to_failed(data_dir: str, request_id: str, error: str = "") -> bool:
    """Move a failed request to the failed/ subdirectory."""
    req_dir = _requests_dir(data_dir)
    failed_dir = req_dir / "failed"
    failed_dir.mkdir(exist_ok=True)

    for f in req_dir.glob(f"*_{request_id}.json"):
        try:
            # Append error info before moving
            request = json.loads(f.read_text(encoding="utf-8"))
            request["failed_at"] = datetime.now(timezone.utc).isoformat()
            request["error"] = error

            dest = failed_dir / f.name
            dest.write_text(json.dumps(request, indent=2), encoding="utf-8")
            f.unlink()
            return True
        except Exception as e:
            logger.warning("Failed to move request %s to failed: %s", f.name, e)
    return False
