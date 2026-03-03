# ---- Annotations Router --------------------------------------------------
# CRUD for document annotations (highlights, notes) on specific pages.
# Wraps core/annotations.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/annotations", tags=["Annotations"])


# ---- Schemas -------------------------------------------------------------

class AnnotationCreate(BaseModel):
    file_key: str
    page: int
    text: str = ""
    excerpt: str = ""
    color: str = "yellow"
    annotation_type: str = "highlight"  # highlight | note | bookmark
    position: Optional[dict] = None  # {x, y, width, height} for positioned notes


class AnnotationUpdate(BaseModel):
    text: Optional[str] = None
    color: Optional[str] = None
    annotation_type: Optional[str] = None


# ---- Endpoints -----------------------------------------------------------

@router.get("")
def list_annotations(
    case_id: str,
    file_key: str = "",
    page: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    """List annotations for a case, optionally filtered by file and page."""
    try:
        from core.annotations import list_annotations as _list
        items = _list(case_id, file_key=file_key, page=page)
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception("Failed to list annotations")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
def create_annotation(
    case_id: str,
    body: AnnotationCreate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Create a new annotation on a document page."""
    try:
        from core.annotations import add_annotation
        ann_id = add_annotation(
            case_id,
            file_key=body.file_key,
            page=body.page,
            text=body.text,
            excerpt=body.excerpt,
            color=body.color,
            annotation_type=body.annotation_type,
        )
        return {"id": ann_id, "status": "created"}
    except Exception as e:
        logger.exception("Failed to create annotation")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{annotation_id}")
def update_annotation(
    case_id: str,
    annotation_id: str,
    body: AnnotationUpdate,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update an annotation's text or color."""
    try:
        from core.annotations import update_annotation as _update
        updates = body.model_dump(exclude_none=True)
        if not _update(case_id, annotation_id, updates):
            raise HTTPException(status_code=404, detail="Annotation not found")
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update annotation")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{annotation_id}")
def delete_annotation(
    case_id: str,
    annotation_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete an annotation."""
    try:
        from core.annotations import delete_annotation as _delete
        if not _delete(case_id, annotation_id):
            raise HTTPException(status_code=404, detail="Annotation not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete annotation")
        raise HTTPException(status_code=500, detail="Internal server error")
