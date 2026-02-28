# ─── Sub-module of core.nodes ──────────────────────────────────
import logging

logger = logging.getLogger(__name__)

from core.nodes._common import *

def generate_cross_reference_matrix(state: dict) -> dict:
    """
    Analyzes relationships between all case documents.
    Returns matrix showing which documents support, contradict, or are neutral to each other.
    """
    logger.info("--- Generating Cross-Reference Matrix ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"cross_reference_matrix": []}

    raw_docs = state.get("raw_documents", [])
    if not raw_docs:
        return {"cross_reference_matrix": []}

    # Group document content by source file
    doc_groups = {}
    for d in raw_docs:
        source = d.metadata.get("source", "Unknown") if hasattr(d, 'metadata') else "Unknown"
        content = d.page_content if hasattr(d, 'page_content') else str(d)
        if source not in doc_groups:
            doc_groups[source] = ""
        doc_groups[source] += content[:2000] + "\n"

    sources = list(doc_groups.keys())
    if len(sources) < 2:
        return {"cross_reference_matrix": [{"doc_a": sources[0] if sources else "N/A", "doc_b": "N/A", "relationship": "only_document", "details": "Only one document available.", "key_facts": "", "strength": "n/a"}]}

    doc_summaries = ""
    for src, content in doc_groups.items():
        doc_summaries += f"\n=== DOCUMENT: {src} ===\n{content[:3000]}\n"

    ctx = get_case_context(state)
    prompt = f"""You are a meticulous {ctx['role']} performing document cross-referencing.

TASK: Analyze relationships between ALL pairs of case documents.

DOCUMENTS:
{doc_summaries}

For EVERY unique pair, produce a JSON entry:
{{
    "doc_a": "filename A",
    "doc_b": "filename B",
    "relationship": "supports" | "contradicts" | "neutral" | "supplements",
    "strength": "strong" | "moderate" | "weak",
    "details": "How/why these documents relate",
    "key_facts": "Specific facts or statements that connect or conflict"
}}

Rules:
- "supports": Documents corroborate each other's facts
- "contradicts": Documents contain conflicting facts/dates/statements
- "supplements": One adds new info that extends the other
- "neutral": Unrelated aspects with no meaningful connection
- Flag contradictions that could be exploited by {ctx['opponent']}
- There should be {len(sources) * (len(sources) - 1) // 2} pairs total

Return ONLY the JSON array, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        matrix = json.loads(content)
    except (json.JSONDecodeError, Exception):
        matrix = [{"doc_a": "Parse Error", "doc_b": "", "relationship": "error", "details": response.content[:500], "key_facts": "", "strength": "n/a"}]

    return {"cross_reference_matrix": matrix}


# === Voice-to-Brief Processor ===


def process_voice_note(state: dict, transcript: str) -> dict:
    """
    Processes a voice recording transcript and extracts structured legal brief.
    """
    logger.info("--- Processing Voice Note ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=4096)
    if not model:
        return {"voice_brief": {"error": "API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No case analysis yet.")
    investigation = state.get("investigation_plan", [])

    inv_str = ""
    for item in (investigation[:10] if isinstance(investigation, list) else []):
        if isinstance(item, dict):
            inv_str += f"- {item.get('task', item.get('description', str(item)))}\n"

    prompt = f"""You are a {ctx['role']}'s legal assistant processing a voice recording transcript.

Extract ALL actionable information. The recording may be a courtroom note, client meeting,
witness interview, attorney dictation, or phone call.

CASE CONTEXT:
{str(summary)[:2000]}

CURRENT INVESTIGATION PLAN:
{inv_str or 'No investigation plan yet.'}

TRANSCRIPT:
{transcript}

Return a JSON object:
{{
    "recording_type": "courtroom_note | client_meeting | witness_interview | dictation | phone_call | other",
    "summary": "2-3 sentence summary",
    "action_items": [
        {{"task": "What needs to be done", "priority": "high | medium | low", "deadline": "If mentioned, otherwise null", "assigned_to": "If mentioned"}}
    ],
    "new_facts": [
        {{"fact": "New information", "source": "Who said it", "significance": "Why it matters"}}
    ],
    "key_quotes": [
        {{"quote": "Exact or near-exact quote", "speaker": "Who said it", "significance": "Why it matters"}}
    ],
    "client_instructions": ["Things the client wants or instructions given"],
    "agreed_terms": ["Agreements, stipulations, or terms discussed"],
    "follow_up_questions": ["Questions raised that need answers"],
    "suggested_updates": "Suggest updates to the case analysis based on this recording"
}}

Return ONLY the JSON object, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        brief = json.loads(content)
    except (json.JSONDecodeError, Exception):
        brief = {"raw_output": response.content, "parse_error": True}

    brief["transcript"] = transcript
    return {"voice_brief": brief}


# === Exhibit Preparation Wizard ===


def generate_exhibit_plan(state: dict) -> dict:
    """
    Generates a comprehensive exhibit plan with strategic ordering,
    AI descriptions, and foundation scripts (Q&A) for each exhibit.
    """
    logger.info("--- Generating Exhibit Plan ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"exhibit_plan": []}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", [])
    elements = state.get("legal_elements", [])
    witnesses = state.get("witnesses", [])
    case_files = state.get("case_files", [])

    file_list = ""
    for i, f in enumerate(case_files):
        fname = os.path.basename(f) if isinstance(f, str) else str(f)
        file_list += f"{i+1}. {fname}\n"

    evidence_str = str(evidence)[:4000] if evidence else "No evidence analysis available."
    elements_str = str(elements)[:3000] if elements else "No elements mapped."

    witness_str = ""
    for w in (witnesses[:10] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            witness_str += f"- {w.get('name', 'Unknown')} ({w.get('role', 'Unknown')})\n"

    prompt = f"""You are a senior {ctx['role']} preparing an exhibit plan for {ctx['case_type_desc']} proceedings.

TASK: Create a comprehensive exhibit plan. For each case file determine:
1. Whether it should be an exhibit
2. The strategic ORDER for presentation
3. A proper legal DESCRIPTION
4. The FOUNDATION SCRIPT — exact Q&A to lay foundation and admit the exhibit

CASE FILES:
{file_list or 'No files listed.'}

CASE SUMMARY:
{str(summary)[:3000]}

STRATEGY:
{str(strategy)[:2000]}

EVIDENCE ANALYSIS:
{evidence_str}

LEGAL ELEMENTS:
{elements_str}

WITNESSES:
{witness_str or 'No witnesses identified.'}

Return a JSON array in recommended presentation ORDER:
[
    {{
        "number": 1,
        "file": "original_filename.pdf",
        "description": "Proper legal description, e.g., 'Incident report by Officer J. Smith, dated 01/15/2025'",
        "type": "documentary | physical | demonstrative | testimonial",
        "sponsoring_witness": "Name of witness who can authenticate this",
        "foundation_script": "Q: I'm showing you what's been marked as Exhibit 1. Do you recognize this?\\nA: [Expected]\\nQ: What is it?\\nA: [Expected]\\nQ: How are you familiar with it?\\nA: [Expected]\\n...",
        "strategic_notes": "Why this exhibit matters and when to introduce it",
        "order_rationale": "Why it should be in this position",
        "anticipated_objections": "Likely objections and how to overcome them"
    }}
]

RULES:
- Order exhibits STRATEGICALLY (chronological, by witness, or by theme)
- Foundation scripts must include EXACT questions for authentication
- For business records, include custodian foundation
- For photos/video, include identification and relevance foundation
- Include anticipated objections (hearsay, relevance, authentication)
- If a file shouldn't be an exhibit, still include it with a note explaining why

Return ONLY the JSON array, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        plan = json.loads(content)
    except (json.JSONDecodeError, Exception):
        plan = [{"number": 1, "file": "Parse Error", "description": response.content[:500], "type": "error", "foundation_script": "", "strategic_notes": "", "order_rationale": "", "anticipated_objections": "", "sponsoring_witness": ""}]

    return {"exhibit_plan": plan}


# === Advanced Audio/Video Forensic Analysis ===


def generate_exhibit_list(state: dict, bates_data: dict = None) -> dict:
    """
    Generates a court-ready exhibit list with AI descriptions, authentication notes,
    anticipated objections, and sponsoring witness for each exhibit.
    Integrates with Bates stamp data when available.
    Returns: {"exhibit_list": [{"exhibit_number": str, ...}]}
    """
    logger.info("--- Generating Exhibit List ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"exhibit_list": []}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", [])
    witnesses = state.get("witnesses", [])
    case_files = state.get("case_files", [])
    elements = state.get("legal_elements", [])

    file_info = ""
    for i, f in enumerate(case_files):
        fname = os.path.basename(f) if isinstance(f, str) else str(f)
        bates_entry = bates_data.get(fname, {}) if bates_data else {}
        bates_str = ""
        if bates_entry:
            bates_str = f" | Bates: {bates_entry.get('range_str', 'N/A')} | Exhibit: {bates_entry.get('exhibit', 'N/A')}"
        file_info += f"{i+1}. {fname}{bates_str}\n"

    witness_str = ""
    for w in (witnesses[:10] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            witness_str += f"- {w.get('name', 'Unknown')} ({w.get('role', 'Unknown')})\n"

    prompt = f"""You are a senior {ctx['role']} preparing a TRIAL EXHIBIT LIST for court filing.

CASE FILES:
{file_info or 'No files listed.'}

CASE SUMMARY:
{str(summary)[:3000]}

STRATEGY:
{str(strategy)[:2000]}

EVIDENCE ANALYSIS:
{str(evidence)[:3000]}

WITNESSES:
{witness_str or 'No witnesses identified.'}

LEGAL ELEMENTS:
{str(elements)[:2000]}

Generate a COURT-READY exhibit list. Return a JSON array:
[
    {{
        "exhibit_number": "A",
        "file": "original_filename.pdf",
        "bates_range": "DEF-000001 to DEF-000005",
        "description": "Formal legal description suitable for court filing",
        "document_type": "Police Report | Medical Record | Photograph | Business Record | Contract | Correspondence | Video Recording | Audio Recording | Government Record | Expert Report | Other",
        "authentication_method": "How this can be authenticated (cite FRE rules)",
        "sponsoring_witness": "Name of the witness who will sponsor this exhibit",
        "anticipated_objections": [
            {{
                "objection": "The likely objection",
                "response": "How to overcome it"
            }}
        ],
        "relevance": "What this exhibit proves and which element it goes to",
        "offer_timing": "When in your case-in-chief to introduce this"
    }}
]

RULES:
- Use proper legal descriptions, NOT just filenames
- Include specific rule references for authentication (FRE 901, 902, 803, etc.)
- Anticipate the TOP 1-2 most likely objections per exhibit
- Order exhibits sequentially as they would appear in a standard exhibit list
- If Bates numbers are provided, include them; if not, leave bates_range empty
- Mark any exhibit that may require a motion in limine for pre-admission

Return ONLY the JSON array, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        exhibit_list = json.loads(content)
    except (json.JSONDecodeError, Exception):
        exhibit_list = [{"exhibit_number": "Error", "file": "Parse Error", "description": response.content[:500]}]

    return {"exhibit_list": exhibit_list}


# === Conflict Check / Adverse Party Scanner ===
# Now delegates to ethical_compliance.py for smart matching (fuzzy, nicknames, initials)


def scan_conflicts(current_case_id: str, all_entities: dict,
                   prospective_clients: list = None) -> dict:
    """
    Scans for conflicts of interest by comparing entities across cases.
    Enhanced: fuzzy matching, nickname detection, initial matching,
    and prospective client screening (RPC 1.18).

    Thin wrapper around ethical_compliance.scan_conflicts_smart().
    """
    from core.ethical_compliance import scan_conflicts_smart
    return scan_conflicts_smart(current_case_id, all_entities,
                                prospective_clients=prospective_clients)


# === AI Opponent Playbook Predictor ===


def predict_opponent_strategy(state: dict) -> dict:
    """
    Analyzes the case from opposing counsel's perspective.
    Returns a structured playbook predicting the opponent's likely strategy,
    motions, witness order, evidence themes, and weak points.
    """
    logger.info("--- Predicting Opponent Strategy ---")
    llm = get_llm(state.get("current_model"))
    if not llm:
        return {"opponent_playbook": {"error": "API Key missing."}}

    ctx = get_case_context(state)

    case_summary = state.get("case_summary", "No case summary available.")
    evidence = state.get("evidence_analysis", "")
    strategy = state.get("strategy_notes", "")
    entities = state.get("entities", [])
    devils_advocate = state.get("devils_advocate_notes", "")

    # Build entity summary
    entity_summary = ""
    if entities and isinstance(entities, list):
        people = [e for e in entities if isinstance(e, dict) and e.get("type", "").upper() in ("PERSON", "PEOPLE")]
        orgs = [e for e in entities if isinstance(e, dict) and e.get("type", "").upper() in ("ORGANIZATION", "COMPANY", "ORG")]
        if people:
            entity_summary += "KEY PEOPLE: " + ", ".join(e.get("id", e.get("name", "")) for e in people[:15]) + "\n"
        if orgs:
            entity_summary += "KEY ORGANIZATIONS: " + ", ".join(e.get("id", e.get("name", "")) for e in orgs[:10]) + "\n"

    prompt = f"""You are an elite {ctx['opponent']} strategist — a legal mastermind hired to WIN against {ctx['our_side']}.

Your job is to analyze this case from {ctx['opponent']}'s perspective and build their most likely playbook.

CASE TYPE: {ctx['case_type_desc']}
PREPARATION: {ctx.get('prep_label', 'Trial')}

CASE SUMMARY:
{str(case_summary)[:3000]}

{f"EVIDENCE ANALYSIS:{chr(10)}{str(evidence)[:2000]}" if evidence else ""}

{f"KNOWN ENTITIES:{chr(10)}{entity_summary}" if entity_summary else ""}

{f"DEFENSE STRATEGY (what opposing counsel would see):{chr(10)}{str(strategy)[:1500]}" if strategy else ""}

{f"KNOWN WEAKNESSES:{chr(10)}{str(devils_advocate)[:1500]}" if devils_advocate else ""}

Respond with a comprehensive opponent playbook using EXACTLY this structure (use the headers verbatim):

## THEORY OF THE CASE
What narrative will {ctx['opponent']} build? What story will they tell the jury/judge?

## ANTICIPATED MOTIONS
List specific motions {ctx['opponent']} is likely to file, with timing and purpose.
Format each as: **Motion Name** — Purpose and likely timing

## PROBABLE WITNESS ORDER
Who will {ctx['opponent']} call and in what order? What will each witness establish?
Format each as: **Witness Name/Role** — What they will testify about

## EVIDENCE THEMES
What evidence themes will {ctx['opponent']} emphasize? How will they frame the physical/documentary evidence?

## WEAK POINTS THEY WILL TARGET
What are the specific vulnerabilities in {ctx['our_side']}'s position that {ctx['opponent']} will exploit?

## RECOMMENDED COUNTER-STRATEGIES
For each predicted move above, suggest a specific counter-tactic for {ctx['our_side']}.
Format each as: **Their Move** → **Your Counter**

## OVERALL THREAT ASSESSMENT
Rate the strength of {ctx['opponent']}'s likely approach on a scale of 1-10 and explain the rating.
Identify the single most dangerous element of their strategy.
"""

    try:
        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        raw = response.content if response else ""
    except Exception as e:
        return {"opponent_playbook": {"error": f"LLM call failed: {str(e)}"}}

    # Parse the structured response into sections
    playbook = {"raw": raw, "sections": []}
    section_headers = [
        "THEORY OF THE CASE",
        "ANTICIPATED MOTIONS",
        "PROBABLE WITNESS ORDER",
        "EVIDENCE THEMES",
        "WEAK POINTS THEY WILL TARGET",
        "RECOMMENDED COUNTER-STRATEGIES",
        "OVERALL THREAT ASSESSMENT",
    ]

    for i, header in enumerate(section_headers):
        pattern = re.compile(r"##\s*" + re.escape(header) + r"\s*\n(.*?)(?=##\s*[A-Z]|\Z)", re.DOTALL | re.IGNORECASE)
        match = pattern.search(raw)
        if match:
            content = match.group(1).strip()
            playbook["sections"].append({
                "title": header,
                "content": content,
                "icon": ["target", "clipboard", "people", "search", "warning", "shield", "chart"][i] if i < 7 else "pin",
            })

    return {"opponent_playbook": playbook}


# === Case Theory Builder / Evaluator ===


def evaluate_case_theory(state: dict, theory_text: str) -> dict:
    """
    Evaluates an attorney's case theory against all available evidence.
    Returns a structured scorecard with strength ratings, supporting/undermining
    evidence, gaps, and alternative theories the opponent might argue.
    """
    logger.info("--- Evaluating Case Theory ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"case_theory": {"error": "API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", [])
    witnesses = state.get("witnesses", [])
    elements = state.get("legal_elements", [])
    timeline = state.get("timeline", [])
    consistency = state.get("consistency_check", [])
    devils = state.get("devils_advocate_notes", "")

    witness_str = ""
    for w in (witnesses[:15] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            witness_str += f"- {w.get('name', '?')} ({w.get('role', '?')}, {w.get('alignment', '?')})\n"

    timeline_str = ""
    for t in (timeline[:20] if isinstance(timeline, list) else []):
        if isinstance(t, dict):
            timeline_str += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    prompt = f"""You are a senior {ctx['role']} and case theory consultant.

The attorney has proposed the following CASE THEORY — a narrative that explains
what happened and why the jury/judge should rule in {ctx['our_side']}'s favor.

## PROPOSED CASE THEORY
{theory_text}

## CASE CONTEXT
{str(summary)[:3000]}

## STRATEGY NOTES
{str(strategy)[:2000]}

## EVIDENCE FOUNDATIONS
{str(evidence)[:3000]}

## WITNESSES
{witness_str or 'None identified yet.'}

## LEGAL ELEMENTS
{str(elements)[:2000]}

## TIMELINE
{timeline_str or 'Not generated yet.'}

## KNOWN CONTRADICTIONS
{str(consistency)[:1500]}

## KNOWN WEAKNESSES (Devil's Advocate)
{str(devils)[:1500]}

Evaluate this case theory RIGOROUSLY. Return a JSON object:
{{
    "overall_score": 75,
    "grade": "B",
    "verdict": "Promising theory with gaps that need addressing",
    "strengths": [
        {{
            "point": "What is strong about this theory",
            "supporting_evidence": ["List of specific evidence that supports this point"],
            "confidence": "high | moderate"
        }}
    ],
    "weaknesses": [
        {{
            "point": "What is weak or vulnerable in this theory",
            "risk_level": "critical | significant | minor",
            "undermining_evidence": ["Specific evidence or facts that undermine this point"],
            "mitigation": "How the attorney could address this weakness"
        }}
    ],
    "evidence_gaps": [
        {{
            "gap": "Evidence or facts the theory needs but doesn't have",
            "importance": "essential | helpful | nice_to_have",
            "how_to_fill": "Investigative steps to obtain this evidence"
        }}
    ],
    "opponent_counter_theories": [
        {{
            "theory": "An alternative narrative the opponent might argue",
            "plausibility": "high | moderate | low",
            "rebuttal": "How to counter this alternative theory"
        }}
    ],
    "jury_appeal": {{
        "emotional_resonance": "high | moderate | low",
        "simplicity": "high | moderate | low",
        "credibility": "high | moderate | low",
        "notes": "Assessment of how well this theory will play with a jury"
    }},
    "recommendations": ["Top 3-5 specific actions to strengthen this theory"]
}}

RULES:
- Score honestly from 0-100 (don't inflate)
- Grade: A (85+), B (70-84), C (55-69), D (40-54), F (<40)
- Be specific about which evidence supports or undermines each point
- Focus on practical, actionable recommendations
- Consider how {ctx['opponent']} will attack this theory
- Return ONLY the JSON, no markdown fences"""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        theory_eval = json.loads(content)
    except (json.JSONDecodeError, Exception):
        theory_eval = {
            "overall_score": 0,
            "grade": "?",
            "verdict": "Could not parse evaluation.",
            "raw_output": response.content[:3000],
            "_parse_error": True
        }

    theory_eval["theory_text"] = theory_text
    return {"case_theory": theory_eval}


# === Jury Instruction Generator ===


def generate_jury_instructions(state: dict) -> dict:
    """
    Generates draft jury instructions based on charges/claims, case type,
    and jurisdiction. Returns standard, special, and contested instructions.
    """
    logger.info("--- Generating Jury Instructions ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"jury_instructions": {"error": "API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    charges = state.get("charges", [])
    elements = state.get("legal_elements", [])
    strategy = state.get("strategy_notes", "")

    charges_str = ""
    for c in (charges if isinstance(charges, list) else []):
        if isinstance(c, dict):
            charges_str += f"- {c.get('charge', c.get('claim', c.get('name', str(c))))}\n"
        else:
            charges_str += f"- {c}\n"

    elements_str = ""
    for e in (elements[:20] if isinstance(elements, list) else []):
        if isinstance(e, dict):
            elements_str += f"- {e.get('element', e.get('name', str(e)))}: {e.get('status', '')}\n"
        else:
            elements_str += f"- {e}\n"

    prompt = f"""You are an expert {ctx['role']} preparing JURY INSTRUCTIONS for trial.

CASE TYPE: {ctx['case_type_desc']}
BURDEN OF PROOF: {ctx['burden']}

CASE SUMMARY:
{str(summary)[:3000]}

{ctx['claims_label'].upper()}:
{charges_str or 'Not yet identified.'}

LEGAL ELEMENTS:
{elements_str or 'Not yet mapped.'}

STRATEGY:
{str(strategy)[:2000]}

Generate a COMPREHENSIVE set of jury instructions. Return a JSON object:
{{
    "standard_instructions": [
        {{
            "number": 1,
            "title": "Instruction title (e.g., 'Duty of the Jury')",
            "category": "preliminary | substantive | evidentiary | procedural | closing",
            "text": "Full text of the instruction as it would be read to the jury",
            "source": "Pattern instruction source or rule reference",
            "notes": "Attorney notes on why this instruction matters"
        }}
    ],
    "special_instructions": [
        {{
            "number": "S-1",
            "title": "Special instruction title",
            "text": "Full text of the proposed special instruction",
            "justification": "Legal basis for requesting this special instruction",
            "strategic_value": "How this instruction helps {ctx['our_side']}"
        }}
    ],
    "contested_instructions": [
        {{
            "title": "Instruction that {ctx['opponent']} will likely request",
            "text": "Likely text they will propose",
            "our_objection": "Grounds for objecting to this instruction",
            "alternative": "Our proposed alternative language if the instruction is appropriate"
        }}
    ],
    "verdict_forms": [
        {{
            "form_number": 1,
            "title": "Verdict form title",
            "text": "Full text of the proposed verdict form",
            "lesser_included": false,
            "notes": "Strategic considerations for this verdict form"
        }}
    ],
    "instruction_conference_strategy": "Overall strategy for the instruction conference — what to fight for, what to concede"
}}

RULES:
- Include 8-15 standard instructions covering all phases (preliminary, substantive, evidentiary, closing)
- Include 2-4 special instructions that favor {ctx['our_side']}
- Anticipate 2-3 contested instructions from {ctx['opponent']}
- Provide complete verdict forms including any lesser-included offenses
- Use language from standard pattern instructions where appropriate
- For {ctx['case_type_desc']} cases, tailor instructions to the specific burden and legal framework
- Return ONLY the JSON, no markdown fences"""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        instructions = json.loads(content)
    except (json.JSONDecodeError, Exception):
        instructions = {
            "standard_instructions": [],
            "special_instructions": [],
            "contested_instructions": [],
            "verdict_forms": [],
            "raw_output": response.content[:3000],
            "_parse_error": True
        }

    return {"jury_instructions": instructions}



def evaluate_missing_discovery(state: dict) -> dict:
    """
    Analyzes all case materials and identifies discovery / evidence that
    appears to be missing.  Categories:
      1) Definitely exists  — referenced in current docs but not produced
      2) Probably exists     — highly likely given the case type / facts
      3) Should exist        — standard discovery for this type of case
      4) Might exist         — speculative but worth requesting

    Also generates a draft discovery request letter to opposing counsel.
    """
    logger.info("--- Evaluating Missing Discovery ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"missing_discovery": {"error": "API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    evidence = state.get("evidence_foundations", [])
    witnesses = state.get("witnesses", [])
    elements = state.get("legal_elements", [])
    timeline = state.get("timeline", [])
    case_type = state.get("case_type", "criminal")
    raw_docs = state.get("raw_documents", [])

    # Build a description of what documents we DO have
    doc_descriptions = ""
    if isinstance(raw_docs, list):
        for i, doc in enumerate(raw_docs[:30]):
            if isinstance(doc, dict):
                src = doc.get("metadata", {}).get("source", "Unknown")
                snippet = str(doc.get("page_content", ""))[:200]
                doc_descriptions += f"  Doc {i+1}: {src}\n    Snippet: {snippet}\n"
            elif hasattr(doc, 'metadata'):
                src = doc.metadata.get("source", "Unknown")
                snippet = str(doc.page_content)[:200]
                doc_descriptions += f"  Doc {i+1}: {src}\n    Snippet: {snippet}\n"

    # Witness context
    witness_str = ""
    for w in (witnesses[:15] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            witness_str += f"- {w.get('name', '?')} ({w.get('role', '?')}, {w.get('alignment', '?')})\n"

    # Build evidence context
    evidence_str = ""
    if isinstance(evidence, list):
        for e in evidence[:20]:
            if isinstance(e, dict):
                evidence_str += f"- {e.get('exhibit', e.get('name', '?'))}: {e.get('description', '')[:100]}\n"
            elif isinstance(e, str):
                evidence_str += f"- {e[:100]}\n"
    elif isinstance(evidence, str):
        evidence_str = evidence[:2000]

    # Timeline context
    timeline_str = ""
    for t in (timeline[:20] if isinstance(timeline, list) else []):
        if isinstance(t, dict):
            timeline_str += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    prompt = f"""You are a senior {ctx['role']} and discovery specialist preparing for {ctx['prep_label']}.

## YOUR TASK
Analyze all available case materials and identify discovery / evidence that
appears to be MISSING from {ctx['opponent']}'s production or that has not yet
been obtained. Think like an experienced litigator who knows what documents
and evidence SHOULD be in a case file for this type of matter.

## CASE SUMMARY
{str(summary)[:3000]}

## CASE TYPE
{ctx['case_type_desc']}

## DOCUMENTS ON FILE
{doc_descriptions or 'No document metadata available.'}

## EVIDENCE ALREADY IDENTIFIED
{evidence_str or 'None cataloged yet.'}

## WITNESSES
{witness_str or 'None identified.'}

## LEGAL ELEMENTS
{str(elements)[:2000]}

## TIMELINE
{timeline_str or 'Not generated.'}

Produce a JSON object with this structure:
{{
    "definitely_exists": [
        {{
            "item": "Description of the missing item",
            "basis": "Why we KNOW this exists (e.g. referenced in Officer Smith's report p.3)",
            "importance": "critical | important | helpful",
            "discovery_type": "document | physical_evidence | recording | digital | testimony | report"
        }}
    ],
    "probably_exists": [
        {{
            "item": "Description",
            "basis": "Why this probably exists given the facts",
            "importance": "critical | important | helpful",
            "discovery_type": "document | physical_evidence | recording | digital | testimony | report"
        }}
    ],
    "should_exist": [
        {{
            "item": "Description",
            "basis": "Why this is standard for this case type",
            "importance": "critical | important | helpful",
            "discovery_type": "document | physical_evidence | recording | digital | testimony | report"
        }}
    ],
    "might_exist": [
        {{
            "item": "Description",
            "basis": "Why this COULD exist and would be valuable",
            "importance": "critical | important | helpful",
            "discovery_type": "document | physical_evidence | recording | digital | testimony | report"
        }}
    ],
    "draft_letter": "A professional discovery request letter/email addressed to opposing counsel requesting the items above. Include specific references. Use a firm but professional tone. Format as a complete letter ready to send.",
    "total_items": 0,
    "summary": "Brief executive summary of the discovery gaps found"
}}

RULES:
- Be thorough — think about body camera footage, 911 calls, dispatch logs,
  lab results, chain of custody docs, personnel files, training records,
  digital evidence, surveillance footage, medical records, financial records,
  phone records, emails, text messages, social media, prior complaints, etc.
- For {ctx['case_type_desc']} cases, focus on discovery that {ctx['opponent']}
  is obligated to produce (Brady material for criminal, mandatory disclosures for civil)
- Mark items as "critical" if they could change the outcome of the case
- In the draft letter, be specific about each category of items requested
- Include a polite but firm reminder about {ctx['opponent']}'s disclosure obligations
- "total_items" should be the sum of items across all four categories
- Return ONLY the JSON, no markdown fences"""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        missing = json.loads(content)
    except (json.JSONDecodeError, Exception):
        missing = {
            "definitely_exists": [],
            "probably_exists": [],
            "should_exist": [],
            "might_exist": [],
            "draft_letter": "",
            "total_items": 0,
            "summary": "Could not parse evaluation.",
            "raw_output": response.content[:3000],
            "_parse_error": True
        }

    # Compute total if model didn't
    if not missing.get("total_items"):
        missing["total_items"] = (
            len(missing.get("definitely_exists", [])) +
            len(missing.get("probably_exists", [])) +
            len(missing.get("should_exist", [])) +
            len(missing.get("might_exist", []))
        )

    return {"missing_discovery": missing}
