# ---- Transcription Router ------------------------------------------------
# Audio/video transcription and status tracking.
# Wraps core/transcription_worker.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))
