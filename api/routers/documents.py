# ---- Documents Router ----------------------------------------------------
# Major document drafting (outlines, sections, citations, AI generation).

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


class DraftResponse(BaseModel):
    id: str = ""
    case_id: str = ""
    title: str = ""
    type: str = ""
    content: str = ""
    created_at: str = ""
    last_updated: str = ""

    model_config = {"extra": "allow"}


class CreateDraftRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="brief", max_length=50)
    content: str = Field(default="")


@router.get("/drafts/{case_id}", response_model=List[DraftResponse])
def list_drafts(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List major document drafts for a case."""
    cm = get_case_manager()
    try:
        return cm.load_major_drafts(case_id) or []
    except Exception:
        return []


@router.post("/drafts/{case_id}")
def save_draft(
    case_id: str,
    body: CreateDraftRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save a document draft."""
    cm = get_case_manager()
    try:
        draft_id = cm.save_major_draft(case_id, body.model_dump())
        return {"status": "saved", "id": draft_id}
    except Exception as e:
        logger.exception("Failed to save draft")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/drafts/{case_id}/{draft_id}")
def delete_draft(
    case_id: str,
    draft_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Delete a document draft."""
    cm = get_case_manager()
    try:
        cm.delete_major_draft(case_id, draft_id)
        return {"status": "deleted", "id": draft_id}
    except Exception as e:
        logger.exception("Failed to delete draft")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/drafts/{case_id}/{draft_id}")
def update_draft(
    case_id: str,
    draft_id: str,
    body: CreateDraftRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Update a document draft."""
    cm = get_case_manager()
    try:
        cm.delete_major_draft(case_id, draft_id)
        new_id = cm.save_major_draft(case_id, {"id": draft_id, **body.model_dump()})
        return {"status": "updated", "id": new_id}
    except Exception as e:
        logger.exception("Failed to update draft")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---- Research Data -------------------------------------------------------

@router.get("/research/{case_id}/{prep_id}")
def get_research(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get legal research data for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id) or {}
    return state.get("legal_research_data", [])


# ---- Helper: load prep state or 404 ------------------------------------

def _load_doc_state(case_id: str, prep_id: str) -> dict:
    """Load preparation state for document generation, or raise 404."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=404, detail="Preparation not found")
    return state


# ---- AI Generation Request Models --------------------------------------

class GenerateOutlineRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    doc_type: str = Field(..., min_length=1, max_length=100)
    doc_subtype: str = Field(default="", max_length=100)
    custom_instructions: str = Field(default="", max_length=5000)
    target_length: str = Field(default="Standard (~15-25 pages)", max_length=100)
    tone: str = Field(default="Formal/Persuasive", max_length=50)


class DraftSectionRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    section: dict
    outline: list
    previous_sections: list = Field(default_factory=list)
    citation_library: list = Field(default_factory=list)
    doc_type: str = Field(default="brief", max_length=100)
    tone: str = Field(default="Formal/Persuasive", max_length=50)
    specific_instructions: str = Field(default="", max_length=5000)


class BuildCitationsRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    additional_citations: list = Field(default_factory=list)


class ReviewBriefRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    sections: list
    outline: list
    citation_library: list = Field(default_factory=list)
    doc_type: str = Field(default="brief", max_length=100)


class AnalyzeOpposingRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    opposing_text: str = Field(..., min_length=10, max_length=50000)
    citation_library: list = Field(default_factory=list)


class VerifyCitationsRequest(BaseModel):
    prep_id: str = Field(..., min_length=1, max_length=50)
    sections: list
    citation_library: list
    verification_model: str = Field(default="gemini", max_length=50)


class FetchPdfsRequest(BaseModel):
    citation_library: list


class ExportWordRequest(BaseModel):
    draft_id: str = Field(default="", max_length=50)
    jurisdiction: str = Field(default="tennessee_state", max_length=50)
    attorney_info: dict = Field(default_factory=dict)
    case_info: dict = Field(default_factory=dict)


class SaveFullDraftRequest(BaseModel):
    """Save a full draft with outline, sections, citations, and config."""
    title: str = Field(..., min_length=1, max_length=500)
    doc_type: str = Field(default="brief", max_length=100)
    doc_subtype: str = Field(default="", max_length=100)
    outline: list = Field(default_factory=list)
    sections: list = Field(default_factory=list)
    citation_library: list = Field(default_factory=list)
    review_results: dict = Field(default_factory=dict)
    attorney_info: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    content: str = Field(default="")


# ---- Document Type Listing ----------------------------------------------

@router.get("/doc-types")
def get_doc_types(user: dict = Depends(get_current_user)):
    """Get available document types and subtypes."""
    from core.nodes.major_docs import DOC_TYPES
    return DOC_TYPES


@router.get("/jurisdictions")
def get_jurisdictions(user: dict = Depends(get_current_user)):
    """Get available jurisdiction presets for Word export."""
    from core.export.court_docs import get_jurisdiction_list
    return get_jurisdiction_list()


# ---- Full Draft Save (with structured data) -----------------------------

@router.post("/drafts/{case_id}/full")
def save_full_draft(
    case_id: str,
    body: SaveFullDraftRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Save a full structured draft (outline + sections + citations + config)."""
    cm = get_case_manager()
    try:
        draft_data = body.model_dump()
        draft_id = cm.save_major_draft(case_id, draft_data)
        return {"status": "saved", "id": draft_id}
    except Exception:
        logger.exception("Failed to save full draft")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/drafts/{case_id}/{draft_id}/full")
def get_full_draft(
    case_id: str,
    draft_id: str,
    user: dict = Depends(get_current_user),
):
    """Load a full structured draft with all data."""
    cm = get_case_manager()
    draft = cm.load_major_draft(case_id, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


# ---- AI Generation Endpoints -------------------------------------------

@router.post("/{case_id}/outline")
async def generate_outline(
    case_id: str,
    body: GenerateOutlineRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a structured section-by-section outline for a major document."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import generate_document_outline
        result = await asyncio.to_thread(
            generate_document_outline,
            state,
            body.doc_type,
            body.doc_subtype,
            body.custom_instructions,
            body.target_length,
            body.tone,
        )
        return result
    except Exception:
        logger.exception("Outline generation failed")
        raise HTTPException(status_code=500, detail="Outline generation failed")


@router.post("/{case_id}/sections/draft")
async def draft_section(
    case_id: str,
    body: DraftSectionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Draft a single section of a major document with full context."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import draft_document_section
        result = await asyncio.to_thread(
            draft_document_section,
            state,
            body.section,
            body.outline,
            body.previous_sections,
            body.citation_library,
            body.doc_type,
            body.tone,
            body.specific_instructions,
        )
        return result
    except Exception:
        logger.exception("Section drafting failed")
        raise HTTPException(status_code=500, detail="Section drafting failed")


@router.post("/{case_id}/citations/build")
async def build_citations(
    case_id: str,
    body: BuildCitationsRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Build a citation library from case analysis data."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import build_citation_library
        result = await asyncio.to_thread(
            build_citation_library,
            state,
            body.additional_citations or None,
        )
        return result
    except Exception:
        logger.exception("Citation library build failed")
        raise HTTPException(status_code=500, detail="Citation library build failed")


@router.post("/{case_id}/review")
async def review_document(
    case_id: str,
    body: ReviewBriefRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """AI review of the assembled document for quality, consistency, and citations."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import review_brief
        result = await asyncio.to_thread(
            review_brief,
            state,
            body.sections,
            body.outline,
            body.citation_library,
            body.doc_type,
        )
        return result
    except Exception:
        logger.exception("Document review failed")
        raise HTTPException(status_code=500, detail="Document review failed")


@router.post("/{case_id}/opponent-analysis")
async def analyze_opponent(
    case_id: str,
    body: AnalyzeOpposingRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Analyze opposing party's brief and generate counter-arguments."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import analyze_opposing_brief
        result = await asyncio.to_thread(
            analyze_opposing_brief,
            state,
            body.opposing_text,
            body.citation_library or None,
        )
        return result
    except Exception:
        logger.exception("Opponent analysis failed")
        raise HTTPException(status_code=500, detail="Opponent analysis failed")


@router.post("/{case_id}/verify-citations")
async def verify_citations(
    case_id: str,
    body: VerifyCitationsRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Verify citations using a different model than the one that drafted."""
    state = _load_doc_state(case_id, body.prep_id)
    try:
        from core.nodes.major_docs import verify_citations_cross_model
        result = await asyncio.to_thread(
            verify_citations_cross_model,
            state,
            body.sections,
            body.citation_library,
            body.verification_model,
        )
        return result
    except Exception:
        logger.exception("Citation verification failed")
        raise HTTPException(status_code=500, detail="Citation verification failed")


@router.post("/{case_id}/fetch-pdfs")
async def fetch_pdfs(
    case_id: str,
    body: FetchPdfsRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Attempt to fetch PDFs for cited cases from public sources."""
    cm = get_case_manager()
    try:
        from core.nodes.major_docs import fetch_case_pdfs
        result = await asyncio.to_thread(
            fetch_case_pdfs,
            body.citation_library,
            case_id,
            cm,
        )
        return result
    except Exception:
        logger.exception("PDF fetch failed")
        raise HTTPException(status_code=500, detail="PDF fetch failed")


@router.post("/{case_id}/export-word")
async def export_word(
    case_id: str,
    body: ExportWordRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Export a saved draft to a formatted Word document."""
    cm = get_case_manager()

    # Load the draft
    draft = cm.load_major_draft(case_id, body.draft_id) if body.draft_id else None
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    try:
        from core.export.court_docs import generate_major_document_word

        # Build case_info from case metadata
        meta = cm.get_case_metadata(case_id) or {}
        case_info = body.case_info or {}
        if not case_info.get("case_type"):
            case_info["case_type"] = meta.get("case_type", "civil")

        doc_bytes = await asyncio.to_thread(
            generate_major_document_word,
            draft,
            body.jurisdiction,
            body.attorney_info or None,
            case_info or None,
        )

        title = draft.get("title", "document").replace(" ", "_")
        filename = f"{title}.docx"

        return StreamingResponse(
            doc_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Word export failed")
        raise HTTPException(status_code=500, detail="Word export failed")
