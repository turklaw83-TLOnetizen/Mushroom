# ---- Exhibits Router -----------------------------------------------------
# Bates numbering + exhibit management endpoints.
# Wraps core/bates.py and core/exhibit_manager.py

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/exhibits", tags=["Exhibits"])


# ---- Schemas -------------------------------------------------------------

class BatesAssignRequest(BaseModel):
    file_keys: List[str]
    prefix: str = ""
    start_number: Optional[int] = None


class ExhibitAssignRequest(BaseModel):
    file_keys: List[str]


# ---- Bates Numbering Endpoints -------------------------------------------

@router.post("/bates/assign")
def assign_bates(
    case_id: str,
    body: BatesAssignRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Assign Bates numbers to files."""
    try:
        from core.bates import assign_bates_numbers
        result = assign_bates_numbers(
            case_id,
            file_keys=body.file_keys,
            prefix=body.prefix,
            start_number=body.start_number,
        )
        return {"status": "assigned", "assignments": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bates")
def list_bates(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all Bates number assignments for a case."""
    try:
        from core.bates import get_bates_registry
        return {"items": get_bates_registry(case_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Exhibit Management Endpoints ----------------------------------------

@router.post("/assign")
def assign_exhibits(
    case_id: str,
    body: ExhibitAssignRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Auto-assign exhibit labels (A, B, ..., AA) to files."""
    try:
        from core.exhibit_manager import assign_exhibit_labels
        result = assign_exhibit_labels(case_id, body.file_keys)
        return {"status": "assigned", "exhibits": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_exhibits(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all exhibits for a case."""
    try:
        from core.exhibit_manager import get_exhibit_list
        return {"items": get_exhibit_list(case_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/pdf")
def export_exhibit_list_pdf(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """Export the exhibit list as a PDF."""
    try:
        from core.exhibit_manager import generate_exhibit_pdf
        pdf_bytes = generate_exhibit_pdf(case_id)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=exhibits_{case_id}.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Export Endpoints (PDF/Word) -----------------------------------------

@router.get("/export/case-report")
def export_case_report(
    case_id: str,
    format: str = "pdf",
    user: dict = Depends(get_current_user),
):
    """Export a comprehensive case report."""
    try:
        if format == "pdf":
            from core.export.pdf_export import generate_case_pdf
            data = generate_case_pdf(case_id)
            return StreamingResponse(
                iter([data]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=case_{case_id}.pdf"},
            )
        elif format == "docx":
            from core.export.word_export import generate_case_docx
            data = generate_case_docx(case_id)
            return StreamingResponse(
                iter([data]),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f"attachment; filename=case_{case_id}.docx"},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/court-docs")
def export_court_docs(
    case_id: str,
    doc_type: str = "motion",
    user: dict = Depends(get_current_user),
):
    """Generate court document from template."""
    try:
        from core.export.court_docs import generate_court_doc
        data = generate_court_doc(case_id, doc_type)
        return StreamingResponse(
            iter([data]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={doc_type}_{case_id}.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
