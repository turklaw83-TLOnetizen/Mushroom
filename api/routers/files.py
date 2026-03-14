# ---- Files Router --------------------------------------------------------
# File upload, download, and management for case documents.
#
# Upload/download use `async def` (they do async file reads via UploadFile).
# All other endpoints use sync `def` for thread-pooled Postgres safety.

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/files", tags=["Files"])


# ---- Response Models (Fix #6) -------------------------------------------

class FileInfo(BaseModel):
    filename: str
    size: int = 0
    tags: List[str] = []
    pinned: bool = False
    uploaded_at: Optional[str] = None
    ingested_at: Optional[str] = None
    excluded: bool = False


class UploadResult(BaseModel):
    uploaded: List[FileInfo]
    count: int


# ---- Endpoints -----------------------------------------------------------

def _load_excluded_files(case_id: str) -> set:
    """Load the set of filenames excluded from analysis."""
    data_dir = get_data_dir()
    path = os.path.join(data_dir, "cases", case_id, "excluded_files.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        return set()


def _save_excluded_files(case_id: str, excluded: set):
    """Save the set of excluded filenames."""
    data_dir = get_data_dir()
    path = os.path.join(data_dir, "cases", case_id, "excluded_files.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(excluded), f)


def _load_ingestion_cache(case_id: str) -> dict:
    """Load the ingestion cache to check which files have been ingested."""
    data_dir = get_data_dir()
    cache_path = os.path.join(data_dir, "cases", case_id, "ingestion_cache.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        # Just get file modification time of the cache as proxy for ingestion time
        mtime = os.path.getmtime(cache_path)
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            "keys": set(cache.keys()),
            "mtime": datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
        }
    except (json.JSONDecodeError, IOError):
        return {}


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
    excluded_files = _load_excluded_files(case_id)
    ingestion_info = _load_ingestion_cache(case_id)
    ingested_keys = ingestion_info.get("keys", set())
    ingestion_mtime = ingestion_info.get("mtime")

    files = []
    for fp in file_paths:
        basename = os.path.basename(fp)
        try:
            stat = os.stat(fp)
            size = stat.st_size
            # Use file modification time as upload timestamp
            uploaded_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        except OSError:
            size = 0
            uploaded_at = None

        # Check if file was ingested (key format: "filename:size" or just "filename")
        file_key = f"{basename}:{size}" if size else basename
        is_ingested = file_key in ingested_keys or basename in ingested_keys

        files.append(FileInfo(
            filename=basename,
            size=size,
            tags=tags.get(basename, []),
            pinned=basename in pinned_files,
            uploaded_at=uploaded_at,
            ingested_at=ingestion_mtime if is_ingested else None,
            excluded=basename in excluded_files,
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


@router.post("/{filename}/exclude")
def exclude_file(
    case_id: str,
    filename: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Exclude a file from analysis."""
    excluded = _load_excluded_files(case_id)
    excluded.add(filename)
    _save_excluded_files(case_id, excluded)
    return {"status": "excluded", "filename": filename}


@router.delete("/{filename}/exclude")
def include_file(
    case_id: str,
    filename: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Re-include a file in analysis."""
    excluded = _load_excluded_files(case_id)
    excluded.discard(filename)
    _save_excluded_files(case_id, excluded)
    return {"status": "included", "filename": filename}
