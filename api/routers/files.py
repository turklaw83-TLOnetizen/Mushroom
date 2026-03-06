# ---- Files Router --------------------------------------------------------
# File upload, download, and management for case documents.
#
# Upload/download use `async def` (they do async file reads via UploadFile).
# All other endpoints use sync `def` for thread-pooled Postgres safety.

import logging
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/files", tags=["Files"])


# ---- Response Models (Fix #6) -------------------------------------------

class FileInfo(BaseModel):
    filename: str
    size: int = 0
    tags: List[str] = []
    pinned: bool = False


class UploadResult(BaseModel):
    uploaded: List[FileInfo]
    count: int


# ---- Endpoints -----------------------------------------------------------

@router.get("", response_model=List[FileInfo])
def list_files(case_id: str, user: dict = Depends(get_current_user)):
    """List all source document files for a case."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")

    file_paths = cm.get_case_files(case_id)
    tags = cm.storage.get_file_tags(case_id)
    pinned_files = cm.get_pinned_files(case_id)

    files = []
    for fp in file_paths:
        basename = os.path.basename(fp)
        try:
            size = os.path.getsize(fp)
        except OSError:
            size = 0
        files.append(FileInfo(
            filename=basename,
            size=size,
            tags=tags.get(basename, []),
            pinned=basename in pinned_files,
        ))
    # Sort pinned files to the top
    files.sort(key=lambda f: (not f.pinned, f.filename))
    return files


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UploadResult)
async def upload_files(
    case_id: str,
    files: List[UploadFile] = File(...),
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Upload one or more files to a case (async for file I/O)."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")

    uploaded = []
    for f in files:
        if not f.filename:
            continue
        # Fix #6: Use os.path.basename for proper sanitization
        safe_name = os.path.basename(f.filename)
        if not safe_name or safe_name.startswith("."):
            raise HTTPException(status_code=400, detail=f"Invalid filename: {f.filename}")

        data = await f.read()
        path = cm.save_file(case_id, data, safe_name)
        uploaded.append(FileInfo(filename=safe_name, size=len(data)))

    return UploadResult(uploaded=uploaded, count=len(uploaded))


@router.get("/{filename}")
def download_file(
    case_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
):
    """Download a specific file from a case."""
    cm = get_case_manager()
    file_path = cm.get_file_path(case_id, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Security: verify path is within source_docs
    resolved = os.path.realpath(file_path)
    case_dir = os.path.realpath(cm.storage._source_docs_dir(case_id))
    if not resolved.startswith(case_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/{filename}")
def delete_file(
    case_id: str,
    filename: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a file from a case."""
    cm = get_case_manager()
    if not cm.delete_file(case_id, filename):
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "filename": filename}


@router.post("/{filename}/tags")
def update_file_tags(
    case_id: str,
    filename: str,
    tags: List[str],
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Update tags for a specific file."""
    cm = get_case_manager()
    all_tags = cm.storage.get_file_tags(case_id)
    all_tags[filename] = tags
    cm.storage.save_file_tags(case_id, all_tags)
    return {"status": "updated", "filename": filename, "tags": tags}


@router.post("/{filename}/pin")
def pin_file(
    case_id: str,
    filename: str,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Pin a file to the top of the file list."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")
    cm.pin_file(case_id, filename)
    return {"status": "pinned", "filename": filename}


@router.delete("/{filename}/pin")
def unpin_file(
    case_id: str,
    filename: str,
    user: dict = Depends(require_role("admin", "attorney", "paralegal")),
):
    """Unpin a file."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")
    cm.unpin_file(case_id, filename)
    return {"status": "unpinned", "filename": filename}
