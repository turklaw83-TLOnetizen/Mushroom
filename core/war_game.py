# ---- AI War Game: Adversarial Case Simulation Engine ---------------------
# 5-round adversarial simulation that stress-tests a case through theory,
# evidence, witness, elements, and jury challenges.  Generates attacks from
# an AI opposing counsel persona, evaluates attorney responses, simulates
# jury deliberation, and produces a comprehensive battle report.
# Storage: data/cases/{case_id}/war_game_sessions/{prep_id}/{session_id}.json

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm, invoke_with_retry
from core.nodes._common import extract_json
from core.state import AgentState, get_case_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROUND_TYPES = ["theory", "evidence", "witnesses", "elements", "jury"]

DIFFICULTY_PERSONAS: Dict[str, str] = {
    "standard": "an experienced opposing counsel preparing for trial",
    "aggressive": (
        "an aggressive trial attorney who exploits every opening and inconsistency"
    ),
    "ruthless": (
        "the most formidable adversary in the jurisdiction -- nothing escapes "
        "your scrutiny, no weakness goes unexploited"
    ),
}


# ---------------------------------------------------------------------------
# Session Persistence Helpers
# ---------------------------------------------------------------------------

def _sessions_dir(data_dir: str, case_id: str, prep_id: str) -> Path:
    """Return the directory where war-game session files are stored."""
    return Path(data_dir) / "cases" / case_id / "war_game_sessions" / prep_id


def _session_path(data_dir: str, case_id: str, prep_id: str, session_id: str) -> Path:
    """Return the path to a single session JSON file."""
    return _sessions_dir(data_dir, case_id, prep_id) / f"{session_id}.json"


def save_war_game_session(
    data_dir: str, case_id: str, prep_id: str, session: dict
) -> str:
    """Persist a war-game session to disk.

    Creates the storage directory if it doesn't exist.  If the session
    already has an ``id`` field, the file is overwritten in place.
    Otherwise a new ID is generated.

    Args:
        data_dir: Root data directory (e.g. ``"data"``).
        case_id: The case identifier.
        prep_id: The preparation identifier within the case.
        session: The full session dict to save.

    Returns:
        The session ID (existing or newly generated).
    """
    session_id = session.get("id") or uuid.uuid4().hex[:12]
    session["id"] = session_id
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    path = _session_path(data_dir, case_id, prep_id, session_id)
    os.makedirs(path.parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, indent=2, default=str)

    return session_id


def load_war_game_session(
    data_dir: str, case_id: str, prep_id: str, session_id: str
) -> Optional[dict]:
    """Load a single war-game session from disk.

    Returns:
        The session dict, or ``None`` if the file does not exist or is corrupt.
    """
    path = _session_path(data_dir, case_id, prep_id, session_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("Failed to load war-game session %s", path)
        return None


def load_war_game_sessions(
    data_dir: str, case_id: str, prep_id: str
) -> List[dict]:
    """Return a metadata-only index of all sessions for a prep, newest first.

    Each entry contains: ``id``, ``difficulty``, ``status``, ``created_at``,
    ``current_round``, ``overall_score``.
    """
    directory = _sessions_dir(data_dir, case_id, prep_id)
    if not directory.exists():
        return []

    index: List[dict] = []
    for fp in directory.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            # Extract report-level overall_score if available
            report = data.get("report") or {}
            index.append({
                "id": data.get("id", fp.stem),
                "difficulty": data.get("difficulty", "standard"),
                "status": data.get("status", "unknown"),
                "created_at": data.get("created_at", ""),
                "current_round": data.get("current_round", 0),
                "overall_score": report.get("overall_score"),
            })
        except Exception:
            logger.warning("Skipping corrupt war-game file %s", fp)
            continue

    index.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return index


def delete_war_game_session(
    data_dir: str, case_id: str, prep_id: str, session_id: str
) -> bool:
    """Delete a war-game session file.  Returns True if found and removed."""
    path = _session_path(data_dir, case_id, prep_id, session_id)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            logger.exception("Failed to delete war-game session %s", path)
    return False


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------

def create_session(difficulty: str = "standard") -> dict:
    """Create a new war-game session skeleton.

    The session starts with ``status='active'`` and five rounds, each
    initialised to ``status='pending'``.

    Args:
        difficulty: One of ``"standard"``, ``"aggressive"``, ``"ruthless"``.

    Returns:
        A fully-structured session dict ready for the first round.
    """
    if difficulty not in DIFFICULTY_PERSONAS:
        difficulty = "standard"

    now = datetime.now(timezone.utc).isoformat()
    session_id = uuid.uuid4().hex[:12]

    rounds: List[dict] = []
    for round_type in ROUND_TYPES:
        rounds.append({
            "type": round_type,
            "status": "pending",
            "attack": None,
            "response": None,
            "evaluation": None,
        })

    return {
        "id": session_id,
        "difficulty": difficulty,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "current_round": 0,
        "rounds": rounds,
        "report": None,
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _safe_str(value: Any, max_len: int = 3000) -> str:
    """Safely coerce a value to a truncated string."""
    if value is None:
        return ""
    s = str(value) if not isinstance(value, str) else value
    return s[:max_len]


def _format_list_of_dicts(items: Any, fields: List[str], limit: int = 15) -> str:
    """Format a list of dicts into readable lines for prompts."""
    if not items or not isinstance(items, list):
        return "[None available]"
    lines: List[str] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        parts = [f"{f}: {item.get(f, '')}" for f in fields if item.get(f)]
        if parts:
            lines.append("- " + " | ".join(parts))
    return "\n".join(lines) if lines else "[None available]"


def _previous_round_summary(session: dict, up_to_round: int) -> str:
    """Build a summary of completed rounds up to (but not including) the given index."""
    parts: List[str] = []
    for i in range(up_to_round):
        rnd = session["rounds"][i]
        if rnd.get("status") != "completed":
            continue
        ev = rnd.get("evaluation") or {}
        score = ev.get("score", "N/A")
        parts.append(
            f"Round {i + 1} ({rnd['type']}): score={score}"
        )
        # Include rulings / witness scores / element coverage if present
        if ev.get("rulings"):
            excluded = [r for r in ev["rulings"] if r.get("ruling") == "excluded"]
            parts.append(f"  Evidence rulings: {len(ev['rulings'])} total, {len(excluded)} excluded")
        if ev.get("witness_scores"):
            low_cred = [w for w in ev["witness_scores"] if w.get("credibility", 100) < 50]
            parts.append(f"  Witness credibility: {len(low_cred)} witnesses below 50")
        if ev.get("element_coverage"):
            gaps = [e for e in ev["element_coverage"] if not e.get("covered")]
            parts.append(f"  Element gaps: {len(gaps)} uncovered")
    return "\n".join(parts) if parts else "[No previous rounds completed]"


def _gather_round_context(state: dict, session: dict, round_type: str) -> str:
    """Build a context string tailored to the round type.

    Pulls relevant fields from the agent state and includes results
    from prior rounds so that each attack builds on cumulative effects.

    Args:
        state: The LangGraph agent state dict.
        session: The current war-game session dict.
        round_type: One of the ``ROUND_TYPES`` values.

    Returns:
        A multi-section string suitable for embedding in an LLM prompt.
    """
    ctx = get_case_context(state)
    sections: List[str] = []

    # -- Common header --
    sections.append(f"CASE TYPE: {ctx.get('case_type_desc', state.get('case_type', 'criminal'))}")
    sections.append(f"CLIENT: {state.get('client_name', '[Client]')}")
    sections.append(f"OUR SIDE: {ctx.get('our_side', 'the defense')}")
    sections.append(f"OPPONENT: {ctx.get('opponent', 'the prosecution')}")

    if ctx.get("directives_block"):
        sections.append(ctx["directives_block"])

    round_idx = ROUND_TYPES.index(round_type)

    # -- Round-specific data --
    if round_type == "theory":
        sections.append(
            f"\nCASE SUMMARY:\n{_safe_str(state.get('case_summary'), 3000) or '[No summary]'}"
        )
        sections.append(
            f"\nSTRATEGY NOTES:\n{_safe_str(state.get('strategy_notes'), 2000) or '[No strategy]'}"
        )
        sections.append(
            f"\nDEVIL'S ADVOCATE NOTES:\n{_safe_str(state.get('devils_advocate_notes'), 2000) or '[None]'}"
        )

    elif round_type == "evidence":
        sections.append(
            f"\nEVIDENCE FOUNDATIONS:\n{_format_list_of_dicts(state.get('evidence_foundations'), ['item', 'admissibility', 'attack', 'source_ref'])}"
        )
        sections.append(
            f"\nCONSISTENCY CHECK:\n{_format_list_of_dicts(state.get('consistency_check'), ['fact', 'source_a', 'source_b', 'notes'])}"
        )
        sections.append(f"\nPREVIOUS ROUNDS:\n{_previous_round_summary(session, round_idx)}")

    elif round_type == "witnesses":
        sections.append(
            f"\nWITNESSES:\n{_format_list_of_dicts(state.get('witnesses'), ['name', 'type', 'goal', 'summary'], limit=20)}"
        )
        sections.append(
            f"\nCROSS-EXAMINATION PLAN:\n{_format_list_of_dicts(state.get('cross_examination_plan'), ['witness', 'goal', 'approach'], limit=15)}"
        )
        sections.append(f"\nPREVIOUS ROUNDS:\n{_previous_round_summary(session, round_idx)}")

    elif round_type == "elements":
        sections.append(
            f"\nLEGAL ELEMENTS:\n{_format_list_of_dicts(state.get('legal_elements'), ['charge', 'element', 'evidence', 'strength'])}"
        )
        charges = state.get("charges", [])
        charges_text = json.dumps(charges[:10], indent=2) if charges else "[None specified]"
        sections.append(f"\nCHARGES/CLAIMS:\n{charges_text}")
        sections.append(f"\nPREVIOUS ROUNDS:\n{_previous_round_summary(session, round_idx)}")

    elif round_type == "jury":
        # Jury round gets everything
        sections.append(
            f"\nCASE SUMMARY:\n{_safe_str(state.get('case_summary'), 2000) or '[No summary]'}"
        )
        sections.append(
            f"\nVOIR DIRE PROFILE:\n{json.dumps(state.get('voir_dire', {}), indent=2, default=str)[:1500]}"
        )
        sections.append(
            f"\nMOCK JURY FEEDBACK:\n{_format_list_of_dicts(state.get('mock_jury_feedback'), ['juror', 'verdict', 'reaction'])}"
        )
        sections.append(f"\nALL ROUND RESULTS:\n{_previous_round_summary(session, round_idx)}")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Round Attack Generation
# ---------------------------------------------------------------------------

_ROUND_ATTACK_FOCUS: Dict[str, str] = {
    "theory": (
        "Attack the opposing counsel's theory of the case. Challenge their "
        "narrative, identify logical gaps, highlight alternative explanations, "
        "and expose weaknesses in their burden-of-proof strategy."
    ),
    "evidence": (
        "Challenge the admissibility and weight of the opposing counsel's "
        "evidence. File motions in limine, challenge chain of custody, "
        "identify hearsay issues, authentication failures, and prejudicial "
        "impact that outweighs probative value."
    ),
    "witnesses": (
        "Attack the credibility and testimony of the opposing side's witnesses. "
        "Identify prior inconsistent statements, bias, motive to lie, lack of "
        "personal knowledge, character issues, and expert qualification gaps."
    ),
    "elements": (
        "Challenge whether the opposing side can satisfy each legal element "
        "required. Identify elements with insufficient evidence, conflicting "
        "proof, or gaps that create reasonable doubt / failure of proof."
    ),
    "jury": (
        "You are now simulating the jury deliberation. Consider how all "
        "previous rounds of attack and defense would land with a jury. "
        "Assess the cumulative impact of theory weaknesses, excluded "
        "evidence, damaged witnesses, and element gaps on the jury's verdict."
    ),
}


def generate_round_attack(state: dict, session: dict, round_type: str) -> str:
    """Generate an AI attack for the specified round.

    The attack is produced by an LLM adopting the difficulty persona and
    focusing on the round's topic.  The session is updated in place with
    the attack text and round status transitions.

    Args:
        state: The LangGraph agent state dict with case data.
        session: The current war-game session (mutated in place).
        round_type: One of ``ROUND_TYPES``.

    Returns:
        The attack text as a Markdown string.

    Raises:
        ValueError: If the round_type is invalid.
        RuntimeError: If no LLM is configured.
    """
    if round_type not in ROUND_TYPES:
        raise ValueError(f"Invalid round type: {round_type}")

    round_idx = ROUND_TYPES.index(round_type)
    rnd = session["rounds"][round_idx]

    # Mark as attacking
    rnd["status"] = "attacking"
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    difficulty = session.get("difficulty", "standard")
    persona = DIFFICULTY_PERSONAS.get(difficulty, DIFFICULTY_PERSONAS["standard"])
    context_block = _gather_round_context(state, session, round_type)
    focus = _ROUND_ATTACK_FOCUS[round_type]

    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        raise RuntimeError("No LLM configured -- cannot generate attack.")

    system_prompt = (
        f"You are {persona}. You are in round {round_idx + 1} of 5 of an "
        f"adversarial war-game simulation against the opposing legal team.\n\n"
        f"ROUND FOCUS ({round_type.upper()}):\n{focus}\n\n"
        f"Your job is to mount the most devastating, well-reasoned attack "
        f"possible. Be specific -- cite evidence, name witnesses, quote "
        f"elements. Do NOT hold back."
    )

    user_prompt = (
        f"Here is the case context and data for your attack:\n\n"
        f"{context_block}\n\n"
        f"Now deliver your round {round_idx + 1} ({round_type}) attack. "
        f"Structure your attack with clear headings and numbered points. "
        f"Be thorough, specific, and devastating."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = invoke_with_retry(llm, messages)
        attack_text = response.content
    except Exception as exc:
        logger.exception("generate_round_attack failed for round %s", round_type)
        attack_text = f"[Attack generation failed: {str(exc)[:200]}]"

    rnd["attack"] = attack_text

    # Jury round auto-completes (no attorney response needed)
    if round_type == "jury":
        rnd["status"] = "completed"
    else:
        rnd["status"] = "awaiting_response"

    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    return attack_text


# ---------------------------------------------------------------------------
# Response Evaluation
# ---------------------------------------------------------------------------

def evaluate_round_response(
    state: dict, session: dict, round_type: str, response: str
) -> dict:
    """Evaluate the attorney's response to a round attack.

    An LLM acting as a fair but strict evaluator scores the response and
    identifies strengths and vulnerabilities.  Round-specific extras are
    included (e.g. evidence rulings for round 2, witness credibility
    for round 3, element coverage for round 4).

    Args:
        state: The LangGraph agent state dict.
        session: The current war-game session (mutated in place).
        round_type: One of ``ROUND_TYPES`` (should not be ``"jury"``).
        response: The attorney's written response to the attack.

    Returns:
        The evaluation dict containing ``score``, ``strengths``,
        ``vulnerabilities``, and round-specific data.
    """
    if round_type not in ROUND_TYPES:
        raise ValueError(f"Invalid round type: {round_type}")

    round_idx = ROUND_TYPES.index(round_type)
    rnd = session["rounds"][round_idx]

    # Store the attorney's response
    rnd["response"] = response

    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        raise RuntimeError("No LLM configured -- cannot evaluate response.")

    context_block = _gather_round_context(state, session, round_type)

    # Build round-specific evaluation schema
    extra_fields = ""
    if round_type == "evidence":
        extra_fields = (
            ',\n    "rulings": [\n'
            '      {"item": "...", "ruling": "admitted|excluded", "reasoning": "..."}\n'
            "    ]"
        )
    elif round_type == "witnesses":
        extra_fields = (
            ',\n    "witness_scores": [\n'
            '      {"name": "...", "credibility": 0-100, "vulnerabilities": "..."}\n'
            "    ]"
        )
    elif round_type == "elements":
        extra_fields = (
            ',\n    "element_coverage": [\n'
            '      {"charge": "...", "element": "...", "covered": true|false, "gap": "..."}\n'
            "    ]"
        )

    system_prompt = (
        "You are a senior judicial evaluator assessing a legal war-game exercise. "
        "You are fair but strict. Score responses on legal reasoning quality, "
        "specificity of citations and evidence, tactical effectiveness, and how "
        "well the response neutralises the attack."
    )

    user_prompt = (
        f"CASE CONTEXT:\n{context_block}\n\n"
        f"ROUND: {round_idx + 1} ({round_type.upper()})\n\n"
        f"ATTACK:\n{rnd.get('attack', '[No attack recorded]')}\n\n"
        f"ATTORNEY RESPONSE:\n{response}\n\n"
        f"Evaluate this response. Return JSON ONLY:\n"
        f"{{\n"
        f'    "score": 0-100,\n'
        f'    "strengths": ["strength 1", "strength 2", ...],\n'
        f'    "vulnerabilities": ["vulnerability 1", "vulnerability 2", ...]'
        f"{extra_fields}\n"
        f"}}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    fallback: Dict[str, Any] = {
        "score": 50,
        "strengths": ["Response submitted"],
        "vulnerabilities": ["Evaluation could not be parsed"],
    }

    try:
        llm_response = invoke_with_retry(llm, messages)
        result = extract_json(llm_response.content)

        if result and isinstance(result, dict) and "score" in result:
            evaluation = result
        else:
            logger.warning("Could not parse evaluation JSON for round %s", round_type)
            evaluation = fallback
            evaluation["raw_response"] = llm_response.content[:1000]
    except Exception as exc:
        logger.exception("evaluate_round_response failed for round %s", round_type)
        evaluation = fallback
        evaluation["error"] = str(exc)[:200]

    # Persist to session
    rnd["evaluation"] = evaluation
    rnd["status"] = "completed"
    session["current_round"] = round_idx + 1
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    return evaluation


# ---------------------------------------------------------------------------
# Jury Verdict Simulation (Round 5)
# ---------------------------------------------------------------------------

_JUROR_PERSONAS = [
    {
        "name": "Juror #1 - Patricia",
        "background": "Retired schoolteacher, 62, methodical thinker, values order and rules",
        "leanings": "Tends to trust authority figures and official documentation",
    },
    {
        "name": "Juror #2 - Marcus",
        "background": "Small business owner, 45, pragmatic, skeptical of institutions",
        "leanings": "Distrusts government overreach, values personal liberty",
    },
    {
        "name": "Juror #3 - Diana",
        "background": "Nurse, 38, empathetic, detail-oriented, strong moral compass",
        "leanings": "Focuses on human impact and credibility of witnesses",
    },
    {
        "name": "Juror #4 - Robert",
        "background": "Engineer, 55, analytical, requires clear logical proof",
        "leanings": "Demands strong evidence chains, skeptical of circumstantial cases",
    },
    {
        "name": "Juror #5 - Angela",
        "background": "Social worker, 33, community-minded, aware of systemic biases",
        "leanings": "Questions investigative thoroughness, sensitive to procedural fairness",
    },
]


def simulate_jury_verdict(state: dict, session: dict) -> dict:
    """Run a 5-juror deliberation simulation using ALL round results.

    Each juror receives a distinct persona and considers the cumulative
    impact of all five rounds.  The function determines a verdict based
    on the majority of individual juror votes.

    Args:
        state: The LangGraph agent state dict.
        session: The current war-game session (mutated in place).

    Returns:
        A dict with ``verdict``, ``juror_verdicts``, and ``score``.
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        raise RuntimeError("No LLM configured -- cannot simulate jury verdict.")

    ctx = get_case_context(state)
    all_rounds_summary = _previous_round_summary(session, len(ROUND_TYPES))

    # Also include the jury-round attack (closing arguments summary)
    jury_round = session["rounds"][4]
    jury_attack = jury_round.get("attack", "")

    case_summary = _safe_str(state.get("case_summary"), 2000)
    charges = state.get("charges", [])
    charges_text = json.dumps(charges[:10], indent=2) if charges else "[None specified]"

    # Determine appropriate verdict labels based on case type
    case_type = state.get("case_type", "criminal")
    if "civil" in case_type:
        verdict_options = "liable|not_liable|hung"
        verdict_label_a = "liable"
        verdict_label_b = "not_liable"
    else:
        verdict_options = "guilty|not_guilty|hung"
        verdict_label_a = "guilty"
        verdict_label_b = "not_guilty"

    jurors_block = "\n".join(
        f"- {j['name']}: {j['background']}. Leanings: {j['leanings']}"
        for j in _JUROR_PERSONAS
    )

    system_prompt = (
        "You are simulating a jury deliberation in a legal war-game exercise. "
        "You must embody each juror's persona authentically -- their background, "
        "values, and cognitive style should shape how they weigh the evidence."
    )

    user_prompt = (
        f"CASE TYPE: {ctx.get('case_type_desc', case_type)}\n"
        f"CLIENT: {state.get('client_name', '[Client]')}\n\n"
        f"CASE SUMMARY:\n{case_summary or '[No summary]'}\n\n"
        f"CHARGES/CLAIMS:\n{charges_text}\n\n"
        f"WAR-GAME ROUND RESULTS:\n{all_rounds_summary}\n\n"
        f"CLOSING ARGUMENTS SUMMARY:\n{jury_attack[:2000] if jury_attack else '[None]'}\n\n"
        f"JUROR PANEL:\n{jurors_block}\n\n"
        f"Simulate the deliberation. Each juror should reason through the "
        f"evidence based on their persona. Consider:\n"
        f"- Theory strengths/weaknesses from Round 1\n"
        f"- Evidence rulings from Round 2 (what was excluded?)\n"
        f"- Witness credibility from Round 3\n"
        f"- Element coverage gaps from Round 4\n\n"
        f"Return JSON ONLY:\n"
        f"{{\n"
        f'    "verdict": "{verdict_options}",\n'
        f'    "juror_verdicts": [\n'
        f'        {{"juror": "Juror #1 - Patricia", "vote": "{verdict_label_a}|{verdict_label_b}", "reasoning": "2-3 sentences"}},\n'
        f"        ... (all 5 jurors)\n"
        f"    ],\n"
        f'    "score": 0-100,\n'
        f'    "deliberation_notes": "Brief summary of key deliberation dynamics"\n'
        f"}}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    fallback: Dict[str, Any] = {
        "verdict": "hung",
        "juror_verdicts": [
            {"juror": j["name"], "vote": "hung", "reasoning": "Deliberation simulation failed"}
            for j in _JUROR_PERSONAS
        ],
        "score": 50,
        "deliberation_notes": "Jury simulation encountered an error.",
    }

    try:
        llm_response = invoke_with_retry(llm, messages)
        result = extract_json(llm_response.content)

        if result and isinstance(result, dict) and "verdict" in result:
            verdict_data = result
        else:
            logger.warning("Could not parse jury verdict JSON")
            verdict_data = fallback
            verdict_data["raw_response"] = llm_response.content[:1000]
    except Exception as exc:
        logger.exception("simulate_jury_verdict failed")
        verdict_data = fallback
        verdict_data["error"] = str(exc)[:200]

    # Persist to the jury round
    jury_round["evaluation"] = verdict_data
    jury_round["status"] = "completed"
    session["current_round"] = 5
    session["status"] = "completed"
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    return verdict_data


# ---------------------------------------------------------------------------
# Battle Report Generation
# ---------------------------------------------------------------------------

def generate_battle_report(state: dict, session: dict) -> dict:
    """Generate a comprehensive post-game battle report.

    Analyses ALL round results using an LLM to produce an overall score,
    ranked vulnerabilities with mitigation strategies, and contingency
    cards for trial use.

    Args:
        state: The LangGraph agent state dict.
        session: The completed war-game session (mutated in place).

    Returns:
        The full report dict which is also stored on ``session["report"]``.
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        raise RuntimeError("No LLM configured -- cannot generate battle report.")

    ctx = get_case_context(state)

    # Compile all round data
    rounds_detail: List[str] = []
    round_scores: List[dict] = []
    for i, rnd in enumerate(session.get("rounds", [])):
        ev = rnd.get("evaluation") or {}
        score = ev.get("score", "N/A")
        round_scores.append({"type": rnd.get("type", ROUND_TYPES[i] if i < 5 else "unknown"), "score": score})

        detail = f"\n--- ROUND {i + 1}: {rnd.get('type', '').upper()} (Score: {score}) ---"
        if rnd.get("attack"):
            detail += f"\nATTACK (excerpt):\n{_safe_str(rnd['attack'], 800)}"
        if rnd.get("response"):
            detail += f"\nRESPONSE (excerpt):\n{_safe_str(rnd['response'], 800)}"
        if ev.get("strengths"):
            detail += f"\nSTRENGTHS: {', '.join(ev['strengths'][:5])}"
        if ev.get("vulnerabilities"):
            detail += f"\nVULNERABILITIES: {', '.join(ev['vulnerabilities'][:5])}"
        if ev.get("rulings"):
            excluded = [r["item"] for r in ev["rulings"] if r.get("ruling") == "excluded"]
            if excluded:
                detail += f"\nEXCLUDED EVIDENCE: {', '.join(excluded[:5])}"
        if ev.get("witness_scores"):
            for ws in ev["witness_scores"][:5]:
                detail += f"\n  Witness {ws.get('name', '?')}: credibility={ws.get('credibility', '?')}"
        if ev.get("element_coverage"):
            gaps = [e for e in ev["element_coverage"] if not e.get("covered")]
            if gaps:
                detail += f"\nELEMENT GAPS: {', '.join(g.get('element', '?') for g in gaps[:5])}"

        rounds_detail.append(detail)

    # Get jury data
    jury_eval = session["rounds"][4].get("evaluation") or {} if len(session.get("rounds", [])) > 4 else {}
    verdict = jury_eval.get("verdict", "unknown")
    juror_verdicts = jury_eval.get("juror_verdicts", [])

    rounds_text = "\n".join(rounds_detail)

    system_prompt = (
        "You are a senior litigation consultant producing a post-game battle "
        "report for a legal war-game exercise. Your analysis must be actionable "
        "and specific -- identify exact vulnerabilities and provide concrete "
        "mitigation strategies."
    )

    user_prompt = (
        f"CASE TYPE: {ctx.get('case_type_desc', state.get('case_type', 'criminal'))}\n"
        f"CLIENT: {state.get('client_name', '[Client]')}\n"
        f"DIFFICULTY: {session.get('difficulty', 'standard')}\n"
        f"JURY VERDICT: {verdict}\n\n"
        f"ROUND-BY-ROUND RESULTS:\n{rounds_text}\n\n"
        f"Generate a comprehensive battle report. Return JSON ONLY:\n"
        f"{{\n"
        f'    "overall_score": 0-100,\n'
        f'    "verdict": "{verdict}",\n'
        f'    "executive_summary": "2-3 sentence overall assessment",\n'
        f'    "vulnerabilities": [\n'
        f"        {{\n"
        f'            "rank": 1,\n'
        f'            "severity": "critical|high|medium|low",\n'
        f'            "area": "theory|evidence|witnesses|elements|procedure",\n'
        f'            "description": "specific description of the vulnerability",\n'
        f'            "exploit_scenario": "how opposing counsel could exploit this",\n'
        f'            "mitigation": "concrete steps to address this vulnerability"\n'
        f"        }}\n"
        f"    ],\n"
        f'    "contingency_cards": [\n'
        f"        {{\n"
        f'            "trigger": "specific event or ruling that triggers this card",\n'
        f'            "response": "prepared response or action to take",\n'
        f'            "authority": "legal authority supporting this response",\n'
        f'            "evidence_to_cite": "specific evidence to reference",\n'
        f'            "risk_level": "low|medium|high"\n'
        f"        }}\n"
        f"    ]\n"
        f"}}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    fallback: Dict[str, Any] = {
        "overall_score": 50,
        "verdict": verdict,
        "executive_summary": "Battle report generation encountered an error.",
        "round_scores": round_scores,
        "vulnerabilities": [],
        "contingency_cards": [],
        "juror_verdicts": juror_verdicts,
    }

    try:
        llm_response = invoke_with_retry(llm, messages)
        result = extract_json(llm_response.content)

        if result and isinstance(result, dict) and "overall_score" in result:
            report = result
        else:
            logger.warning("Could not parse battle report JSON")
            report = fallback
            report["raw_response"] = llm_response.content[:1000]
    except Exception as exc:
        logger.exception("generate_battle_report failed")
        report = fallback
        report["error"] = str(exc)[:200]

    # Always ensure round_scores and juror_verdicts are present
    report.setdefault("round_scores", round_scores)
    report.setdefault("juror_verdicts", juror_verdicts)
    report.setdefault("verdict", verdict)

    # Save to session
    session["report"] = report
    session["status"] = "completed"
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    return report
