# ---- On-Demand AI Generation Router --------------------------------------
# POST endpoints for one-shot AI generation features: witness prep,
# interview plans, deposition analysis, client reports, statements,
# opponent playbook, case theory, jury instructions, demand letters,
# and exhibit plans.
#
# Each endpoint loads case/prep state, builds a tailored prompt, and
# returns the LLM-generated result synchronously.

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_role
from api.deps import get_case_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases/{case_id}/ondemand", tags=["On-Demand AI"])


# ---- Schemas -------------------------------------------------------------

class WitnessPrepRequest(BaseModel):
    prep_id: str
    witness_index: int = Field(..., ge=0, description="Index into the witnesses list")


class InterviewPlanRequest(BaseModel):
    prep_id: str
    witness_index: int = Field(..., ge=0, description="Index into the witnesses list")


class DepositionAnalysisRequest(BaseModel):
    prep_id: str
    transcript: str = Field(..., min_length=1, max_length=200000)


class PrepIdRequest(BaseModel):
    """Shared request body for endpoints that only need prep_id."""
    prep_id: str


class StatementsRequest(BaseModel):
    prep_id: str
    witness_index: Optional[int] = Field(
        default=None, ge=0, description="Optional witness index; omit for general statement templates"
    )


class ConflictScanRequest(BaseModel):
    prep_id: str
    party_name: str = Field(..., min_length=1, max_length=500, description="Name of the party to check for conflicts")


class OnDemandResponse(BaseModel):
    result: str


# ---- Helpers -------------------------------------------------------------

def _load_case_and_prep(case_id: str, prep_id: str) -> tuple:
    """Load case data and prep state, raising 404 on missing resources.

    Returns (case_manager, case_data, state).
    """
    cm = get_case_manager()
    case_data = cm.get_case(case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")

    state = cm.load_prep_state(case_id, prep_id) or {}
    return cm, case_data, state


def _build_case_context(case_data: dict, state: dict) -> str:
    """Build a context string from case metadata and prep state."""
    parts = [
        f"Case: {case_data.get('name', 'Unknown')}",
        f"Type: {case_data.get('case_type', 'N/A')}",
        f"Category: {case_data.get('case_category', 'N/A')}",
        f"Client: {case_data.get('client_name', 'N/A')}",
        f"Jurisdiction: {case_data.get('jurisdiction', 'N/A')}",
        f"Phase: {case_data.get('phase', 'N/A')}",
    ]

    case_summary = state.get("case_summary", "")
    if case_summary:
        parts.append(f"\nCase Summary:\n{str(case_summary)[:6000]}")

    strategy = state.get("strategy_notes", "")
    if strategy:
        parts.append(f"\nStrategy Notes:\n{str(strategy)[:4000]}")

    witnesses = state.get("witnesses", [])
    if witnesses:
        witness_lines = []
        for w in witnesses[:30]:
            if isinstance(w, dict):
                witness_lines.append(
                    f"- {w.get('name', 'Unknown')} ({w.get('type', 'unknown')}): "
                    f"{w.get('summary', w.get('description', ''))[:200]}"
                )
        if witness_lines:
            parts.append(f"\nWitnesses:\n" + "\n".join(witness_lines))

    elements = state.get("elements_of_offense", "") or state.get("elements", "")
    if elements:
        parts.append(f"\nElements of Offense/Claim:\n{str(elements)[:3000]}")

    timeline = state.get("timeline", [])
    if timeline and isinstance(timeline, list):
        tl_text = "\n".join(
            f"- {e.get('date', '?')}: {e.get('event', e.get('description', ''))}"
            for e in timeline[:20]
            if isinstance(e, dict)
        )
        if tl_text:
            parts.append(f"\nTimeline:\n{tl_text}")

    return "\n".join(parts)


def _get_witness(state: dict, witness_index: int) -> dict:
    """Extract a witness by index from prep state, raising 404 if out of range."""
    witnesses = state.get("witnesses", [])
    if not witnesses or witness_index >= len(witnesses):
        raise HTTPException(
            status_code=404,
            detail=f"Witness index {witness_index} out of range (have {len(witnesses)} witnesses)",
        )
    return witnesses[witness_index]


async def _run_ondemand_prompt(
    case_id: str,
    prep_id: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int = 8192,
) -> str:
    """Run a one-shot LLM prompt with case context.

    Loads case/prep state, builds context, and invokes the LLM.
    """
    _cm, case_data, state = _load_case_and_prep(case_id, prep_id)
    context = _build_case_context(case_data, state)

    from core.llm import get_llm

    llm = get_llm(max_output_tokens=max_output_tokens)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{context}\n\n{user_prompt}"},
    ]

    response = await asyncio.to_thread(llm.invoke, messages)
    return response.content


# ---- Endpoints -----------------------------------------------------------

@router.post("/witness-prep", response_model=OnDemandResponse)
async def generate_witness_prep(
    case_id: str,
    body: WitnessPrepRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate preparation materials for a specific witness."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)
    witness = _get_witness(state, body.witness_index)

    witness_name = witness.get("name", "Unknown")
    witness_type = witness.get("type", "unknown")
    witness_summary = witness.get("summary", witness.get("description", "No details available."))

    system_prompt = (
        "You are an expert trial attorney preparing for witness examination. "
        "Generate comprehensive witness preparation materials including: "
        "key areas to cover, potential pitfalls, suggested question themes, "
        "credibility assessment, and recommended preparation strategy."
    )
    user_prompt = (
        f"Prepare detailed witness preparation materials for:\n"
        f"Witness: {witness_name}\n"
        f"Type: {witness_type}\n"
        f"Summary: {witness_summary}\n\n"
        f"Include:\n"
        f"1. Key areas to explore during preparation sessions\n"
        f"2. Potential weaknesses or credibility issues\n"
        f"3. Suggested question themes for examination\n"
        f"4. Recommended preparation strategy and timeline\n"
        f"5. Areas where this witness's testimony supports or undermines our theory"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/interview-plan", response_model=OnDemandResponse)
async def generate_interview_plan(
    case_id: str,
    body: InterviewPlanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate interview questions for a specific witness."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)
    witness = _get_witness(state, body.witness_index)

    witness_name = witness.get("name", "Unknown")
    witness_type = witness.get("type", "unknown")
    witness_summary = witness.get("summary", witness.get("description", "No details available."))

    system_prompt = (
        "You are an expert legal investigator and trial attorney. "
        "Generate a structured interview plan with specific questions "
        "organized by topic area. Questions should be a mix of open-ended "
        "and targeted follow-ups."
    )
    user_prompt = (
        f"Create a detailed interview plan for:\n"
        f"Witness: {witness_name}\n"
        f"Type: {witness_type}\n"
        f"Summary: {witness_summary}\n\n"
        f"Include:\n"
        f"1. Background and rapport-building questions\n"
        f"2. Core factual questions organized by topic\n"
        f"3. Follow-up and probing questions\n"
        f"4. Questions to test consistency and credibility\n"
        f"5. Closing questions and next steps"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/deposition-analysis", response_model=OnDemandResponse)
async def analyze_deposition(
    case_id: str,
    body: DepositionAnalysisRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Analyze a deposition transcript for key findings and inconsistencies."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)
    context = _build_case_context(case_data, state)

    system_prompt = (
        "You are an expert litigation attorney analyzing a deposition transcript. "
        "Provide a thorough analysis identifying key admissions, inconsistencies, "
        "impeachment opportunities, and strategic implications."
    )
    user_prompt = (
        f"{context}\n\n"
        f"Analyze the following deposition transcript:\n\n"
        f"{body.transcript[:100000]}\n\n"
        f"Provide:\n"
        f"1. Key admissions and favorable testimony\n"
        f"2. Inconsistencies (internal and with other evidence)\n"
        f"3. Impeachment opportunities\n"
        f"4. Areas requiring follow-up or supplemental discovery\n"
        f"5. Strategic implications for trial preparation\n"
        f"6. Recommended designations for trial use"
    )

    from core.llm import get_llm

    llm = get_llm(max_output_tokens=16384)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await asyncio.to_thread(llm.invoke, messages)
    return {"result": response.content}


@router.post("/client-report", response_model=OnDemandResponse)
async def generate_client_report(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a client-friendly case summary report."""
    system_prompt = (
        "You are an attorney writing a clear, professional case status report "
        "for your client. Avoid excessive legal jargon — explain concepts in "
        "plain language while remaining accurate. The report should be "
        "reassuring but honest about risks and next steps."
    )
    user_prompt = (
        "Generate a client-friendly case status report including:\n"
        "1. Current case status and recent developments\n"
        "2. Key strengths of our position\n"
        "3. Risks and challenges (explained plainly)\n"
        "4. Upcoming deadlines and next steps\n"
        "5. Recommended actions for the client\n"
        "6. Estimated timeline and what to expect"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/statements", response_model=OnDemandResponse)
async def generate_statements(
    case_id: str,
    body: StatementsRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate statement templates, optionally focused on a specific witness."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)

    witness_context = ""
    if body.witness_index is not None:
        witness = _get_witness(state, body.witness_index)
        witness_context = (
            f"\nFocus on witness: {witness.get('name', 'Unknown')} "
            f"({witness.get('type', 'unknown')})\n"
            f"Summary: {witness.get('summary', witness.get('description', ''))}\n"
        )

    system_prompt = (
        "You are an expert attorney drafting witness statement templates. "
        "Generate clear, structured statement templates that capture "
        "essential facts while being easy for witnesses to review and sign."
    )
    user_prompt = (
        f"Generate statement templates for this case.{witness_context}\n\n"
        f"Include:\n"
        f"1. Opening identification and oath paragraph\n"
        f"2. Background information sections\n"
        f"3. Factual narrative sections with placeholders\n"
        f"4. Key events and observations\n"
        f"5. Closing attestation paragraph\n"
        f"6. Notes on areas requiring specific detail from the witness"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/opponent-playbook", response_model=OnDemandResponse)
async def generate_opponent_playbook(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Predict and analyze the opponent's likely strategy."""
    system_prompt = (
        "You are an expert trial strategist analyzing the case from the "
        "opposing counsel's perspective. Predict their likely strategy, "
        "arguments, and tactics based on the available case information."
    )
    user_prompt = (
        "Generate an opponent strategy playbook including:\n"
        "1. Likely legal theories and arguments\n"
        "2. Predicted motions and procedural tactics\n"
        "3. Expected witness examination strategy\n"
        "4. Probable evidence presentation approach\n"
        "5. Potential settlement posture and negotiation tactics\n"
        "6. Weaknesses they are likely to exploit in our case\n"
        "7. Recommended counter-strategies for each anticipated move"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/case-theory", response_model=OnDemandResponse)
async def validate_case_theory(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Validate the case theory against available evidence."""
    system_prompt = (
        "You are an expert appellate attorney and legal theorist. "
        "Critically evaluate the case theory against the available evidence, "
        "identifying strengths, gaps, and areas needing reinforcement."
    )
    user_prompt = (
        "Evaluate the current case theory against the evidence:\n"
        "1. Theory coherence — does the narrative hold together logically?\n"
        "2. Evidence mapping — which evidence supports each element?\n"
        "3. Gap analysis — what elements lack sufficient evidentiary support?\n"
        "4. Alternative theories — what competing narratives could the opponent present?\n"
        "5. Jury appeal — how persuasive is this theory to a lay audience?\n"
        "6. Recommendations — specific steps to strengthen the theory"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/jury-instructions", response_model=OnDemandResponse)
async def generate_jury_instructions(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate applicable jury instructions based on the case."""
    system_prompt = (
        "You are an expert trial attorney drafting proposed jury instructions. "
        "Generate clear, legally accurate instructions that favor our client's "
        "position while remaining within the bounds of applicable law."
    )
    user_prompt = (
        "Draft proposed jury instructions including:\n"
        "1. Preliminary instructions (burden of proof, role of jury)\n"
        "2. Substantive instructions for each legal element/claim\n"
        "3. Evidentiary instructions (witness credibility, expert testimony)\n"
        "4. Damages instructions (if applicable)\n"
        "5. Special verdict form questions (if applicable)\n"
        "6. Closing instructions\n"
        "7. Notes on which instructions to object to and grounds for objection"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/demand-letter", response_model=OnDemandResponse)
async def generate_demand_letter(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a settlement demand letter."""
    system_prompt = (
        "You are an experienced litigation attorney drafting a settlement "
        "demand letter. The letter should be professional, persuasive, and "
        "clearly articulate the legal basis for the claim, damages, and "
        "settlement demand."
    )
    user_prompt = (
        "Draft a settlement demand letter including:\n"
        "1. Professional letterhead format\n"
        "2. Statement of representation\n"
        "3. Factual background and liability analysis\n"
        "4. Damages summary with specific categories\n"
        "5. Legal authority supporting the claim\n"
        "6. Settlement demand amount with justification\n"
        "7. Response deadline and consequences of non-response\n"
        "8. Preservation of all rights and remedies"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/exhibit-plan", response_model=OnDemandResponse)
async def generate_exhibit_plan(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate an exhibit organization and presentation plan."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)

    # Include file list if available
    files_context = ""
    try:
        files = _cm.get_case_files(case_id)
        if files:
            file_lines = [f"- {f}" for f in files[:50]]
            files_context = f"\nCase Files:\n" + "\n".join(file_lines)
    except Exception:
        pass

    evidence = state.get("evidence_foundations", [])
    evidence_context = ""
    if evidence and isinstance(evidence, list):
        ev_lines = []
        for e in evidence[:30]:
            if isinstance(e, dict):
                ev_lines.append(
                    f"- {e.get('exhibit', e.get('name', 'Unknown'))}: "
                    f"{e.get('description', e.get('foundation', ''))[:150]}"
                )
        if ev_lines:
            evidence_context = f"\nEvidence Foundations:\n" + "\n".join(ev_lines)

    system_prompt = (
        "You are an expert trial attorney planning exhibit organization "
        "and presentation strategy. Create a detailed exhibit plan that "
        "maximizes impact and ensures proper foundation for each exhibit."
    )
    user_prompt = (
        f"Generate an exhibit organization and presentation plan."
        f"{files_context}{evidence_context}\n\n"
        f"Include:\n"
        f"1. Exhibit numbering and organization scheme\n"
        f"2. Foundation requirements for each exhibit category\n"
        f"3. Order of presentation strategy\n"
        f"4. Witness-exhibit pairing (which witness introduces each exhibit)\n"
        f"5. Pre-trial exhibit exchange and stipulation strategy\n"
        f"6. Technology and presentation logistics\n"
        f"7. Backup plans for excluded or challenged exhibits"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


# ---- Evidence Intelligence Endpoints ------------------------------------

@router.post("/cross-references", response_model=OnDemandResponse)
async def generate_cross_references(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Generate a cross-reference matrix for evidence in the case."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)

    # Gather evidence foundations for richer context
    evidence = state.get("evidence_foundations", [])
    evidence_context = ""
    if evidence and isinstance(evidence, list):
        ev_lines = []
        for e in evidence[:50]:
            if isinstance(e, dict):
                ev_lines.append(
                    f"- {e.get('exhibit', e.get('name', 'Unknown'))}: "
                    f"{e.get('description', e.get('foundation', ''))[:200]}"
                )
        if ev_lines:
            evidence_context = f"\nEvidence Items:\n" + "\n".join(ev_lines)

    system_prompt = (
        "You are an evidence analyst. Generate a cross-reference matrix showing "
        "how each piece of evidence relates to other evidence, witnesses, and legal "
        "elements. Use markdown tables where appropriate."
    )
    user_prompt = (
        f"Generate a comprehensive evidence cross-reference matrix for this case."
        f"{evidence_context}\n\n"
        f"Include:\n"
        f"1. Evidence-to-evidence relationships (corroboration, contradiction)\n"
        f"2. Evidence-to-witness mapping (who introduces or authenticates each item)\n"
        f"3. Evidence-to-legal-element mapping (which elements each item supports)\n"
        f"4. Chain of custody or authentication dependencies\n"
        f"5. Strength ratings for each evidentiary link\n"
        f"6. Gaps where cross-referencing reveals missing connections"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/missing-discovery", response_model=OnDemandResponse)
async def analyze_missing_discovery(
    case_id: str,
    body: PrepIdRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Identify gaps in discovery and potentially missing evidence."""
    _cm, case_data, state = _load_case_and_prep(case_id, body.prep_id)

    # Gather file list for context
    files_context = ""
    try:
        files = _cm.get_case_files(case_id)
        if files:
            file_lines = [f"- {f}" for f in files[:50]]
            files_context = f"\nCase Files on Hand:\n" + "\n".join(file_lines)
    except Exception:
        pass

    evidence = state.get("evidence_foundations", [])
    evidence_context = ""
    if evidence and isinstance(evidence, list):
        ev_lines = []
        for e in evidence[:50]:
            if isinstance(e, dict):
                ev_lines.append(
                    f"- {e.get('exhibit', e.get('name', 'Unknown'))}: "
                    f"{e.get('description', e.get('foundation', ''))[:200]}"
                )
        if ev_lines:
            evidence_context = f"\nKnown Evidence:\n" + "\n".join(ev_lines)

    system_prompt = (
        "You are a discovery analyst. Identify gaps in the evidence, missing "
        "witness statements, potentially undisclosed documents, and discovery "
        "violations. Be thorough and specific."
    )
    user_prompt = (
        f"Analyze the discovery status for this case and identify what is missing."
        f"{files_context}{evidence_context}\n\n"
        f"Include:\n"
        f"1. Missing witness statements or depositions\n"
        f"2. Documents that should exist but are absent (e.g., contracts, records, communications)\n"
        f"3. Potential discovery violations or withholding\n"
        f"4. Gaps between the timeline and available evidence\n"
        f"5. Recommended discovery requests or subpoenas\n"
        f"6. Preservation concerns and spoliation risks"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}


@router.post("/conflict-scan", response_model=OnDemandResponse)
async def scan_conflicts(
    case_id: str,
    body: ConflictScanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Check a party name for potential conflicts of interest."""
    system_prompt = (
        "You are a conflict of interest checker. Check if the given party name "
        "has any conflicts with clients, cases, or staff in this matter. Analyze "
        "potential ethical issues, disqualification risks, and screening requirements."
    )
    user_prompt = (
        f"Perform a conflict of interest scan for the following party:\n"
        f"Party Name: {body.party_name}\n\n"
        f"Analyze:\n"
        f"1. Direct conflicts — does this party appear as a client, witness, or adverse party?\n"
        f"2. Indirect conflicts — business relationships, family ties, prior representations\n"
        f"3. Imputed conflicts — conflicts through affiliated attorneys or staff\n"
        f"4. Temporal conflicts — prior matters involving this party or related entities\n"
        f"5. Ethical rule analysis — applicable rules of professional conduct\n"
        f"6. Recommended screening measures or disclosures\n"
        f"7. Risk assessment — severity and likelihood of conflict materializing"
    )

    result = await _run_ondemand_prompt(
        case_id, body.prep_id, system_prompt, user_prompt, max_output_tokens=8192
    )
    return {"result": result}
