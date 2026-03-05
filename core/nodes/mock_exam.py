# ---- Mock Examination Simulator Engine ------------------------------------
# Interactive AI witness persona for practice examination sessions.
# Includes coaching analysis, opposing counsel objections, and scoring.

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.nodes._common import (
    CITATION_INSTRUCTION,
    extract_json,
    format_docs_with_sources,
    get_case_context,
    get_llm,
    invoke_with_retry,
    invoke_with_retry_streaming,
)

logger = logging.getLogger(__name__)

# Maximum message history sent to persona prompt (prevent context overflow)
MAX_HISTORY_MESSAGES = 20

# Max document text chars in persona prompt
MAX_DOC_TEXT_CHARS = 8000


# ---- Witness Persona -------------------------------------------------------

def build_witness_persona_prompt(
    state: dict,
    witness: dict,
    exam_type: str,
    session_messages: list,
    document_text: str = "",
) -> list:
    """Build the full LangChain message list for the witness persona LLM call.

    Args:
        state: Full prep state from CaseManager.load_prep_state().
        witness: Witness dict from state["witnesses"].
        exam_type: "cross" or "direct".
        session_messages: List of session message dicts with role/content keys.
        document_text: Pre-gathered document text mentioning this witness.

    Returns:
        List of LangChain message objects ready for LLM invocation.
    """
    ctx = get_case_context(state)
    w_name = witness.get("name", witness.get("witness", "Unknown Witness"))
    w_type = witness.get("type", witness.get("role", "Unknown"))
    w_desc = witness.get("description", witness.get("testimony", ""))
    w_goal = witness.get("goal", "")

    case_summary = state.get("case_summary", "No case summary available.")
    inconsistencies = _format_witness_inconsistencies(state, w_name)

    # Cross-exam vs direct persona behavior
    if exam_type == "cross":
        behavior = f"""You are being cross-examined by {ctx['our_side']}'s attorney.
BEHAVIOR RULES FOR CROSS-EXAMINATION:
- Be defensive but truthful. Answer only what is directly asked.
- Do NOT volunteer additional information or elaborate unless pressed.
- Give short, direct answers — prefer "Yes", "No", "I don't recall" when possible.
- You may be evasive on details that could hurt your credibility, but do not outright lie.
- If the attorney pins you on a specific document or prior statement, you must acknowledge it.
- Show realistic witness behaviors: slight hesitation before damaging admissions, qualifying answers, attempting to explain unfavorable facts.
- If cornered on a contradiction, show discomfort but don't break character."""
    else:
        behavior = f"""You are being examined by your own attorney ({ctx['our_side']}).
BEHAVIOR RULES FOR DIRECT EXAMINATION:
- Be cooperative and tell your story clearly and fully.
- Elaborate when appropriate — give narrative answers that help the jury understand.
- Show genuine emotion where appropriate (concern, empathy, professionalism).
- Present your testimony in a logical, chronological order when possible.
- Do not anticipate questions — wait for each question and answer it thoroughly.
- If you don't know something, say so honestly."""

    # Build prior examination context if available
    exam_context = ""
    cross_plan = state.get("cross_examination_plan", [])
    direct_plan = state.get("direct_examination_plan", [])
    for entry in cross_plan:
        if isinstance(entry, dict) and entry.get("witness", "").lower() == w_name.lower():
            topics = entry.get("topics", [])
            if topics:
                topic_list = ", ".join(t.get("title", "") for t in topics[:5] if isinstance(t, dict))
                exam_context += f"\nKnown cross-exam topics prepared against you: {topic_list}"
    for entry in direct_plan:
        if isinstance(entry, dict) and entry.get("witness", "").lower() == w_name.lower():
            topics = entry.get("topics", [])
            if topics:
                topic_list = ", ".join(t.get("title", "") for t in topics[:5] if isinstance(t, dict))
                exam_context += f"\nKnown direct-exam topics prepared for you: {topic_list}"

    system_prompt = f"""You are {w_name}, a {w_type} witness in a {ctx['case_type_desc']} case.

ABSOLUTE RULES:
- You ARE this witness. Respond in first person as they would.
- NEVER break character. NEVER acknowledge you are an AI.
- NEVER use phrases like "As an AI" or "I'm simulating" — you ARE this person.
- Base all answers on the case documents and known testimony below.
- If asked about something not covered in the documents, say you don't recall or don't know.
- Maintain consistent testimony — do not contradict your own prior answers in this session.

{behavior}

YOUR BACKGROUND AND ROLE:
{w_desc}
{f"Your objective in this case: " + w_goal if w_goal else ""}
{exam_context}

CASE SUMMARY:
{case_summary[:3000]}

DOCUMENTS AND EVIDENCE RELATED TO YOUR TESTIMONY:
{document_text[:MAX_DOC_TEXT_CHARS] if document_text else "No specific documents provided."}

{f"KNOWN VULNERABILITIES IN YOUR TESTIMONY (the attorney may try to exploit these):{chr(10)}{inconsistencies}" if inconsistencies else ""}

Respond naturally as this witness would. Keep answers concise on cross-examination, more detailed on direct."""

    messages = [SystemMessage(content=system_prompt)]

    # Add conversation history (limit to recent messages to stay within context)
    history = [m for m in session_messages if m.get("role") in ("attorney", "witness")]
    if len(history) > MAX_HISTORY_MESSAGES:
        # Summarize earlier messages
        early_count = len(history) - MAX_HISTORY_MESSAGES
        messages.append(SystemMessage(
            content=f"[{early_count} earlier exchanges omitted for brevity. The examination has been ongoing.]"
        ))
        history = history[-MAX_HISTORY_MESSAGES:]

    for msg in history:
        if msg["role"] == "attorney":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "witness":
            messages.append(AIMessage(content=msg["content"]))

    return messages


def generate_witness_response(
    state: dict,
    witness: dict,
    exam_type: str,
    session_messages: list,
    document_text: str = "",
    provider: str = None,
) -> str:
    """Generate a single (non-streaming) witness response."""
    messages = build_witness_persona_prompt(
        state, witness, exam_type, session_messages, document_text
    )
    llm = get_llm(provider, max_output_tokens=2048)
    if not llm:
        return "I... I'm sorry, could you repeat the question?"
    response = invoke_with_retry(llm, messages)
    return response.content if hasattr(response, "content") else str(response)


def stream_witness_response(
    state: dict,
    witness: dict,
    exam_type: str,
    session_messages: list,
    document_text: str = "",
    provider: str = None,
) -> Generator[Tuple[str, str], None, None]:
    """Streaming generator for witness response.

    Yields:
        ("token", partial_text) for each token
        ("done", full_text) when complete
    """
    messages = build_witness_persona_prompt(
        state, witness, exam_type, session_messages, document_text
    )
    llm = get_llm(provider, max_output_tokens=2048)
    if not llm:
        yield ("done", "I... I'm sorry, could you repeat the question?")
        return
    yield from invoke_with_retry_streaming(llm, messages)


# ---- Coaching Analysis ------------------------------------------------------

def analyze_question_for_coaching(
    state: dict,
    question: str,
    exam_type: str,
    witness: dict,
    recent_messages: list,
) -> Optional[dict]:
    """Analyze an attorney's question and provide coaching feedback.

    Returns dict with coaching data, or None if no notable feedback.
    """
    ctx = get_case_context(state)
    w_name = witness.get("name", "the witness")
    w_type = witness.get("type", "Unknown")

    # Gather cross-exam plan for impeachment opportunities
    cross_plan_text = ""
    for entry in state.get("cross_examination_plan", []):
        if isinstance(entry, dict) and entry.get("witness", "").lower() == w_name.lower():
            for topic in entry.get("topics", [])[:5]:
                if isinstance(topic, dict):
                    cross_plan_text += f"\n- {topic.get('title', '')}: {topic.get('strategy_note', '')}"

    # Consistency check for impeachment opportunities
    consistency_text = ""
    for item in state.get("consistency_check", []):
        if isinstance(item, dict):
            fact = item.get("fact", "")
            if w_name.lower() in fact.lower():
                consistency_text += f"\n- {fact} (Source A: {item.get('source_a', '')}, Source B: {item.get('source_b', '')})"

    # Recent exchange context
    recent = recent_messages[-6:] if len(recent_messages) > 6 else recent_messages
    exchange_ctx = "\n".join(
        f"{'ATTORNEY' if m['role'] == 'attorney' else 'WITNESS'}: {m['content'][:200]}"
        for m in recent if m.get("role") in ("attorney", "witness")
    )

    prompt = f"""You are an expert trial advocacy coach evaluating an attorney's examination question.

EXAMINATION TYPE: {"Cross-Examination" if exam_type == "cross" else "Direct Examination"}
WITNESS: {w_name} ({w_type})
CASE TYPE: {ctx['case_type_desc']}

THE ATTORNEY'S QUESTION:
"{question}"

RECENT EXCHANGE CONTEXT:
{exchange_ctx}

{f"PREPARED CROSS-EXAM TOPICS (unused = missed opportunities):{cross_plan_text}" if cross_plan_text else ""}
{f"KNOWN INCONSISTENCIES IN WITNESS TESTIMONY:{consistency_text}" if consistency_text else ""}

EVALUATE the question and respond with ONLY valid JSON:
{{
    "has_feedback": true/false,
    "objectionable": true/false,
    "objection_basis": "Leading on direct" | "Compound question" | "Argumentative" | "Assumes facts not in evidence" | "Calls for speculation" | "Asked and answered" | "Calls for narrative" | null,
    "technique_tips": ["tip1", "tip2"],
    "impeachment_opportunity": "description of missed impeachment, with source reference" | null,
    "door_warning": "warning about what this question opens the door to" | null,
    "severity": "info" | "warning" | "critical"
}}

RULES:
- On cross-examination: Leading questions are GOOD (expected technique). Don't flag them.
- On direct examination: Leading questions ARE objectionable. Flag them.
- Only flag genuine issues — don't nitpick every question.
- "has_feedback" should be false if the question is fine and there's nothing noteworthy.
- Compound questions (two questions in one) are always problematic.
- If the attorney is missing an obvious impeachment opportunity based on the prepared cross-exam plan, note it.
- Be concise in tips — one sentence each.
"""

    llm = get_llm(state.get("current_model"), max_output_tokens=1024)
    if not llm:
        return None

    try:
        response = invoke_with_retry(llm, [
            SystemMessage(content="You are a trial advocacy coaching assistant. Respond only with valid JSON."),
            HumanMessage(content=prompt),
        ])
        result = extract_json(response.content if hasattr(response, "content") else str(response))
        if result and isinstance(result, dict) and result.get("has_feedback"):
            return result
    except Exception as e:
        logger.warning("Coaching analysis failed: %s", e)

    return None


# ---- Opposing Counsel Objections -------------------------------------------

def generate_objection(
    state: dict,
    question: str,
    exam_type: str,
    witness: dict,
    opponent_label: str,
) -> dict:
    """Generate a realistic opposing counsel objection (or no objection).

    Returns dict with {objects, basis, ruling_suggestion, explanation}.
    """
    ctx = get_case_context(state)
    w_name = witness.get("name", "the witness")

    prompt = f"""You are {opponent_label}'s attorney in a {ctx['case_type_desc']} case.
The opposing attorney just asked {w_name} the following question during {"cross-examination" if exam_type == "cross" else "direct examination"}:

QUESTION: "{question}"

Should you object? Consider:
- Is this a proper question for this type of examination?
- On cross-exam: Leading questions ARE allowed. Most questions are fine.
- On direct: Leading questions are objectionable. Open-ended questions are proper.
- Common objection bases: relevance, hearsay, leading (direct only), compound, argumentative, assumes facts not in evidence, calls for speculation, narrative, beyond scope, asked and answered, lack of foundation.
- NOT every question deserves an objection. Good trial lawyers only object strategically.
- Object maybe 10-20% of the time on direct exam, and only 5-10% on cross exam.

Respond with ONLY valid JSON:
{{
    "objects": true/false,
    "basis": "Objection, [basis]" | null,
    "ruling_suggestion": "sustained" | "overruled",
    "explanation": "Brief explanation of why the objection is/isn't valid"
}}
"""

    llm = get_llm(state.get("current_model"), max_output_tokens=512)
    if not llm:
        return {"objects": False, "basis": None, "ruling_suggestion": "overruled", "explanation": ""}

    try:
        response = invoke_with_retry(llm, [
            SystemMessage(content="You are an experienced trial attorney. Respond only with valid JSON."),
            HumanMessage(content=prompt),
        ])
        result = extract_json(response.content if hasattr(response, "content") else str(response))
        if result and isinstance(result, dict):
            return result
    except Exception as e:
        logger.warning("Objection generation failed: %s", e)

    return {"objects": False, "basis": None, "ruling_suggestion": "overruled", "explanation": ""}


# ---- Post-Session Scorecard ------------------------------------------------

def generate_scorecard(
    state: dict,
    session_messages: list,
    coaching_notes: list,
    exam_type: str,
    witness: dict,
) -> dict:
    """Generate a comprehensive post-session scorecard.

    Returns dict with overall_score, categories, missed_opportunities,
    suggested_question_sequences, and summary.
    """
    ctx = get_case_context(state)
    w_name = witness.get("name", "the witness")
    w_type = witness.get("type", "Unknown")

    # Build transcript
    transcript_lines = []
    for msg in session_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")[:500]
        if role == "attorney":
            transcript_lines.append(f"Q: {content}")
        elif role == "witness":
            transcript_lines.append(f"A: {content}")
        elif role == "objection":
            transcript_lines.append(f"[OBJECTION: {content}]")
    transcript = "\n".join(transcript_lines)

    # Build coaching summary
    coaching_summary = ""
    if coaching_notes:
        coaching_summary = "\n".join(
            f"- [{n.get('severity', 'info').upper()}] {n.get('content', '')[:200]}"
            for n in coaching_notes[:20]
        )

    # Build cross-exam plan reference (what was planned vs what was asked)
    planned_topics = []
    for entry in state.get("cross_examination_plan", []):
        if isinstance(entry, dict) and entry.get("witness", "").lower() == w_name.lower():
            for topic in entry.get("topics", []):
                if isinstance(topic, dict):
                    planned_topics.append(topic.get("title", ""))

    prompt = f"""You are an expert trial advocacy instructor scoring a mock examination session.

EXAMINATION TYPE: {"Cross-Examination" if exam_type == "cross" else "Direct Examination"}
WITNESS: {w_name} ({w_type})
CASE TYPE: {ctx['case_type_desc']}
TOTAL QUESTIONS ASKED: {sum(1 for m in session_messages if m.get('role') == 'attorney')}

SESSION TRANSCRIPT:
{transcript[:6000]}

{f"COACHING NOTES FROM SESSION:{chr(10)}{coaching_summary}" if coaching_summary else ""}
{f"PLANNED EXAMINATION TOPICS: {', '.join(planned_topics)}" if planned_topics else ""}

Score this examination session. Respond with ONLY valid JSON:
{{
    "overall_score": 0-100,
    "categories": {{
        "question_technique": {{
            "score": 0-100,
            "notes": "Assessment of question form, sequencing, and control",
            "highlights": ["Q#: specific example of good/bad technique"]
        }},
        "impeachment_effectiveness": {{
            "score": 0-100,
            "notes": "How well the attorney exploited contradictions and weaknesses",
            "missed_opportunities": [
                {{"description": "what was missed", "suggested_question": "better question to ask", "source": "document reference if applicable"}}
            ]
        }},
        "evidence_usage": {{
            "score": 0-100,
            "notes": "How well the attorney referenced and used case documents"
        }},
        "objection_avoidance": {{
            "score": 0-100,
            "notes": "How many questions were objectionable, and how well the attorney adapted"
        }},
        "narrative_control": {{
            "score": 0-100,
            "notes": "How well the attorney controlled the witness and maintained case narrative"
        }}
    }},
    "suggested_question_sequences": [
        {{
            "topic": "Topic the attorney should have covered or could improve",
            "questions": ["Question 1", "Question 2", "Question 3"],
            "rationale": "Why this sequence is effective"
        }}
    ],
    "summary": "2-3 sentence overall assessment with key takeaway"
}}

SCORING GUIDELINES:
- 90-100: Expert level — outstanding technique, thorough coverage
- 75-89: Proficient — solid work with minor areas for improvement
- 60-74: Developing — adequate but significant gaps or technique issues
- Below 60: Needs work — fundamental technique issues or major gaps
- For {"cross" if exam_type == "cross" else "direct"}-examination, weight {"leading question form, impeachment sequences, and witness control" if exam_type == "cross" else "open-ended questions, narrative flow, and foundation laying"} most heavily.
"""

    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return _default_scorecard()

    try:
        response = invoke_with_retry(llm, [
            SystemMessage(content="You are an expert trial advocacy scoring system. Respond only with valid JSON."),
            HumanMessage(content=prompt),
        ])
        result = extract_json(response.content if hasattr(response, "content") else str(response))
        if result and isinstance(result, dict) and "overall_score" in result:
            return result
    except Exception as e:
        logger.error("Scorecard generation failed: %s", e)

    return _default_scorecard()


def _default_scorecard() -> dict:
    """Fallback scorecard if LLM generation fails."""
    return {
        "overall_score": 0,
        "categories": {
            "question_technique": {"score": 0, "notes": "Unable to generate score."},
            "impeachment_effectiveness": {"score": 0, "notes": "Unable to generate score."},
            "evidence_usage": {"score": 0, "notes": "Unable to generate score."},
            "objection_avoidance": {"score": 0, "notes": "Unable to generate score."},
            "narrative_control": {"score": 0, "notes": "Unable to generate score."},
        },
        "suggested_question_sequences": [],
        "summary": "Scorecard generation failed. Please try ending the session again.",
    }


# ---- Document / Inconsistency Helpers --------------------------------------

def _gather_witness_document_text(
    case_id: str,
    witness_name: str,
    state: dict,
) -> str:
    """Search OCR cache and raw docs for passages mentioning this witness.

    Returns concatenated text capped at MAX_DOC_TEXT_CHARS.
    """
    from core.config import CONFIG
    data_dir = CONFIG.get("storage", {}).get("data_dir", "data")
    case_dir = os.path.join(data_dir, "cases", case_id)

    text_parts = []

    # Try OCRCache search
    try:
        from core.ingest import OCRCache
        cache = OCRCache(case_dir)
        results = cache.search(witness_name, max_snippets_per_file=3, context_chars=200)
        for r in results:
            fname = r.get("filename", "")
            for snippet in r.get("snippets", []):
                text_parts.append(f"[{fname}]: ...{snippet.get('text', '')}...")
    except Exception as e:
        logger.debug("OCRCache search failed for %s: %s", witness_name, e)

    # Also pull from raw_documents in state
    raw_docs = state.get("raw_documents", [])
    for doc in raw_docs:
        content = ""
        if hasattr(doc, "page_content"):
            content = doc.page_content
        elif isinstance(doc, dict):
            content = doc.get("page_content", doc.get("text", ""))
        if witness_name.lower() in content.lower():
            # Extract a window around the mention
            idx = content.lower().find(witness_name.lower())
            start = max(0, idx - 200)
            end = min(len(content), idx + 300)
            source = ""
            if hasattr(doc, "metadata"):
                source = doc.metadata.get("source", "")
            elif isinstance(doc, dict):
                source = doc.get("metadata", {}).get("source", "")
            text_parts.append(f"[{source}]: ...{content[start:end]}...")

    combined = "\n\n".join(text_parts)
    return combined[:MAX_DOC_TEXT_CHARS]


def _format_witness_inconsistencies(state: dict, witness_name: str) -> str:
    """Extract inconsistencies from consistency_check that mention this witness."""
    items = state.get("consistency_check", [])
    if not items:
        return ""

    relevant = []
    name_lower = witness_name.lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        fact = item.get("fact", "")
        source_a = item.get("source_a", "")
        source_b = item.get("source_b", "")
        notes = item.get("notes", "")
        combined = f"{fact} {source_a} {source_b} {notes}".lower()
        if name_lower in combined:
            relevant.append(
                f"- {fact}\n  Source A: {source_a}\n  Source B: {source_b}"
                + (f"\n  Notes: {notes}" if notes else "")
            )

    return "\n".join(relevant) if relevant else ""


# ---- Session Helpers --------------------------------------------------------

def create_session_id() -> str:
    """Generate a short unique session ID."""
    return uuid.uuid4().hex[:12]


def create_initial_session_data(
    session_id: str,
    witness_name: str,
    witness_type: str,
    exam_type: str,
    opposing_counsel_mode: bool,
) -> dict:
    """Create the initial session data structure."""
    return {
        "session_id": session_id,
        "witness_name": witness_name,
        "witness_type": witness_type,
        "exam_type": exam_type,
        "opposing_counsel_mode": opposing_counsel_mode,
        "messages": [
            {
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "role": "system",
                "content": (
                    f"Mock {'cross' if exam_type == 'cross' else 'direct'}-examination session started. "
                    f"You are examining {witness_name} ({witness_type} witness)."
                    + (" Opposing counsel is active and may object." if opposing_counsel_mode else "")
                ),
                "timestamp": datetime.now().isoformat(),
            }
        ],
        "coaching_notes": [],
        "scorecard": None,
    }


def create_session_index_entry(
    session_id: str,
    witness_name: str,
    witness_type: str,
    exam_type: str,
    opposing_counsel_mode: bool,
) -> dict:
    """Create the index entry for mock_exam_sessions.json."""
    return {
        "id": session_id,
        "witness_name": witness_name,
        "witness_type": witness_type,
        "exam_type": exam_type,
        "opposing_counsel_mode": opposing_counsel_mode,
        "created_at": datetime.now().isoformat(),
        "ended_at": None,
        "message_count": 0,
        "status": "active",
        "scorecard_summary": None,
    }
