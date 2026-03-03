# ---- AI Summary Router ---------------------------------------------------
# One-click AI case summaries for meetings and court prep.
# Uses existing LLM infrastructure.

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/ai", tags=["AI Features"])


class SummaryRequest(BaseModel):
    style: str = "general"  # general | court_prep | client_meeting | deposition
    max_length: int = 2000


@router.post("/summary")
def generate_summary(
    case_id: str,
    body: SummaryRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate an AI case summary using all available case data."""
    try:
        from api.deps import get_case_manager
        from core.llm import get_llm

        cm = get_case_manager()
        case_data = cm.get_case_metadata(case_id)
        if not case_data:
            raise HTTPException(status_code=404, detail="Case not found")

        # Gather context
        context_parts = [
            f"Case: {case_data.get('name', 'Unknown')}",
            f"Type: {case_data.get('case_type', 'N/A')}",
            f"Category: {case_data.get('case_category', 'N/A')}",
            f"Status: {case_data.get('status', 'N/A')}",
            f"Client: {case_data.get('client_name', 'N/A')}",
        ]

        # Add analysis results if available
        analysis = case_data.get("analysis", {})
        if analysis:
            context_parts.append(f"\nAnalysis Results:\n{str(analysis)[:3000]}")

        style_prompts = {
            "general": "Provide a comprehensive case summary suitable for internal review.",
            "court_prep": "Provide a case summary optimized for court preparation, emphasizing key facts, legal issues, and strategic considerations.",
            "client_meeting": "Provide a client-friendly case summary that explains status and next steps in plain language.",
            "deposition": "Provide a summary focused on key facts, witness statements, and areas requiring further investigation for deposition preparation.",
        }

        prompt = f"""You are a legal analyst. Based on the following case information, {style_prompts.get(body.style, style_prompts['general'])}

Case Information:
{chr(10).join(context_parts)}

Keep the summary under {body.max_length} characters. Be specific, cite evidence where available, and highlight any gaps or risks."""

        llm = get_llm()
        response = llm.invoke(prompt)
        summary_text = response.content if hasattr(response, 'content') else str(response)

        return {
            "summary": summary_text,
            "style": body.style,
            "case_id": case_id,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI summary generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deposition-prep")
def deposition_prep(
    case_id: str,
    witness_id: str = "",
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate deposition preparation questions based on case evidence."""
    try:
        from api.deps import get_case_manager
        from core.llm import get_llm

        cm = get_case_manager()
        case_data = cm.get_case_metadata(case_id)
        if not case_data:
            raise HTTPException(status_code=404, detail="Case not found")

        prompt = f"""You are a litigation attorney preparing for a deposition in the case "{case_data.get('name', '')}".

Case type: {case_data.get('case_type', 'N/A')}
Category: {case_data.get('case_category', 'N/A')}

Generate a list of 15-20 strategic deposition questions organized by topic area.
For each question, include a brief note on what you're trying to establish.
Focus on areas where the evidence may be weak or contradictory."""

        llm = get_llm()
        response = llm.invoke(prompt)

        return {
            "questions": response.content if hasattr(response, 'content') else str(response),
            "case_id": case_id,
            "witness_id": witness_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
