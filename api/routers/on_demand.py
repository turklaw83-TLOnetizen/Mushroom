# ---- On-Demand AI Generation Router --------------------------------------
# Endpoints for generating specific analysis artifacts on request.
# Each calls a core/nodes function via asyncio.to_thread().

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/preparations/{prep_id}/generate",
    tags=["On-Demand Generation"],
)


# ---- Request Models ------------------------------------------------------

class WitnessPrepRequest(BaseModel):
    witness_name: str = Field(..., min_length=1, max_length=200)
    witness_role: str = ""
    witness_goal: str = ""


class InterviewPlanRequest(BaseModel):
    witness_name: str = Field(..., min_length=1, max_length=200)
    witness_role: str = ""
    interview_type: str = "initial"  # initial | follow_up | pre_testimony


class DepositionOutlineRequest(BaseModel):
    witness_name: str = Field(..., min_length=1, max_length=200)
    witness_role: str = ""
    topics: str = ""


class StatementRequest(BaseModel):
    statement_type: str = "opening"  # opening | closing
    tone: str = "measured"  # aggressive | measured | empathetic
    audience: str = "jury"  # jury | bench


class ClientReportRequest(BaseModel):
    pass  # No params needed — uses full state


class CheatSheetRequest(BaseModel):
    pass  # No params needed — uses full state


class OpponentPlaybookRequest(BaseModel):
    pass  # No params needed — uses full state


class LexisQueryRequest(BaseModel):
    research_focus: str = ""


class LexisAnalysisRequest(BaseModel):
    pasted_text: str = Field(..., min_length=10, max_length=100000)
    query_context: str = ""


# ---- Helper: load state or 404 ------------------------------------------

def _load_state_or_404(case_id: str, prep_id: str) -> dict:
    from api.deps import get_case_manager
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=404, detail="Preparation not found")
    return state


def _save_result(case_id: str, prep_id: str, updates: dict):
    from api.deps import get_case_manager
    cm = get_case_manager()
    cm.save_prep_state(case_id, prep_id, updates)


# ---- Witness Prep --------------------------------------------------------

@router.post("/witness-prep")
async def gen_witness_prep(
    case_id: str,
    prep_id: str,
    body: WitnessPrepRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate witness preparation (mock cross-examination scenarios)."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.examination import generate_witness_prep
        result = await asyncio.to_thread(
            generate_witness_prep, state, body.witness_name, body.witness_role, body.witness_goal,
        )

        # Save to state under witness_prep key
        existing = state.get("witness_prep", {})
        if isinstance(existing, dict):
            existing[body.witness_name] = result.get("witness_prep", result)
        else:
            existing = {body.witness_name: result.get("witness_prep", result)}
        _save_result(case_id, prep_id, {"witness_prep": existing})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Witness prep generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Interview Plan ------------------------------------------------------

@router.post("/interview-plan")
async def gen_interview_plan(
    case_id: str,
    prep_id: str,
    body: InterviewPlanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a structured interview preparation plan."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.examination import generate_interview_plan
        result = await asyncio.to_thread(
            generate_interview_plan, state, body.witness_name, body.witness_role, body.interview_type,
        )

        existing = state.get("interview_plans", {})
        if isinstance(existing, dict):
            existing[body.witness_name] = result.get("interview_plan", result)
        else:
            existing = {body.witness_name: result.get("interview_plan", result)}
        _save_result(case_id, prep_id, {"interview_plans": existing})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Interview plan generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Deposition Outline --------------------------------------------------

@router.post("/deposition-outline")
async def gen_deposition_outline(
    case_id: str,
    prep_id: str,
    body: DepositionOutlineRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a structured deposition outline."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.examination import generate_deposition_outline
        result = await asyncio.to_thread(
            generate_deposition_outline, state, body.witness_name, body.witness_role, body.topics,
        )

        existing = state.get("deposition_outlines", {})
        if isinstance(existing, dict):
            existing[body.witness_name] = result.get("deposition_outline", result)
        else:
            existing = {body.witness_name: result.get("deposition_outline", result)}
        _save_result(case_id, prep_id, {"deposition_outlines": existing})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Deposition outline generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Client Report -------------------------------------------------------

@router.post("/client-report")
async def gen_client_report(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a plain-language client report."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.research import generate_client_report
        result = await asyncio.to_thread(generate_client_report, state)

        content = result.get("client_report", result)
        _save_result(case_id, prep_id, {"client_report": content})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Client report generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Cheat Sheet ---------------------------------------------------------

@router.post("/cheat-sheet")
async def gen_cheat_sheet(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a courtroom cheat sheet from existing analysis."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.research import generate_cheat_sheet
        result = await asyncio.to_thread(generate_cheat_sheet, state)

        content = result.get("cheat_sheet", result)
        _save_result(case_id, prep_id, {"cheat_sheet": content})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cheat sheet generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Lexis+ Query Generation ---------------------------------------------

@router.post("/lexis-queries")
async def gen_lexis_queries(
    case_id: str,
    prep_id: str,
    body: LexisQueryRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate optimized Lexis+/Westlaw Boolean search queries."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.research import generate_lexis_queries
        result = await asyncio.to_thread(
            generate_lexis_queries, state, body.research_focus,
        )

        queries = result.get("lexis_queries", [])
        _save_result(case_id, prep_id, {"lexis_queries": queries})

        return {"status": "success", "result": {"lexis_queries": queries}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Lexis query generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Lexis+ Results Analysis ---------------------------------------------

@router.post("/lexis-analysis")
async def gen_lexis_analysis(
    case_id: str,
    prep_id: str,
    body: LexisAnalysisRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Analyze pasted legal research results from Lexis+/Westlaw."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.research import analyze_lexis_results
        result = await asyncio.to_thread(
            analyze_lexis_results, state, body.pasted_text, body.query_context,
        )

        analysis = result.get("lexis_analysis", {})
        _save_result(case_id, prep_id, {"lexis_analysis": analysis})

        return {"status": "success", "result": {"lexis_analysis": analysis}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Lexis analysis failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Statements (Opening / Closing) --------------------------------------

@router.post("/statements")
async def gen_statements(
    case_id: str,
    prep_id: str,
    body: StatementRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a draft opening or closing statement."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.research import generate_statements
        result = await asyncio.to_thread(
            generate_statements, state, body.statement_type, body.tone, body.audience,
        )

        key = f"{body.statement_type}_statement"
        content = result.get("statement", result)
        _save_result(case_id, prep_id, {key: content})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Statement generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Opponent Playbook ---------------------------------------------------

@router.post("/opponent-playbook")
async def gen_opponent_playbook(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a prediction of opposing counsel's strategy."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        # Use the devil's advocate / strategy analysis to build playbook
        from core.llm import get_llm, invoke_with_retry
        from api.deps import get_config
        from langchain_core.messages import HumanMessage, SystemMessage

        config = get_config()
        provider = config.get("llm", {}).get("provider", "anthropic")
        llm = get_llm(provider, max_output_tokens=8192)

        context_parts = []
        if state.get("case_summary"):
            context_parts.append(f"Case Summary:\n{str(state['case_summary'])[:3000]}")
        if state.get("devils_advocate_notes"):
            context_parts.append(f"Devil's Advocate Analysis:\n{str(state['devils_advocate_notes'])[:3000]}")
        if state.get("consistency_check"):
            context_parts.append(f"Evidence Inconsistencies:\n{str(state['consistency_check'])[:2000]}")
        if state.get("witnesses"):
            context_parts.append(f"Witnesses:\n{str(state['witnesses'])[:2000]}")

        prompt = [
            SystemMessage(content="""You are a senior trial strategist analyzing the opposing counsel's likely approach.
Based on the case information, predict their strategy including:
1. Their likely theory of the case
2. Key witnesses they'll prioritize and how they'll use them
3. Evidence they'll emphasize and how they'll frame it
4. Anticipated motions and procedural tactics
5. Cross-examination approaches for your witnesses
6. Weaknesses in their case they'll try to hide
7. Recommended counter-strategies for each element

Be specific to the facts of this case. Use markdown formatting."""),
            HumanMessage(content="\n\n".join(context_parts) or "No case data available."),
        ]

        result = await asyncio.to_thread(invoke_with_retry, llm, prompt)
        content = result.content if hasattr(result, "content") else str(result)

        _save_result(case_id, prep_id, {"opponent_playbook": content})

        return {"status": "success", "result": {"opponent_playbook": content}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Opponent playbook generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Deposition Analysis -------------------------------------------------

class DepositionAnalysisRequest(BaseModel):
    deposition_text: str = Field(..., min_length=10)


@router.post("/deposition-analysis")
async def gen_deposition_analysis(
    case_id: str,
    prep_id: str,
    body: DepositionAnalysisRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Analyze a deposition transcript for key findings and inconsistencies."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.examination import analyze_deposition
        result = await asyncio.to_thread(analyze_deposition, state, body.deposition_text)

        _save_result(case_id, prep_id, {"deposition_analysis": result.get("deposition_analysis", result)})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Deposition analysis generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Medical Chronology (Civil) -----------------------------------------

@router.post("/medical-chronology")
async def gen_medical_chronology(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a medical chronology for civil cases."""
    try:
        state = _load_state_or_404(case_id, prep_id)
        from core.nodes.civil import generate_medical_chronology
        result = await asyncio.to_thread(generate_medical_chronology, state)
        content = result.get("medical_chronology", result)
        _save_result(case_id, prep_id, {"medical_chronology": content})
        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Medical chronology generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Demand Letter (Civil) ----------------------------------------------

@router.post("/demand-letter")
async def gen_demand_letter(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a demand letter for civil litigation."""
    try:
        state = _load_state_or_404(case_id, prep_id)
        from core.nodes.civil import generate_demand_letter
        result = await asyncio.to_thread(generate_demand_letter, state)
        content = result.get("demand_letter", result)
        _save_result(case_id, prep_id, {"demand_letter": content})
        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Demand letter generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Voir Dire Generation ------------------------------------------------

@router.post("/voir-dire")
async def gen_voir_dire(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate voir dire questions and jury selection strategy."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.analysis import generate_voir_dire
        result = await asyncio.to_thread(generate_voir_dire, state)

        _save_result(case_id, prep_id, {"voir_dire": result.get("voir_dire", result)})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Voir dire generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ---- Mock Jury Simulation ------------------------------------------------

@router.post("/mock-jury")
async def gen_mock_jury(
    case_id: str,
    prep_id: str,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Run a mock jury simulation based on current case analysis."""
    try:
        state = _load_state_or_404(case_id, prep_id)

        from core.nodes.analysis import generate_mock_jury
        result = await asyncio.to_thread(generate_mock_jury, state)

        _save_result(case_id, prep_id, {"mock_jury_feedback": result.get("mock_jury_feedback", result)})

        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Mock jury simulation failed")
        raise HTTPException(status_code=500, detail="Generation failed")
