# ---- Documents Router ----------------------------------------------------
# Major document drafting (outlines, sections, citations, quality scoring,
# quick cards export).

import asyncio
import logging
from typing import Dict, List, Optional

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
    court_type: str = ""
    content: str = ""
    created_at: str = ""
    last_updated: str = ""
    quality_score: Optional[int] = None
    quality_grade: Optional[str] = None

    model_config = {"extra": "allow"}


class CreateDraftRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="brief", max_length=50)
    court_type: str = Field(default="state", max_length=50)
    content: str = Field(default="")


class OutlineRequest(BaseModel):
    doc_type: str = Field(..., min_length=1)
    doc_subtype: str = Field(default="")
    court_type: str = Field(default="state")
    custom_instructions: str = Field(default="")
    target_length: str = Field(default="Standard (~15-25 pages)")
    tone: str = Field(default="Formal/Persuasive")


class DraftSectionRequest(BaseModel):
    section_num: str = Field(...)
    section_title: str = Field(...)
    section_description: str = Field(default="")
    outline: list = Field(default=[])
    previous_sections: list = Field(default=[])
    citation_library: list = Field(default=[])
    doc_type: str = Field(default="brief")
    tone: str = Field(default="Formal/Persuasive")
    specific_instructions: str = Field(default="")


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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


# ---- Draft Quality Scoring -----------------------------------------------

@router.get("/drafts/{case_id}/{draft_id}/quality")
def get_draft_quality(
    case_id: str,
    draft_id: str,
    user: dict = Depends(get_current_user),
):
    """Compute quality score for a specific draft."""
    cm = get_case_manager()
    drafts = cm.load_major_drafts(case_id) or []
    draft = next((d for d in drafts if d.get("id") == draft_id), None)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    try:
        from core.draft_quality import compute_draft_quality_score
        score, grade, breakdown = compute_draft_quality_score(draft)
        return {
            "score": score,
            "grade": grade,
            "breakdown": breakdown,
        }
    except Exception as e:
        logger.exception("Draft quality scoring failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Outline Generation --------------------------------------------------

@router.post("/outline/{case_id}/{prep_id}")
async def generate_outline(
    case_id: str,
    prep_id: str,
    body: OutlineRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a document outline using AI."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    try:
        from core.nodes.major_docs import generate_document_outline
        result = await asyncio.to_thread(
            generate_document_outline,
            state,
            body.doc_type,
            body.doc_subtype or body.doc_type,
            body.custom_instructions,
            body.target_length,
            body.tone,
        )
        return result
    except Exception as e:
        logger.exception("Outline generation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Section Drafting ----------------------------------------------------

@router.post("/draft-section/{case_id}/{prep_id}")
async def draft_section(
    case_id: str,
    prep_id: str,
    body: DraftSectionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Draft a single section of a document using AI."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    section = {
        "section_num": body.section_num,
        "title": body.section_title,
        "description": body.section_description,
    }

    try:
        from core.nodes.major_docs import draft_document_section
        result = await asyncio.to_thread(
            draft_document_section,
            state,
            section,
            body.outline,
            body.previous_sections,
            body.citation_library,
            body.doc_type,
            body.tone,
            body.specific_instructions,
        )
        return result
    except Exception as e:
        logger.exception("Section drafting failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---- AI Review -----------------------------------------------------------

@router.post("/review/{case_id}/{prep_id}/{draft_id}")
async def review_draft(
    case_id: str,
    prep_id: str,
    draft_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run AI review on a draft."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    drafts = cm.load_major_drafts(case_id) or []
    draft = next((d for d in drafts if d.get("id") == draft_id), None)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    sections = draft.get("sections", [])
    outline = draft.get("outline", [])
    citations = draft.get("citation_library", [])
    doc_type = draft.get("type", "brief")

    # If draft has no structured sections, create one from content
    if not sections and draft.get("content"):
        sections = [{"section_num": "I", "title": draft.get("title", ""),
                      "content": draft.get("content", "")}]

    try:
        from core.nodes.major_docs import review_brief
        result = await asyncio.to_thread(
            review_brief, state, sections, outline, citations, doc_type
        )
        return result
    except Exception as e:
        logger.exception("Draft review failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Quick Cards Export --------------------------------------------------

@router.get("/quick-cards/{case_id}/{prep_id}")
async def export_quick_cards(
    case_id: str,
    prep_id: str,
    card_type: str = Query(default="witness", regex="^(witness|evidence|objections)$"),
    user: dict = Depends(get_current_user),
):
    """Export courtroom quick reference cards as PDF."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    case_name = cm.get_case_name(case_id)

    try:
        from core.export.quick_cards import generate_quick_cards_pdf
        buf = await asyncio.to_thread(generate_quick_cards_pdf, state, card_type, case_name)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{case_name}_{card_type}_cards.pdf"'},
        )
    except Exception as e:
        logger.exception("Quick cards export failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Quick Cards Data (JSON for frontend rendering) ----------------------

@router.get("/quick-cards-data/{case_id}/{prep_id}")
def get_quick_cards_data(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Get quick cards data as JSON for frontend rendering."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if not state:
        raise HTTPException(status_code=404, detail="Preparation state not found")

    import json

    witnesses = state.get("witnesses", [])
    if isinstance(witnesses, str):
        try:
            witnesses = json.loads(witnesses)
        except Exception:
            witnesses = []

    evidence = state.get("evidence_foundations", [])
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = []

    cross_plan = state.get("cross_examination_plan", [])
    if isinstance(cross_plan, str):
        try:
            cross_plan = json.loads(cross_plan.replace("```json", "").replace("```", ""))
        except Exception:
            cross_plan = []

    # Build cross lookup
    cross_by_name = {}
    if isinstance(cross_plan, list):
        for wb in cross_plan:
            if isinstance(wb, dict):
                wname = wb.get("witness", "").strip().lower()
                cross_by_name[wname] = wb

    # Standard objections library
    objections = [
        {"name": "Hearsay", "rule": "FRE 801/802",
         "basis": "Out-of-court statement offered for truth of the matter asserted.",
         "response": "Not offered for truth; state of mind; business record (803(6)); present sense impression (803(1)); excited utterance (803(2)); prior inconsistent statement (801(d)(1)(A))"},
        {"name": "Relevance", "rule": "FRE 401/402",
         "basis": "Evidence that has no tendency to make a fact of consequence more or less probable.",
         "response": "Goes to [specific fact]. Probative value outweighs any prejudice."},
        {"name": "Prejudicial (403)", "rule": "FRE 403",
         "basis": "Probative value is substantially outweighed by danger of unfair prejudice.",
         "response": "Probative value is high because [reason]. Limiting instruction cures any prejudice."},
        {"name": "Lack of Foundation", "rule": "FRE 901/902",
         "basis": "Insufficient showing of authenticity or competence to testify.",
         "response": "Lay proper foundation through witness testimony, chain of custody, or self-authentication."},
        {"name": "Leading Question", "rule": "FRE 611(c)",
         "basis": "Suggests the answer on direct examination.",
         "response": "Hostile witness / adverse party / foundational question / refreshing recollection."},
        {"name": "Speculation", "rule": "FRE 602/701",
         "basis": "Witness lacks personal knowledge or is guessing.",
         "response": "Witness has personal knowledge from [source]. Opinion is rationally based on perception (701)."},
        {"name": "Best Evidence", "rule": "FRE 1002",
         "basis": "Original writing/recording/photo required to prove content.",
         "response": "Original is unavailable (1004). Duplicate is admissible (1003). Content not in dispute."},
        {"name": "Character Evidence", "rule": "FRE 404(a)/(b)",
         "basis": "Improper use of character to prove conforming conduct.",
         "response": "Not offered for character -- offered to show motive/opportunity/intent/plan/knowledge/identity (404(b))."},
        {"name": "Opinion (Lay)", "rule": "FRE 701",
         "basis": "Lay witness giving improper opinion testimony.",
         "response": "Rationally based on perception, helpful to trier of fact, not based on specialized knowledge."},
        {"name": "Expert Reliability", "rule": "FRE 702/Daubert",
         "basis": "Expert opinion lacks sufficient basis, reliability, or methodology.",
         "response": "Methodology is generally accepted, peer-reviewed, tested, with known error rate. Expert is qualified."},
        {"name": "Cumulative", "rule": "FRE 403/611",
         "basis": "Evidence is unnecessarily repetitive of what has already been established.",
         "response": "This exhibit/testimony adds [specific new element] not yet covered."},
        {"name": "Assumes Facts Not in Evidence", "rule": "FRE 611",
         "basis": "Question embeds an unproven factual premise.",
         "response": "Rephrase without the embedded assumption."},
    ]

    return {
        "witnesses": [
            {
                "name": w.get("name", w.get("witness", "Unknown")),
                "type": w.get("type", w.get("role", "")),
                "alignment": w.get("alignment", ""),
                "summary": w.get("summary", w.get("significance", "")),
                "impeachment_points": w.get("impeachment_points", w.get("weaknesses", [])),
                "cross_questions": cross_by_name.get(
                    w.get("name", w.get("witness", "")).strip().lower(), {}
                ).get("topics", []),
            }
            for w in witnesses if isinstance(w, dict)
        ],
        "evidence": [
            {
                "exhibit": ev.get("exhibit", ev.get("title", ev.get("document", "Unknown"))),
                "type": ev.get("type", ev.get("category", "")),
                "foundation": ev.get("foundation", ev.get("authentication", "")),
                "objections": ev.get("objections", ev.get("potential_objections", [])),
                "value": ev.get("defense_value", ev.get("value", ev.get("significance", ""))),
            }
            for ev in evidence if isinstance(ev, dict)
        ],
        "objections": objections,
    }
