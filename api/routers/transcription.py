# ---- Transcription Router ------------------------------------------------
# Audio/video transcription and status tracking.
# Wraps core/transcription_worker.py

import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/transcription", tags=["Transcription"])


class TranscribeRequest(BaseModel):
    file_key: str
    language: str = "en"


class AnnotationRequest(BaseModel):
    type: str
    content: str
    timestamp: float = 0.0


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
        return list_transcription_jobs(case_id)
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


@router.post("/jobs/{job_id}/annotations")
def add_annotation(
    case_id: str,
    job_id: str,
    body: AnnotationRequest,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Add an annotation to a transcription job."""
    import time
    import uuid
    try:
        from core.transcription_worker import get_transcription_status, save_transcription_annotation
        status = get_transcription_status(case_id, job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")

        annotation = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": body.timestamp,
            "type": body.type,
            "content": body.content,
            "created_by": user.get("name", user.get("id", "unknown")),
            "created_at": time.time(),
        }
        save_transcription_annotation(case_id, job_id, annotation)
        return annotation
    except HTTPException:
        raise
    except ImportError:
        # Fallback: store annotations in JSON storage if worker doesn't support it
        import json
        import os
        from pathlib import Path

        data_dir = Path(os.getenv("DATA_DIR", "data"))
        ann_file = data_dir / "cases" / case_id / "transcription" / f"{job_id}_annotations.json"
        ann_file.parent.mkdir(parents=True, exist_ok=True)

        annotations = []
        if ann_file.exists():
            try:
                annotations = json.loads(ann_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        annotation = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": body.timestamp,
            "type": body.type,
            "content": body.content,
            "created_by": user.get("name", user.get("id", "unknown")),
            "created_at": time.time(),
        }
        annotations.append(annotation)
        ann_file.write_text(json.dumps(annotations, default=str), encoding="utf-8")
        return annotation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
