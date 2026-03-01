# ---- Research Router -----------------------------------------------------
# Legal research for a case preparation: retrieve results and run LLM-powered
# research queries with optional jurisdiction scoping.

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from api.deps import get_case_manager, get_config

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/research",
    tags=["Research"],
)


# ---- Schemas -------------------------------------------------------------

class ResearchSource(BaseModel):
    title: str = ""
    url: str = ""

    model_config = {"extra": "allow"}


class ResearchItem(BaseModel):
    topic: str = ""
    summary: str = ""
    sources: List[ResearchSource] = Field(default_factory=list)
    relevance: str = ""

    model_config = {"extra": "allow"}


class CaseLawItem(BaseModel):
    case_name: str = ""
    citation: str = ""
    holding: str = ""
    relevance: str = ""
    year: Optional[int] = None

    model_config = {"extra": "allow"}


class StatuteItem(BaseModel):
    title: str = ""
    section: str = ""
    text: str = ""
    jurisdiction: str = ""

    model_config = {"extra": "allow"}


class ResearchResponse(BaseModel):
    research_items: List[ResearchItem] = Field(default_factory=list)
    case_law: List[CaseLawItem] = Field(default_factory=list)
    statutes: List[StatuteItem] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class RunResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    jurisdiction: str = ""


# ---- Helpers -------------------------------------------------------------

def _parse_llm_json(text: str) -> Optional[dict]:
    """Extract the first JSON object from LLM output using bracket-finding."""
    if not text:
        return None
    # Strip markdown code fences
    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
    if "```" in cleaned:
        cleaned = cleaned.split("```", 1)[0]
    # Try direct parse first
    try:
        return json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: find first { ... } pair
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _shape_research_data(raw: dict) -> dict:
    """Normalize parsed JSON into the expected response shape."""
    return {
        "research_items": raw.get("research_items", []),
        "case_law": raw.get("case_law", []),
        "statutes": raw.get("statutes", []),
    }


# ---- Endpoints -----------------------------------------------------------

@router.get("", response_model=ResearchResponse)
def get_research(
    case_id: str,
    prep_id: str,
    user: dict = Depends(get_current_user),
):
    """Return stored legal research results for a preparation."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Preparation not found")

    research = state.get("legal_research", {})
    return ResearchResponse(
        research_items=research.get("research_items", []),
        case_law=research.get("case_law", []),
        statutes=research.get("statutes", []),
    )


@router.post("/run", response_model=ResearchResponse)
def run_research(
    case_id: str,
    prep_id: str,
    body: RunResearchRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run an LLM-powered legal research query and save results."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Preparation not found")

    # ---- Build LLM prompt ------------------------------------------------
    case_summary = state.get("case_summary", "")
    charges = state.get("charges", [])
    strategy = state.get("strategy_notes", "")

    jurisdiction_clause = ""
    if body.jurisdiction:
        jurisdiction_clause = (
            f"\nJURISDICTION FOCUS: Prioritize laws and case law from {body.jurisdiction}."
        )

    prompt = f"""You are a Legal Research Assistant. Conduct thorough research
on the following query in the context of the case described below.
{jurisdiction_clause}

RESEARCH QUERY:
{body.query}

CASE SUMMARY:
{case_summary[:3000] if case_summary else "(No case summary available.)"}

CHARGES / CLAIMS:
{json.dumps(charges[:20], default=str) if charges else "(None specified.)"}

DEFENSE STRATEGY:
{strategy[:2000] if strategy else "(Not yet developed.)"}

Return your findings as a JSON object with this exact structure:
{{
    "research_items": [
        {{
            "topic": "Short topic title",
            "summary": "Detailed summary of findings on this topic",
            "sources": [{{"title": "Source name", "url": ""}}],
            "relevance": "How this relates to the case"
        }}
    ],
    "case_law": [
        {{
            "case_name": "Full case name",
            "citation": "Standard legal citation",
            "holding": "Key holding of the court",
            "relevance": "Why this case matters here",
            "year": 2020
        }}
    ],
    "statutes": [
        {{
            "title": "Statute title or common name",
            "section": "Section number (e.g., 18 U.S.C. 1001)",
            "text": "Relevant text or summary of the provision",
            "jurisdiction": "Federal / State name"
        }}
    ]
}}

Provide 2-5 research items, 3-8 relevant case law entries, and 2-6 statutes.
Mark any citations that need verification. Return ONLY valid JSON."""

    # ---- Invoke LLM ------------------------------------------------------
    try:
        from core.llm import get_llm, invoke_with_retry
        from langchain_core.messages import HumanMessage

        config = get_config()
        provider = config.get("llm", {}).get("default_provider", "anthropic")
        llm = get_llm(provider, max_output_tokens=8192)
        if llm is None:
            raise HTTPException(
                status_code=503,
                detail="No LLM available. Check that an API key is configured.",
            )

        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        raw_text = response.content if hasattr(response, "content") else str(response)
    except HTTPException:
        raise
    except ImportError as e:
        logger.exception("LLM modules not available")
        raise HTTPException(status_code=500, detail=f"LLM modules not available: {e}")
    except Exception as e:
        logger.exception("LLM research call failed")
        raise HTTPException(status_code=500, detail=f"Research generation failed: {e}")

    # ---- Parse response --------------------------------------------------
    parsed = _parse_llm_json(raw_text)
    if parsed is None:
        # Could not parse JSON; wrap raw text as a single research item
        logger.warning("Could not parse LLM JSON for research -- wrapping raw text")
        research_data = {
            "research_items": [
                {
                    "topic": body.query,
                    "summary": raw_text,
                    "sources": [],
                    "relevance": "Raw LLM output (JSON parse failed)",
                }
            ],
            "case_law": [],
            "statutes": [],
        }
    else:
        research_data = _shape_research_data(parsed)

    # ---- Persist ----------------------------------------------------------
    research_data["_query"] = body.query
    research_data["_jurisdiction"] = body.jurisdiction
    research_data["_generated_at"] = datetime.now(timezone.utc).isoformat()

    cm.save_prep_state(case_id, prep_id, {"legal_research": research_data})

    return ResearchResponse(
        research_items=research_data.get("research_items", []),
        case_law=research_data.get("case_law", []),
        statutes=research_data.get("statutes", []),
    )
