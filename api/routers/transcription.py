# ---- Transcription Router ------------------------------------------------
# Audio/video transcription and status tracking.
# Wraps core/transcription_worker.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/transcription", tags=["Transcription"])


class TranscribeRequest(BaseModel):
    file_key: str
    language: str = "en"


@router.post("/start")
def start_transcription(
    case_id: str,
    body: TranscribeRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Start transcription of an audio/video file."""
    try:
        from core.transcription_worker import transcribe_file
        result = transcribe_file(case_id, body.file_key, language=body.language)
        return {"status": "started", "job_id": result}
    except Exception as e:
        logger.exception("Failed to start transcription")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs")
def list_jobs(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all transcription jobs for a case."""
    try:
        from core.transcription_worker import list_transcription_jobs
        return {"items": list_transcription_jobs(case_id)}
    except Exception as e:
        logger.exception("Failed to list transcription jobs")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}")
def get_job_status(
    case_id: str,
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """Get status + result of a transcription job."""
    try:
        from core.transcription_worker import get_transcription_status
        status = get_transcription_status(case_id, job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get transcription job status")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Bookmark Schemas & Endpoints ----------------------------------------

class BookmarkRequest(BaseModel):
    file_key: str = Field(..., max_length=500)
    timestamp_seconds: int = Field(..., ge=0)
    label: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=5000)


@router.get("/bookmarks")
def list_bookmarks(
    case_id: str,
    file_key: str = "",
    user: dict = Depends(get_current_user),
):
    """List transcript bookmarks, optionally filtered by file."""
    from core.transcription_worker import get_bookmarks
    return {"items": get_bookmarks(case_id, file_key)}


@router.post("/bookmarks")
def create_bookmark(
    case_id: str,
    body: BookmarkRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Create a bookmark on a transcript timestamp."""
    from core.transcription_worker import add_bookmark
    bm_id = add_bookmark(
        case_id=case_id,
        file_key=body.file_key,
        timestamp_seconds=body.timestamp_seconds,
        label=body.label,
        note=body.note,
        created_by=user.get("name", user.get("user_id", "")),
    )
    return {"id": bm_id, "status": "created"}


@router.delete("/bookmarks/{bookmark_id}")
def remove_bookmark(
    case_id: str,
    bookmark_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a transcript bookmark."""
    from core.transcription_worker import delete_bookmark
    if not delete_bookmark(case_id, bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}
