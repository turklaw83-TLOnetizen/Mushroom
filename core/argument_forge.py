# ---- Argument Forge: AI-Powered Legal Argument Construction Engine ----------
# Identifies legal issues, generates multi-framework arguments, steelmans
# opposition, builds counter-matrices, prepares oral arguments, scores
# win-probability, and exports to brief skeleton.
# Storage: data/cases/{case_id}/argument_sessions.json

import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.nodes._common import *

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Roman numeral helper
# ---------------------------------------------------------------------------

_ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


# ---------------------------------------------------------------------------
# Session persistence helpers
# ---------------------------------------------------------------------------

def _sessions_path(data_dir: str, case_id: str) -> Path:
    return Path(data_dir) / "cases" / case_id / "argument_sessions.json"


def save_argument_session(data_dir: str, case_id: str, session: dict) -> str:
    """Save an argument session to disk.

    If the session already has an 'id' field, it is updated in place.
    Otherwise a new ID is generated and the session is appended.

    Returns:
        The session ID (existing or newly generated).
    """
    path = _sessions_path(data_dir, case_id)
    os.makedirs(path.parent, exist_ok=True)

    sessions = _load_raw_sessions(path)

    session_id = session.get("id") or secrets.token_hex(6)
    session["id"] = session_id
    session["updated_at"] = datetime.utcnow().isoformat()

    # Update in place if existing
    replaced = False
    for i, s in enumerate(sessions):
        if s.get("id") == session_id:
            sessions[i] = session
            replaced = True
            break
    if not replaced:
        session.setdefault("created_at", session["updated_at"])
        sessions.append(session)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, default=str)

    return session_id


def load_argument_sessions(data_dir: str, case_id: str) -> list:
    """Load all argument sessions for a case, newest first."""
    path = _sessions_path(data_dir, case_id)
    sessions = _load_raw_sessions(path)
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def delete_argument_session(data_dir: str, case_id: str, session_id: str) -> bool:
    """Delete an argument session by ID. Returns True if found and deleted."""
    path = _sessions_path(data_dir, case_id)
    sessions = _load_raw_sessions(path)
    before = len(sessions)
    sessions = [s for s in sessions if s.get("id") != session_id]
    if len(sessions) < before:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, default=str)
        return True
    return False


def _load_raw_sessions(path: Path) -> list:
    """Load raw sessions list from disk."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        logger.exception("Failed to load argument_sessions.json from %s", path)
        return []


# ---------------------------------------------------------------------------
# 1. Identify Issues
# ---------------------------------------------------------------------------

def identify_issues(state: AgentState, custom_focus: str = "") -> dict:
    """Analyze a case and identify the key legal issues that need to be argued.

    Gathers case summary, legal elements, charges, evidence foundations,
    strategy notes, and witnesses to produce a prioritized list of issues
    with suggested legal frameworks for each.

    Args:
        state: LangGraph agent state with case data.
        custom_focus: Optional user-supplied focus area to narrow the analysis.

    Returns:
        {"issues": [{"id", "title", "description", "frameworks", "priority"}]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")
    legal_elements = state.get("legal_elements", [])
    charges = state.get("charges", [])
    evidence = state.get("evidence_foundations", [])
    strategy = state.get("strategy_notes", "")
    witnesses = state.get("witnesses", [])

    elements_text = ""
    if legal_elements:
        elements_text = "\n".join(
            f"- {e.get('charge', '')}: {e.get('element', '')} (strength: {e.get('strength', '')})"
            for e in legal_elements[:20] if isinstance(e, dict)
        )

    charges_text = json.dumps(charges[:10], indent=2) if charges else "[None specified]"

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    witness_text = ""
    if witnesses:
        witness_text = "\n".join(
            f"- {w.get('name', '')}: {w.get('type', '')} — {w.get('summary', '')[:120]}"
            for w in witnesses[:15] if isinstance(w, dict)
        )

    focus_block = f"\nFOCUS AREA:\n{custom_focus}\n" if custom_focus else ""

    prompt = f"""You are a senior litigation strategist. Analyze this case and identify the key legal issues that need to be argued. For each issue, suggest which legal frameworks could apply.

{ctx.get('directives_block', '')}

ROLE: {ctx.get('role', 'Attorney')}
CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}

CASE SUMMARY:
{case_summary[:3000] if case_summary else '[No case summary available]'}

CHARGES/CLAIMS:
{charges_text}

LEGAL ELEMENTS:
{elements_text or '[No elements mapped]'}

EVIDENCE:
{evidence_text or '[No evidence data]'}

STRATEGY NOTES:
{strategy[:2000] if strategy else '[No strategy notes]'}

WITNESSES:
{witness_text or '[No witness data]'}
{focus_block}
TASK:
Identify the key legal issues in this case. For each issue provide:
- id: a short identifier (e.g., "issue_1", "issue_2")
- title: concise issue heading
- description: 2-4 sentences explaining the issue and its significance
- frameworks: list of applicable legal frameworks from ["constitutional", "statutory", "common_law", "regulatory", "procedural", "policy", "equity"]
- priority: "high", "medium", or "low"

Return JSON ONLY:
{{
    "issues": [
        {{"id": "issue_1", "title": "...", "description": "...", "frameworks": ["constitutional", "statutory"], "priority": "high"}},
        ...
    ]
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "issues" in result:
            return result

        return {
            "issues": [{"id": "issue_1", "title": "Parse Error", "description": response.content[:500],
                         "frameworks": [], "priority": "medium"}],
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("identify_issues failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 2. Generate Arguments
# ---------------------------------------------------------------------------

def generate_arguments(state: AgentState, issue: dict, frameworks: list = None) -> dict:
    """Construct legal arguments for a specific issue from multiple framework perspectives.

    For each framework, the LLM builds a thesis, reasoning chain, supporting
    law, supporting facts, and a strength score.

    Args:
        state: LangGraph agent state with case data.
        issue: A single issue dict from identify_issues().
        frameworks: Optional list of frameworks to use. Defaults to all five.

    Returns:
        {"arguments": [{"framework", "thesis", "reasoning", "supporting_law",
                         "supporting_facts", "strength"}]}
    """
    if frameworks is None:
        frameworks = ["constitutional", "statutory", "common_law", "policy", "equity"]

    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")
    legal_elements = state.get("legal_elements", [])
    charges = state.get("charges", [])
    evidence = state.get("evidence_foundations", [])
    strategy = state.get("strategy_notes", "")
    witnesses = state.get("witnesses", [])
    timeline = state.get("timeline", [])

    elements_text = ""
    if legal_elements:
        elements_text = "\n".join(
            f"- {e.get('charge', '')}: {e.get('element', '')} (strength: {e.get('strength', '')})"
            for e in legal_elements[:20] if isinstance(e, dict)
        )

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    witness_text = ""
    if witnesses:
        witness_text = "\n".join(
            f"- {w.get('name', '')}: {w.get('type', '')} — {w.get('summary', '')[:120]}"
            for w in witnesses[:15] if isinstance(w, dict)
        )

    timeline_text = ""
    if timeline:
        timeline_text = "\n".join(
            f"- {t.get('date', '')}: {t.get('event', '')[:150]}"
            for t in timeline[:20] if isinstance(t, dict)
        )

    charges_text = json.dumps(charges[:10], indent=2) if charges else "[None specified]"
    frameworks_str = ", ".join(frameworks)

    prompt = f"""You are a senior litigation attorney constructing legal arguments for the following issue.

{ctx.get('directives_block', '')}

ROLE: {ctx.get('role', 'Attorney')}
CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}

ISSUE:
  Title: {issue.get('title', '')}
  Description: {issue.get('description', '')}
  Priority: {issue.get('priority', '')}

CASE SUMMARY:
{case_summary[:3000] if case_summary else '[No case summary available]'}

CHARGES/CLAIMS:
{charges_text}

LEGAL ELEMENTS:
{elements_text or '[No elements mapped]'}

EVIDENCE:
{evidence_text or '[No evidence data]'}

WITNESSES:
{witness_text or '[No witness data]'}

TIMELINE:
{timeline_text or '[No timeline data]'}

STRATEGY NOTES:
{strategy[:2000] if strategy else '[No strategy notes]'}

TASK:
Construct arguments for the above issue from each of these legal framework perspectives: {frameworks_str}.

For each framework argument, provide:
- framework: which framework this argument draws from
- thesis: one-sentence statement of the argument
- reasoning: detailed 3-5 sentence reasoning chain
- supporting_law: key statutes, case law, or legal principles that support this argument
- supporting_facts: specific facts from the case materials that support this argument
- strength: 0-100 score estimating how persuasive this argument is

Return JSON ONLY:
{{
    "arguments": [
        {{"framework": "constitutional", "thesis": "...", "reasoning": "...", "supporting_law": "...", "supporting_facts": "...", "strength": 85}},
        ...
    ]
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "arguments" in result:
            return result

        return {
            "arguments": [{"framework": "unknown", "thesis": response.content[:500],
                           "reasoning": "", "supporting_law": "", "supporting_facts": "",
                           "strength": 0}],
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("generate_arguments failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 3. Steelman Opposition
# ---------------------------------------------------------------------------

def steelman_opposition(state: AgentState, our_arguments: list) -> dict:
    """Construct the strongest possible opposition to each of our arguments.

    Adopts the role of opposing counsel and produces creative, thorough
    counter-positions that reveal every potential weakness.

    Args:
        state: LangGraph agent state with case data.
        our_arguments: List of argument dicts from generate_arguments().

    Returns:
        {"opposition_arguments": [{"responding_to", "position", "reasoning",
                                    "legal_basis", "strength"}]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")
    evidence = state.get("evidence_foundations", [])

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    arguments_text = ""
    for i, arg in enumerate(our_arguments):
        arguments_text += f"""
ARGUMENT {i}:
  Framework: {arg.get('framework', '')}
  Thesis: {arg.get('thesis', '')}
  Reasoning: {arg.get('reasoning', '')}
  Supporting Law: {arg.get('supporting_law', '')}
  Supporting Facts: {arg.get('supporting_facts', '')}
  Strength: {arg.get('strength', '')}
"""

    prompt = f"""You are opposing counsel. Your job is to construct the STRONGEST possible counter-position to each argument below. Be thorough and creative — identify every weakness, logical flaw, factual gap, and legal vulnerability.

{ctx.get('directives_block', '')}

CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}

CASE SUMMARY:
{case_summary[:2000] if case_summary else '[No case summary available]'}

EVIDENCE AVAILABLE TO BOTH SIDES:
{evidence_text or '[No evidence data]'}

ARGUMENTS TO COUNTER:
{arguments_text}

TASK:
For each argument, construct the strongest opposition. Consider:
- Constitutional challenges or statutory exceptions
- Contrary case law or distinguishable precedent
- Factual disputes, credibility issues, and alternative interpretations
- Procedural defenses, standing, jurisdictional arguments
- Policy arguments that cut the other way

For each counter-argument, provide:
- responding_to: the index number of the argument being countered (integer)
- position: one-sentence statement of the counter-position
- reasoning: detailed 3-5 sentence explanation
- legal_basis: supporting case law, statutes, or legal principles
- strength: 0-100 score of how persuasive this counter-argument is

Return JSON ONLY:
{{
    "opposition_arguments": [
        {{"responding_to": 0, "position": "...", "reasoning": "...", "legal_basis": "...", "strength": 75}},
        ...
    ]
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "opposition_arguments" in result:
            return result

        return {
            "opposition_arguments": [{"responding_to": 0, "position": response.content[:500],
                                       "reasoning": "", "legal_basis": "", "strength": 0}],
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("steelman_opposition failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 4. Build Counter-Matrix
# ---------------------------------------------------------------------------

def build_counter_matrix(state: AgentState, our_arguments: list,
                         opponent_arguments: list) -> dict:
    """Build a rebuttal matrix pairing each argument with its counter and our rebuttal.

    For each argument-vs-counter pair the LLM develops a rebuttal and
    assesses who holds the net advantage.

    Args:
        state: LangGraph agent state with case data.
        our_arguments: List of our argument dicts.
        opponent_arguments: List of opposition argument dicts from steelman_opposition().

    Returns:
        {"matrix": [{"our_argument", "their_counter", "our_rebuttal",
                      "net_advantage", "confidence"}]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")
    evidence = state.get("evidence_foundations", [])

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    # Build paired listing
    pairs_text = ""
    for opp in opponent_arguments:
        idx = opp.get("responding_to", 0)
        our_arg = our_arguments[idx] if 0 <= idx < len(our_arguments) else {}
        pairs_text += f"""
--- PAIR (Argument {idx}) ---
OUR ARGUMENT:
  Thesis: {our_arg.get('thesis', '[unknown]')}
  Reasoning: {our_arg.get('reasoning', '')}
  Supporting Law: {our_arg.get('supporting_law', '')}

THEIR COUNTER:
  Position: {opp.get('position', '')}
  Reasoning: {opp.get('reasoning', '')}
  Legal Basis: {opp.get('legal_basis', '')}
  Strength: {opp.get('strength', '')}
"""

    prompt = f"""You are a senior appellate strategist. For each pair of argument and counter-argument below, develop a rebuttal and assess who has the net advantage.

{ctx.get('directives_block', '')}

CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}

CASE SUMMARY:
{case_summary[:2000] if case_summary else '[No case summary available]'}

EVIDENCE:
{evidence_text or '[No evidence data]'}

ARGUMENT-COUNTER PAIRS:
{pairs_text}

TASK:
For each pair, provide:
- our_argument: brief summary of our argument thesis
- their_counter: brief summary of their counter-position
- our_rebuttal: 2-4 sentence rebuttal addressing their counter
- net_advantage: "ours", "theirs", or "neutral"
- confidence: 0-100 score of how confident you are in the net advantage assessment

Return JSON ONLY:
{{
    "matrix": [
        {{"our_argument": "...", "their_counter": "...", "our_rebuttal": "...", "net_advantage": "ours", "confidence": 80}},
        ...
    ]
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "matrix" in result:
            return result

        return {
            "matrix": [{"our_argument": "", "their_counter": "", "our_rebuttal": response.content[:500],
                         "net_advantage": "neutral", "confidence": 0}],
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("build_counter_matrix failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 5. Prepare Oral Arguments
# ---------------------------------------------------------------------------

def prepare_oral_arguments(state: AgentState, arguments: list,
                           time_limit: int = 15) -> dict:
    """Structure arguments for oral presentation within a time limit.

    Allocates time per topic, identifies key talking points and
    transitions, and crafts opening and closing statements.

    Args:
        state: LangGraph agent state with case data.
        arguments: List of argument dicts to present orally.
        time_limit: Total presentation time in minutes (default 15).

    Returns:
        {"segments": [{"topic", "duration_minutes", "key_points", "transitions"}],
         "total_minutes", "opening_hook", "closing_punch"}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")

    arguments_text = ""
    for i, arg in enumerate(arguments):
        arguments_text += f"""
ARGUMENT {i + 1}:
  Framework: {arg.get('framework', '')}
  Thesis: {arg.get('thesis', '')}
  Strength: {arg.get('strength', '')}
  Key Facts: {arg.get('supporting_facts', '')[:200]}
"""

    prompt = f"""You are an experienced appellate advocate preparing for oral argument.

{ctx.get('directives_block', '')}

ROLE: {ctx.get('role', 'Attorney')}
CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}
TIME LIMIT: {time_limit} minutes

CASE SUMMARY:
{case_summary[:2000] if case_summary else '[No case summary available]'}

ARGUMENTS TO PRESENT:
{arguments_text}

TASK:
Structure these arguments for oral presentation within {time_limit} minutes. Create a presentation plan that:
1. Allocates time proportionally to argument strength and importance
2. Identifies key talking points and supporting facts for each segment
3. Writes smooth transitions between topics
4. Crafts a compelling opening hook and closing punch

For each segment, provide:
- topic: the argument or topic heading
- duration_minutes: time allocation (float, e.g., 3.5)
- key_points: list of 2-4 bullet points to cover
- transitions: transition sentence to the next segment (empty string for last segment)

Return JSON ONLY:
{{
    "segments": [
        {{"topic": "...", "duration_minutes": 3.0, "key_points": ["...", "..."], "transitions": "..."}},
        ...
    ],
    "total_minutes": {time_limit},
    "opening_hook": "...",
    "closing_punch": "..."
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "segments" in result:
            return result

        return {
            "segments": [{"topic": "Full Presentation", "duration_minutes": float(time_limit),
                          "key_points": [response.content[:500]], "transitions": ""}],
            "total_minutes": time_limit,
            "opening_hook": "",
            "closing_punch": "",
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("prepare_oral_arguments failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 6. Score Arguments
# ---------------------------------------------------------------------------

def score_arguments(state: AgentState, arguments: list) -> dict:
    """Score each argument's likelihood of success with the court.

    Considers judicial temperament, precedent strength, factual support,
    and procedural posture to produce win-probability estimates and
    risk assessments.

    Args:
        state: LangGraph agent state with case data.
        arguments: List of argument dicts to score.

    Returns:
        {"scored_arguments": [{"argument", "win_probability", "risk_factors",
                                "recommendation"}],
         "overall_confidence", "strongest_argument", "weakest_argument"}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "")
    charges = state.get("charges", [])

    charges_text = json.dumps(charges[:10], indent=2) if charges else "[None specified]"

    arguments_text = ""
    for i, arg in enumerate(arguments):
        arguments_text += f"""
ARGUMENT {i + 1}:
  Framework: {arg.get('framework', '')}
  Thesis: {arg.get('thesis', '')}
  Reasoning: {arg.get('reasoning', '')}
  Supporting Law: {arg.get('supporting_law', '')}
  Supporting Facts: {arg.get('supporting_facts', '')}
  Self-Assessed Strength: {arg.get('strength', '')}
"""

    prompt = f"""You are an experienced trial judge and appellate reviewer. Score each argument's likelihood of success before the court.

{ctx.get('directives_block', '')}

CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}

CASE SUMMARY:
{case_summary[:2000] if case_summary else '[No case summary available]'}

CHARGES/CLAIMS:
{charges_text}

ARGUMENTS TO SCORE:
{arguments_text}

TASK:
Score each argument considering:
- Judicial temperament: how receptive is a typical court to this type of argument?
- Precedent strength: how strong is the cited legal authority?
- Factual support: are the supporting facts specific and verifiable?
- Procedural posture: is this the right stage/forum for this argument?

For each argument provide:
- argument: brief label (framework + short thesis)
- win_probability: 0-100 percentage chance this argument succeeds
- risk_factors: list of 1-3 specific risks or weaknesses
- recommendation: one sentence — "Lead with this", "Use as backup", "Reconsider", etc.

Also provide:
- overall_confidence: 0-100 aggregate confidence across all arguments
- strongest_argument: label of the strongest argument
- weakest_argument: label of the weakest argument

Return JSON ONLY:
{{
    "scored_arguments": [
        {{"argument": "...", "win_probability": 75, "risk_factors": ["...", "..."], "recommendation": "..."}},
        ...
    ],
    "overall_confidence": 70,
    "strongest_argument": "...",
    "weakest_argument": "..."
}}
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        result = extract_json(response.content)

        if result and isinstance(result, dict) and "scored_arguments" in result:
            return result

        return {
            "scored_arguments": [{"argument": "Parse Error", "win_probability": 0,
                                   "risk_factors": ["Could not parse LLM response"],
                                   "recommendation": "Re-run scoring"}],
            "overall_confidence": 0,
            "strongest_argument": "",
            "weakest_argument": "",
            "raw_response": response.content,
        }
    except Exception as e:
        logger.exception("score_arguments failed")
        return {"error": f"LLM call failed: {str(e)[:200]}"}


# ---------------------------------------------------------------------------
# 7. Export to Brief Skeleton
# ---------------------------------------------------------------------------

def export_to_brief_skeleton(arguments: list, counter_matrix: list = None) -> dict:
    """Transform strong arguments into a Major Document Drafter-compatible outline.

    Pure Python — no LLM call. Filters arguments with strength >= 60 and
    structures them into a section outline suitable for generate_document_outline()
    in core/nodes/major_docs.py.

    Args:
        arguments: List of argument dicts from generate_arguments().
        counter_matrix: Optional list of counter-matrix entries from
                        build_counter_matrix() to include a counter-arguments section.

    Returns:
        {"doc_type": "Major Motion", "doc_subtype": "", "document_title": str,
         "outline": [{"section_num", "title", "description", "estimated_pages"}]}
    """
    # Filter to strong arguments (strength >= 60)
    strong_args = [
        a for a in arguments
        if isinstance(a, dict) and a.get("strength", 0) >= 60
    ]

    # Fall back to all arguments if none meet the threshold
    if not strong_args and arguments:
        strong_args = sorted(
            [a for a in arguments if isinstance(a, dict)],
            key=lambda a: a.get("strength", 0),
            reverse=True,
        )[:3]

    outline = []
    section_idx = 0

    # Section I: Introduction
    intro_desc = "Introduce the case, the relief sought, and summarize the key arguments."
    if strong_args:
        arg_previews = "; ".join(
            a.get("thesis", "")[:80] for a in strong_args[:3]
        )
        intro_desc += f" Preview of arguments: {arg_previews}"

    outline.append({
        "section_num": _ROMAN_NUMERALS[section_idx],
        "title": "Introduction",
        "description": intro_desc,
        "estimated_pages": 2,
    })
    section_idx += 1

    # One section per strong argument
    for arg in strong_args:
        if section_idx >= len(_ROMAN_NUMERALS) - 2:
            # Reserve space for Counter-Arguments and Conclusion
            break

        framework = arg.get("framework", "Legal")
        thesis = arg.get("thesis", "")
        reasoning = arg.get("reasoning", "")
        supporting_law = arg.get("supporting_law", "")

        title = f"{framework.replace('_', ' ').title()} Argument"
        desc = thesis[:200]
        if reasoning:
            desc += f" {reasoning[:150]}"
        if supporting_law:
            desc += f" Key authority: {supporting_law[:100]}"

        strength = arg.get("strength", 50)
        pages = 3 if strength >= 80 else 2

        outline.append({
            "section_num": _ROMAN_NUMERALS[section_idx],
            "title": title,
            "description": desc.strip(),
            "estimated_pages": pages,
        })
        section_idx += 1

    # Counter-Arguments section (if matrix provided)
    if counter_matrix and section_idx < len(_ROMAN_NUMERALS) - 1:
        adverse = [
            m for m in counter_matrix
            if isinstance(m, dict) and m.get("net_advantage") == "theirs"
        ]
        neutral = [
            m for m in counter_matrix
            if isinstance(m, dict) and m.get("net_advantage") == "neutral"
        ]
        counter_desc = (
            f"Address anticipated counter-arguments. "
            f"{len(adverse)} adverse points and {len(neutral)} contested points "
            f"require preemptive rebuttal."
        )
        outline.append({
            "section_num": _ROMAN_NUMERALS[section_idx],
            "title": "Anticipated Counter-Arguments and Rebuttals",
            "description": counter_desc,
            "estimated_pages": 2,
        })
        section_idx += 1

    # Conclusion
    if section_idx < len(_ROMAN_NUMERALS):
        outline.append({
            "section_num": _ROMAN_NUMERALS[section_idx],
            "title": "Conclusion",
            "description": "Summarize the strongest arguments, restate the relief sought, and provide a clear call to action for the court.",
            "estimated_pages": 1,
        })

    # Build document title from strongest argument
    doc_title = "MEMORANDUM IN SUPPORT OF MOTION"
    if strong_args:
        top_framework = strong_args[0].get("framework", "")
        if top_framework:
            doc_title = f"MEMORANDUM IN SUPPORT OF MOTION — {top_framework.replace('_', ' ').upper()} GROUNDS"

    return {
        "doc_type": "Major Motion",
        "doc_subtype": "",
        "document_title": doc_title,
        "outline": outline,
    }
