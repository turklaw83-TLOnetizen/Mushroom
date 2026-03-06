# ---- Discovery Drafter — AI-Powered Discovery Request Generation -----------
# Civil-only. Generates targeted interrogatories, RFPs, RFAs, and
# meet-and-confer letters using case analysis context.

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from core.llm import get_llm, invoke_with_retry
from core.nodes._common import extract_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

def _build_case_context(case_mgr, data_dir: str, case_id: str) -> Dict[str, Any]:
    """Load the latest prep state and case metadata to build context for drafting.

    Returns a dict with: case_name, case_type, client_name, jurisdiction,
    opposing_counsel, case_summary, witnesses, evidence_foundations,
    legal_elements, investigation_plan, timeline, entities, charges,
    strategy_notes, attorney_directives.
    """
    meta = case_mgr.get_case_metadata(case_id)

    # Find the most recent prep
    preps = case_mgr.list_preparations(case_id)
    state: Dict[str, Any] = {}
    if preps:
        # Sort by created_at descending, pick the latest
        sorted_preps = sorted(
            preps,
            key=lambda p: p.get("created_at", ""),
            reverse=True,
        )
        latest_prep = sorted_preps[0]
        loaded = case_mgr.load_prep_state(case_id, latest_prep["id"])
        if loaded:
            state = loaded

    return {
        "case_name": meta.get("name", ""),
        "case_type": meta.get("case_type", ""),
        "client_name": meta.get("client_name", ""),
        "jurisdiction": meta.get("jurisdiction", ""),
        "opposing_counsel": meta.get("opposing_counsel", ""),
        "court_name": meta.get("court_name", ""),
        "docket_number": meta.get("docket_number", ""),
        "case_summary": state.get("case_summary", ""),
        "witnesses": state.get("witnesses", []),
        "evidence_foundations": state.get("evidence_foundations", []),
        "legal_elements": state.get("legal_elements", []),
        "investigation_plan": state.get("investigation_plan", []),
        "timeline": state.get("timeline", []),
        "entities": state.get("entities", []),
        "charges": state.get("charges", []),
        "strategy_notes": state.get("strategy_notes", ""),
        "devils_advocate_notes": state.get("devils_advocate_notes", ""),
        "attorney_directives": state.get("attorney_directives", []),
        "consistency_check": state.get("consistency_check", []),
    }


def _format_context_block(ctx: Dict) -> str:
    """Format case context into a structured text block for LLM prompts."""
    parts = []

    parts.append(f"CASE: {ctx['case_name']}")
    parts.append(f"CASE TYPE: {ctx['case_type']}")
    parts.append(f"CLIENT: {ctx['client_name']}")
    if ctx.get("jurisdiction"):
        parts.append(f"JURISDICTION: {ctx['jurisdiction']}")
    if ctx.get("opposing_counsel"):
        parts.append(f"OPPOSING COUNSEL: {ctx['opposing_counsel']}")
    if ctx.get("court_name"):
        parts.append(f"COURT: {ctx['court_name']}")

    if ctx.get("case_summary"):
        parts.append(f"\n--- CASE SUMMARY ---\n{ctx['case_summary'][:3000]}")

    if ctx.get("legal_elements"):
        elems = ctx["legal_elements"][:20]
        lines = []
        for e in elems:
            charge = e.get("charge", e.get("element", ""))
            element = e.get("element", "")
            evidence = e.get("evidence", "")
            strength = e.get("strength", "")
            lines.append(f"  - {charge} / {element}: evidence={evidence}, strength={strength}")
        parts.append(f"\n--- LEGAL ELEMENTS ({len(elems)}) ---\n" + "\n".join(lines))

    if ctx.get("witnesses"):
        wits = ctx["witnesses"][:15]
        lines = []
        for w in wits:
            name = w.get("name", "Unknown")
            wtype = w.get("type", "")
            goal = w.get("goal", "")
            lines.append(f"  - {name} ({wtype}): {goal[:100]}")
        parts.append(f"\n--- WITNESSES ({len(wits)}) ---\n" + "\n".join(lines))

    if ctx.get("evidence_foundations"):
        evid = ctx["evidence_foundations"][:15]
        lines = []
        for e in evid:
            item = e.get("item", "")
            admissibility = e.get("admissibility", "")
            attack = e.get("attack", "")
            lines.append(f"  - {item}: admissibility={admissibility}, attack={attack[:80]}")
        parts.append(f"\n--- EVIDENCE ({len(evid)}) ---\n" + "\n".join(lines))

    if ctx.get("investigation_plan"):
        plans = ctx["investigation_plan"][:10]
        lines = []
        for p in plans:
            action = p.get("action", "")
            reason = p.get("reason", "")
            lines.append(f"  - {action}: {reason[:80]}")
        parts.append(f"\n--- INVESTIGATION GAPS ({len(plans)}) ---\n" + "\n".join(lines))

    if ctx.get("timeline"):
        events = ctx["timeline"][:15]
        lines = []
        for t in events:
            dt = f"{t.get('year', '')}-{t.get('month', '')}-{t.get('day', '')}"
            headline = t.get("headline", "")
            lines.append(f"  - {dt}: {headline}")
        parts.append(f"\n--- KEY TIMELINE ({len(events)}) ---\n" + "\n".join(lines))

    if ctx.get("consistency_check"):
        checks = ctx["consistency_check"][:8]
        lines = []
        for c in checks:
            fact = c.get("fact", "")
            notes = c.get("notes", "")
            lines.append(f"  - {fact}: {notes[:80]}")
        parts.append(f"\n--- INCONSISTENCIES ({len(checks)}) ---\n" + "\n".join(lines))

    if ctx.get("strategy_notes"):
        parts.append(f"\n--- STRATEGY NOTES ---\n{ctx['strategy_notes'][:2000]}")

    directives = ctx.get("attorney_directives", [])
    if directives:
        dtexts = [d.get("text", "") for d in directives[:5]]
        parts.append(f"\n--- ATTORNEY DIRECTIVES ---\n" + "\n".join(f"  - {t}" for t in dtexts))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Targeting Parameters
# ---------------------------------------------------------------------------

def _format_targeting(targeting: Dict) -> str:
    """Format targeting parameters into prompt text."""
    parts = []
    if targeting.get("focus_witnesses"):
        parts.append("FOCUS ON THESE WITNESSES: " + ", ".join(targeting["focus_witnesses"]))
    if targeting.get("focus_themes"):
        parts.append("FOCUS ON THESE THEMES: " + ", ".join(targeting["focus_themes"]))
    if targeting.get("focus_evidence_gaps"):
        parts.append("TARGET THESE EVIDENCE GAPS: " + ", ".join(targeting["focus_evidence_gaps"]))
    if targeting.get("date_range"):
        parts.append(f"DATE RANGE OF INTEREST: {targeting['date_range']}")
    return "\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Draft Interrogatories
# ---------------------------------------------------------------------------

def draft_interrogatories(
    case_mgr,
    data_dir: str,
    case_id: str,
    *,
    targeting: Optional[Dict] = None,
    custom_instructions: str = "",
    num_items: int = 25,
) -> List[Dict]:
    """Generate targeted interrogatories using case analysis context.

    Returns a list of dicts: [{"number": int, "text": str, "targeting_rationale": str}]
    """
    ctx = _build_case_context(case_mgr, data_dir, case_id)
    context_block = _format_context_block(ctx)
    targeting_block = _format_targeting(targeting or {})

    role = "plaintiff" if ctx["case_type"] == "civil-plaintiff" else "defendant"
    opponent = "defendant" if role == "plaintiff" else "plaintiff"

    prompt = f"""You are a litigation attorney drafting interrogatories for the {role} in a civil case.

{context_block}

{targeting_block}

{f"ADDITIONAL INSTRUCTIONS FROM ATTORNEY: {custom_instructions}" if custom_instructions else ""}

Draft exactly {num_items} interrogatories to serve on the {opponent}. Each interrogatory must:
1. Be specific and targeted based on the case facts above
2. Not be compound (one question per interrogatory)
3. Be designed to uncover facts that strengthen our case or expose weaknesses in the opposing side
4. Include standard definitions and instructions preamble requests where appropriate
5. Target specific witnesses, events, or evidence gaps identified in the case analysis
6. Be properly numbered starting from 1

For each interrogatory, explain WHY you are asking it (what case fact or gap it targets).

Return a JSON array of objects with these exact keys:
- "number" (integer starting from 1)
- "text" (the full interrogatory text)
- "targeting_rationale" (1-2 sentence explanation of what this targets)

Return ONLY the JSON array, no other text."""

    return _invoke_drafter(prompt, num_items)


# ---------------------------------------------------------------------------
# Draft Requests for Production
# ---------------------------------------------------------------------------

def draft_requests_for_production(
    case_mgr,
    data_dir: str,
    case_id: str,
    *,
    targeting: Optional[Dict] = None,
    custom_instructions: str = "",
    num_items: int = 20,
) -> List[Dict]:
    """Generate targeted requests for production using case analysis context.

    Returns a list of dicts: [{"number": int, "text": str, "targeting_rationale": str}]
    """
    ctx = _build_case_context(case_mgr, data_dir, case_id)
    context_block = _format_context_block(ctx)
    targeting_block = _format_targeting(targeting or {})

    role = "plaintiff" if ctx["case_type"] == "civil-plaintiff" else "defendant"
    opponent = "defendant" if role == "plaintiff" else "plaintiff"

    prompt = f"""You are a litigation attorney drafting requests for production of documents for the {role} in a civil case.

{context_block}

{targeting_block}

{f"ADDITIONAL INSTRUCTIONS FROM ATTORNEY: {custom_instructions}" if custom_instructions else ""}

Draft exactly {num_items} requests for production to serve on the {opponent}. Each request must:
1. Be specific about the categories of documents requested
2. Include reasonable time frames based on case facts
3. Reference specific events, communications, or transactions from the case
4. Target documents that would support our theory or undermine the opposing party
5. Use proper legal language ("any and all documents, including but not limited to...")
6. Include ESI (electronically stored information) where relevant
7. Be properly numbered starting from 1

For each request, explain WHY you are requesting these documents.

Return a JSON array of objects with these exact keys:
- "number" (integer starting from 1)
- "text" (the full request for production text)
- "targeting_rationale" (1-2 sentence explanation of what this targets)

Return ONLY the JSON array, no other text."""

    return _invoke_drafter(prompt, num_items)


# ---------------------------------------------------------------------------
# Draft Requests for Admission
# ---------------------------------------------------------------------------

def draft_requests_for_admission(
    case_mgr,
    data_dir: str,
    case_id: str,
    *,
    targeting: Optional[Dict] = None,
    custom_instructions: str = "",
    num_items: int = 20,
) -> List[Dict]:
    """Generate targeted requests for admission using case analysis context.

    Returns a list of dicts: [{"number": int, "text": str, "targeting_rationale": str}]
    """
    ctx = _build_case_context(case_mgr, data_dir, case_id)
    context_block = _format_context_block(ctx)
    targeting_block = _format_targeting(targeting or {})

    role = "plaintiff" if ctx["case_type"] == "civil-plaintiff" else "defendant"
    opponent = "defendant" if role == "plaintiff" else "plaintiff"

    prompt = f"""You are a litigation attorney drafting requests for admission for the {role} in a civil case.

{context_block}

{targeting_block}

{f"ADDITIONAL INSTRUCTIONS FROM ATTORNEY: {custom_instructions}" if custom_instructions else ""}

Draft exactly {num_items} requests for admission to serve on the {opponent}. Each request must:
1. Be specific, fact-bound statements that the opposing party must admit or deny
2. Target facts that narrow triable issues if admitted
3. Include requests about authenticity of key documents
4. Address specific events, communications, and relationships in the case
5. Be strategically ordered — start with easily admitted facts, build to contested ones
6. Be properly numbered starting from 1

Effective RFAs:
- Focus on undisputed facts to take them off the table at trial
- Target the genuineness of documents likely to be exhibits
- Address specific dates, amounts, and identities
- Pin down the opposing party's position on key issues

For each request, explain the strategic purpose.

Return a JSON array of objects with these exact keys:
- "number" (integer starting from 1)
- "text" (the full request for admission text)
- "targeting_rationale" (1-2 sentence explanation of what this targets)

Return ONLY the JSON array, no other text."""

    return _invoke_drafter(prompt, num_items)


# ---------------------------------------------------------------------------
# Meet-and-Confer Letter
# ---------------------------------------------------------------------------

def generate_meet_confer_letter(
    case_mgr,
    data_dir: str,
    case_id: str,
    *,
    request_data: Dict,
    deficient_item_numbers: List[int],
    custom_instructions: str = "",
) -> str:
    """Generate a professional meet-and-confer letter for deficient discovery responses.

    Args:
        request_data: The discovery request dict (with items and responses)
        deficient_item_numbers: Which item numbers have deficient responses
        custom_instructions: Additional attorney guidance

    Returns:
        Formatted letter text (markdown)
    """
    ctx = _build_case_context(case_mgr, data_dir, case_id)

    # Build deficient items summary
    deficient_items = []
    for item in request_data.get("items", []):
        if item.get("number") in deficient_item_numbers:
            deficient_items.append({
                "number": item["number"],
                "text": item.get("text", ""),
                "response": item.get("response", ""),
                "objection": item.get("objection", ""),
            })

    if not deficient_items:
        return "No deficient items specified."

    items_block = ""
    for di in deficient_items:
        items_block += f"\nItem #{di['number']}:\n"
        items_block += f"  Request: {di['text']}\n"
        items_block += f"  Response: {di['response'] or '(no response)'}\n"
        items_block += f"  Objection: {di['objection'] or '(none)'}\n"

    role = "plaintiff" if ctx["case_type"] == "civil-plaintiff" else "defendant"
    request_type_display = request_data.get("request_type", "discovery requests").replace("_", " ").title()

    prompt = f"""You are a litigation attorney drafting a professional meet-and-confer letter regarding deficient discovery responses.

CASE: {ctx['case_name']}
OUR CLIENT: {ctx['client_name']} ({role})
OPPOSING COUNSEL: {ctx.get('opposing_counsel', 'Opposing Counsel')}
COURT: {ctx.get('court_name', '')}
DOCKET: {ctx.get('docket_number', '')}

DISCOVERY REQUEST TYPE: {request_type_display}
REQUEST TITLE: {request_data.get('title', '')}
DATE SERVED: {request_data.get('date_served', '')}

DEFICIENT ITEMS:
{items_block}

{f"ADDITIONAL INSTRUCTIONS: {custom_instructions}" if custom_instructions else ""}

Draft a professional meet-and-confer letter that:
1. References the specific discovery requests and response date
2. For each deficient item, explains WHY the response is inadequate
3. Cites relevant discovery rules (Federal Rules of Civil Procedure or state equivalent)
4. Requests supplemental responses within a reasonable deadline (14 days)
5. Notes that a motion to compel will be filed if the deficiencies are not cured
6. Maintains a professional, firm but courteous tone
7. Includes a proper letter header format

Return the complete letter in markdown format."""

    try:
        llm = get_llm("anthropic", max_output_tokens=4096)
        if not llm:
            llm = get_llm("xai", max_output_tokens=4096)
        if not llm:
            return "Error: No LLM provider available. Check API keys."

        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()
    except Exception:
        logger.exception("Failed to generate meet-and-confer letter")
        return "Error generating letter. Please try again."


# ---------------------------------------------------------------------------
# Shared LLM Invocation
# ---------------------------------------------------------------------------

def _invoke_drafter(prompt: str, expected_count: int) -> List[Dict]:
    """Invoke LLM for drafting, parse JSON response, return items."""
    try:
        llm = get_llm("anthropic", max_output_tokens=8192)
        if not llm:
            llm = get_llm("xai", max_output_tokens=8192)
        if not llm:
            logger.error("No LLM provider available for discovery drafting")
            return []

        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)

        items = extract_json(content, expect_list=True)
        if not items or not isinstance(items, list):
            logger.warning("Failed to parse discovery draft response as JSON list")
            return []

        # Normalize items
        normalized = []
        for i, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            normalized.append({
                "number": item.get("number", i),
                "text": str(item.get("text", "")),
                "targeting_rationale": str(item.get("targeting_rationale", "")),
            })

        return normalized

    except Exception:
        logger.exception("Discovery drafting failed")
        return []
