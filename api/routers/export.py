# ---- Export Router -------------------------------------------------------
# Download reports, briefs, and trial binders.
#
# All export endpoints use async def + asyncio.to_thread because
# document generation (PDF, Word) is CPU-bound and slow.

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.auth import get_current_user
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/export", tags=["Export"])


@router.get("/pdf/{prep_id}")
async def export_pdf_report(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Generate and download a PDF analysis report."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    case_name = cm.get_case_name(case_id)

    try:
        from core.export.pdf_export import generate_pdf_report
        buf = await asyncio.to_thread(generate_pdf_report, state, case_name)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{case_name}_report.pdf"'},
        )
    except Exception as e:
        logger.exception("PDF export failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/word/{prep_id}")
async def export_word_report(
    case_id: str,
    prep_id: str,
    module_filter: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Generate and download a Word analysis report."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    case_name = cm.get_case_name(case_id)

    try:
        from core.export.word_export import generate_word_report
        buf = await asyncio.to_thread(generate_word_report, state, case_name, module_filter)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{case_name}_report.docx"'},
        )
    except Exception as e:
        logger.exception("Word export failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/brief/{prep_id}")
async def export_irac_brief(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Generate and download an IRAC brief."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    case_name = cm.get_case_name(case_id)

    try:
        from core.export.word_export import generate_brief_outline
        buf = await asyncio.to_thread(generate_brief_outline, state, case_name)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{case_name}_brief.docx"'},
        )
    except Exception as e:
        logger.exception("Brief export failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trial-binder/{prep_id}")
async def export_trial_binder(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Generate and download a 13-tab trial binder PDF."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    case_name = cm.get_case_name(case_id)
    prep = cm.get_preparation(case_id, prep_id) or {}
    prep_type = prep.get("type", "trial")
    prep_name = prep.get("name", "")

    try:
        from core.export.pdf_export import generate_trial_binder_pdf
        buf = await asyncio.to_thread(
            generate_trial_binder_pdf, state, case_name, prep_type, prep_name
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{case_name}_trial_binder.pdf"'},
        )
    except Exception as e:
        logger.exception("Trial binder export failed")
        raise HTTPException(status_code=500, detail="Internal server error")
