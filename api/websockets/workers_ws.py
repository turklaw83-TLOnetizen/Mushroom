# ---- Worker Status WebSocket ---------------------------------------------
# Unified real-time stream of analysis, ingestion, and OCR worker status.
# Fix #4: WebSocket auth via query parameter token.
# Fix #5: Scan all prep dirs for analysis progress (not a fixed prep_id).

import asyncio
import glob
import json
import logging
import os

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate_ws(token: str) -> dict | None:
    """Verify a WebSocket token (same logic as HTTP auth)."""
    if not token:
        return None
    try:
        from api.auth import _verify_clerk_session, _verify_jwt, _get_clerk_secret_key

        # Try Clerk first
        if _get_clerk_secret_key():
            claims = await _verify_clerk_session(token)
            if claims:
                return {
                    "id": claims.get("sub", ""),
                    "role": claims.get("role", claims.get("public_metadata", {}).get("role", "attorney")),
                }
        # Fallback to legacy JWT
        claims = _verify_jwt(token)
        if claims:
            return {"id": claims.get("sub", ""), "role": claims.get("role", "attorney")}
    except Exception:
        pass
    return None


DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))


def _read_json_status(path: str, default: dict) -> dict:
    """Read a JSON status file from disk, returning default on any error."""
    if not os.path.exists(path):
        return dict(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return dict(default)


def _get_ingestion_status(case_id: str) -> dict:
    """Read ingestion status directly from disk (no heavy imports)."""
    path = os.path.join(DATA_DIR, "cases", case_id, "ingestion_status.json")
    return _read_json_status(path, {"status": "idle", "progress": 0, "message": ""})


def _get_ocr_status(case_id: str) -> dict:
    """Read OCR status directly from disk (no heavy imports)."""
    path = os.path.join(DATA_DIR, "cases", case_id, "ocr_status.json")
    return _read_json_status(path, {"status": "idle", "files_done": 0, "files_total": 0})


def _get_any_active_progress(case_id: str) -> dict:
    """Scan all prep directories for analysis progress.

    Returns the first running progress, or the most recently updated one,
    or {"status": "idle"} if no progress files exist.
    """
    preps_dir = os.path.join(DATA_DIR, "cases", case_id, "preparations")
    if not os.path.isdir(preps_dir):
        return {"status": "idle"}

    best = None
    best_ts = ""

    for progress_file in glob.glob(os.path.join(preps_dir, "*", "progress.json")):
        try:
            with open(progress_file, "r") as f:
                data = json.load(f)
            # If any prep is actively running, return it immediately
            if data.get("status") == "running":
                return data
            # Track the most recently updated progress
            updated = data.get("updated_at", "")
            if updated > best_ts:
                best_ts = updated
                best = data
        except (json.JSONDecodeError, IOError, OSError):
            continue

    return best or {"status": "idle"}


@router.websocket("/ws/workers/{case_id}")
async def worker_status_stream(
    websocket: WebSocket,
    case_id: str,
    token: str = Query(default=""),
):
    """
    Unified worker status stream for a case.

    Requires ?token=<jwt> query parameter for authentication.
    Polls analysis, ingestion, and OCR worker status every 500ms
    and sends JSON updates to the client. Stops when all workers
    are idle/complete/error.
    """
    # Fix #4: Authenticate before accepting
    user = await _authenticate_ws(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WebSocket connected for case %s (user: %s)", case_id, user.get("id"))

    idle_count = 0
    max_idle = 10  # Stop after 5s of all-idle

    try:
        while True:
            status = {}

            # Analysis progress — scan all prep dirs for any active progress
            try:
                status["analysis"] = _get_any_active_progress(case_id)
            except Exception:
                status["analysis"] = {"status": "idle"}

            # Ingestion status — read directly from disk (avoids heavy core imports)
            status["ingestion"] = _get_ingestion_status(case_id)

            # OCR status — read directly from disk
            status["ocr"] = _get_ocr_status(case_id)

            await websocket.send_json(status)

            # Check if all workers are idle — if so, increment counter
            all_idle = all(
                s.get("status") in (None, "idle", "complete", "error", "unavailable")
                for s in status.values()
            )
            if all_idle:
                idle_count += 1
                if idle_count >= max_idle:
                    await websocket.send_json({"_done": True})
                    break
            else:
                idle_count = 0

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for case %s", case_id)
    except Exception as e:
        logger.error("WebSocket error for case %s: %s", case_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
