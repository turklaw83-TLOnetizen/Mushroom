# ---- Sub-module of core.nodes ------------------------------------------------
import logging

from core.nodes._common import *

logger = logging.getLogger(__name__)

def generate_cross_questions(state: AgentState):
    """
    Node 3: Generates Cross-Examination questions for witnesses.
    Calls the LLM ONCE PER WITNESS to guarantee thorough coverage of every witness.
    Supports per-witness selection via cross_exam_witnesses state field.
    """
    logger.info("--- Generating Cross-Exam ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=16384)
    if not llm: return {"cross_examination_plan": []}

    all_witnesses = state.get("witnesses", [])

    # Support per-witness selection
    selected_names = state.get("cross_exam_witnesses", None)
    if selected_names and isinstance(selected_names, list):
        # User explicitly selected witnesses — respect their choice regardless of type
        targets = [w for w in all_witnesses if isinstance(w, dict) and
                   w.get("name", w.get("witness", "")) in selected_names]
    else:
        # Default: only cross-examine opposing/neutral witnesses (State, Swing, Unknown)
        # Defense witnesses get direct examination, not cross
        targets = [w for w in all_witnesses if isinstance(w, dict) and
                   w.get("type", w.get("role", "Unknown")).lower() not in ("defense",)]

    if not targets:
        # If no witnesses identified, generate a generic outline
        targets = [{"name": "General Prosecution Witness", "type": "State"}]

    ctx = get_case_context(state)
    strategy = state.get('strategy_notes', '')
    case_summary = state.get('case_summary', '')

    # ── Generate per-witness individually ──
    all_cross_data = []

    for wit_idx, witness in enumerate(targets):
        w_name = witness.get("name", witness.get("witness", "")).strip()
        w_type = witness.get("type", witness.get("role", "Unknown"))
        w_desc = witness.get("description", witness.get("testimony", ""))

        # Assign label for unnamed witnesses
        if not w_name or w_name.lower() in ("unknown", "unnamed", "n/a", ""):
            if "victim" in w_type.lower() or "complainant" in w_type.lower():
                w_name = f"Unnamed Victim #{wit_idx + 1}"
            else:
                w_name = f"Unnamed Witness #{wit_idx + 1}"

        logger.info(f"  --> Cross-exam for witness {wit_idx + 1}/{len(targets)}: {w_name}")

        prompt = f"""You are a SEASONED TRIAL ATTORNEY preparing cross-examination.

Generate a THOROUGH, COMPREHENSIVE cross-examination outline for this ONE witness:

WITNESS: {w_name}
TYPE: {w_type}
KNOWN TESTIMONY/ROLE: {w_desc}

{ctx['directives_block']}

INSTRUCTIONS:
- Organize by TOPIC areas (e.g., "Credibility & Bias", "Timeline Inconsistencies",
  "Perception & Memory", "Prior Inconsistent Statements", "Chain of Custody", etc.)
- Use LEADING questions (Yes/No format) — this is cross-examination
- Be THOROUGH — include every question needed to fully explore each topic
- For each question provide the strategic RATIONALE
- Cite specific case documents/pages wherever possible
- Sequence questions to build toward impeachment points
- Establish favorable facts BEFORE attacking credibility
- For each topic, include a brief STRATEGY NOTE explaining the overall goal

{CITATION_INSTRUCTION}

CRITICAL: Return ONLY valid JSON. No markdown fences, no commentary.

Return a JSON object for this witness:
{{
  "witness": "{w_name}",
  "type": "{w_type}",
  "topics": [
    {{
      "title": "Topic Name",
      "strategy_note": "Brief strategy for this line of questioning",
      "questions": [
        {{"question": "Leading question text?", "source": "[[source: Document.pdf, p.X]]", "rationale": "Why this question matters"}}
      ]
    }}
  ]
}}

DEFENSE STRATEGY:
{strategy}

CASE SUMMARY:
{case_summary}"""

        try:
            response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
            content = response.content

            # Parse JSON
            witness_data = None
            try:
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    witness_data = parsed
                elif isinstance(parsed, list) and len(parsed) > 0:
                    witness_data = parsed[0]
            except json.JSONDecodeError:

                match = re.search(r'\{[^{}]*"witness"[^{}]*"topics"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
                if match:
                    try:
                        witness_data = json.loads(match.group(0))
                    except Exception as e:
                        logger.warning(f"Cross-exam fallback JSON parse failed for {w_name}: {e}")

            if witness_data and isinstance(witness_data, dict):
                # Ensure witness name and type are set
                witness_data.setdefault("witness", w_name)
                witness_data.setdefault("type", w_type)
                all_cross_data.append(witness_data)
                logger.info(f"    [OK] Generated {len(witness_data.get('topics', []))} topics for {w_name}")
            else:
                # Fallback: store raw text for this witness
                all_cross_data.append({
                    "witness": w_name,
                    "type": w_type,
                    "topics": [{
                        "title": "Cross-Examination Notes",
                        "strategy_note": "Raw AI output — could not parse structured format",
                        "questions": [{"question": content[:2000], "source": "", "rationale": "Unparsed output"}]
                    }]
                })
        except Exception as e:
            logger.warning(f"    [ERR] Error generating for {w_name}: {e}")
            all_cross_data.append({
                "witness": w_name,
                "type": w_type,
                "topics": [{
                    "title": "Generation Error",
                    "strategy_note": f"Error: {str(e)[:200]}",
                    "questions": []
                }]
            })

    logger.info(f"--- Cross-Exam Complete: {len(all_cross_data)} witnesses ---")
    return {"cross_examination_plan": all_cross_data}


def generate_direct_questions(state: AgentState):
    """
    Node 4: Generates Direct-Examination questions for DEFENSE/SWING witnesses.
    Calls the LLM ONCE PER WITNESS to guarantee thorough coverage.
    """
    logger.info("--- Generating Direct-Exam ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=16384)
    if not llm: return {"direct_examination_plan": []}

    all_witnesses = state.get("witnesses", [])

    # Filter for friendly witnesses (Defense + Swing)
    targets = [w for w in all_witnesses if isinstance(w, dict) and
               w.get("type", w.get("role", "Unknown")) in ["Defense", "Swing"]]

    if not targets:
        return {"direct_examination_plan": "No defense witnesses identified."}

    ctx = get_case_context(state)
    strategy = state.get('strategy_notes', '')
    case_summary = state.get('case_summary', '')

    # ── Generate per-witness individually ──
    all_direct_data = []

    for wit_idx, witness in enumerate(targets):
        w_name = witness.get("name", witness.get("witness", "")).strip()
        w_type = witness.get("type", witness.get("role", "Unknown"))
        w_desc = witness.get("description", witness.get("testimony", ""))

        if not w_name or w_name.lower() in ("unknown", "unnamed", "n/a", ""):
            w_name = f"Unnamed Defense Witness #{wit_idx + 1}"

        logger.info(f"  --> Direct-exam for witness {wit_idx + 1}/{len(targets)}: {w_name}")

        prompt = f"""You are a SEASONED TRIAL ATTORNEY preparing direct examination.

Generate a THOROUGH, COMPREHENSIVE direct examination outline for this ONE witness:

WITNESS: {w_name}
TYPE: {w_type}
KNOWN TESTIMONY/ROLE: {w_desc}

{ctx['directives_block']}

INSTRUCTIONS:
- Structure the examination to tell a STORY organized by TOPIC
  (e.g., "Background & Credentials", "Relationship to Events", "The Incident",
  "Aftermath", "Character Evidence", etc.)
- Use OPEN-ENDED questions (Who, What, Where, When, Why, How, Describe, Explain)
  — this is direct examination, NOT cross
- For each question provide the GOAL (what testimony you're eliciting)
- Build a logical narrative arc — introduction, context, key events, impact
- Include foundational questions before introducing exhibits
- Anticipate and preemptively address weaknesses (front the bad facts)
- For each topic, include a brief STRATEGY NOTE explaining the overall goal

{CITATION_INSTRUCTION}

CRITICAL: Return ONLY valid JSON. No markdown fences, no commentary.

Return a JSON object for this witness:
{{
  "witness": "{w_name}",
  "type": "{w_type}",
  "topics": [
    {{
      "title": "Topic Name",
      "strategy_note": "Brief strategy for this line of questioning",
      "questions": [
        {{"question": "Open-ended question text?", "goal": "What testimony this elicits"}}
      ]
    }}
  ]
}}

{ctx['our_side'].upper()} STRATEGY:
{strategy}

CASE SUMMARY:
{case_summary}"""

        try:
            response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
            content = response.content

            # Parse JSON
            witness_data = None
            try:
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    witness_data = parsed
                elif isinstance(parsed, list) and len(parsed) > 0:
                    witness_data = parsed[0]
            except json.JSONDecodeError:
                match = re.search(r'\{[^{}]*"witness"[^{}]*"topics"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
                if match:
                    try:
                        witness_data = json.loads(match.group(0))
                    except Exception as e:
                        logger.warning(f"Direct-exam fallback JSON parse failed for {w_name}: {e}")

            if witness_data and isinstance(witness_data, dict):
                witness_data.setdefault("witness", w_name)
                witness_data.setdefault("type", w_type)
                all_direct_data.append(witness_data)
                logger.info(f"    [OK] Generated {len(witness_data.get('topics', []))} topics for {w_name}")
            else:
                all_direct_data.append({
                    "witness": w_name,
                    "type": w_type,
                    "topics": [{
                        "title": "Direct Examination Notes",
                        "strategy_note": "Raw AI output — could not parse structured format",
                        "questions": [{"question": content[:2000], "goal": "Unparsed output"}]
                    }]
                })
        except Exception as e:
            logger.warning(f"    [ERR] Error generating for {w_name}: {e}")
            all_direct_data.append({
                "witness": w_name,
                "type": w_type,
                "topics": [{
                    "title": "Generation Error",
                    "strategy_note": f"Error: {str(e)[:200]}",
                    "questions": []
                }]
            })

    logger.info(f"--- Direct-Exam Complete: {len(all_direct_data)} witnesses ---")
    return {"direct_examination_plan": all_direct_data}


def generate_witness_prep(state: dict, witness_name: str, witness_role: str = "", witness_goal: str = "") -> dict:
    """
    Generates mock opposing counsel cross-examination for a specific witness.
    Simulates aggressive, realistic questioning based on case facts.
    Returns: {"witness_prep": {"witness": str, "scenarios": list[dict], "coaching_notes": str}}
    """
    model = get_llm(state.get("current_model", "xai"))

    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "No strategy available.")
    evidence = state.get("evidence_foundations", [])
    conflicts = state.get("consistency_check", [])
    cross_exam = state.get("cross_examination_plan", [])

    # Build evidence context
    evidence_ctx = ""
    for e in evidence[:8]:
        if isinstance(e, dict):
            evidence_ctx += f"- {e.get('evidence', e.get('item', 'Unknown'))}: {e.get('foundation_type', e.get('admissibility', ''))}\n"

    # Build conflict context
    conflict_ctx = ""
    for c in conflicts[:5]:
        if isinstance(c, dict):
            conflict_ctx += f"- {c.get('issue', c.get('contradiction', 'Unknown'))}: {c.get('details', c.get('description', ''))}\n"

    prompt = f"""You are an EXPERIENCED OPPOSING COUNSEL preparing aggressive cross-examination
for the witness "{witness_name}" (Role: {witness_role or 'Not specified'}.
The defense's goal with this witness: {witness_goal or 'Not specified'}).

CASE CONTEXT:
{str(summary)[:2000]}

DEFENSE STRATEGY:
{str(strategy)[:1000]}

KEY EVIDENCE:
{evidence_ctx or 'None identified'}

KNOWN CONTRADICTIONS/WEAKNESSES:
{conflict_ctx or 'None identified'}

Generate a COMPREHENSIVE witness preparation package with these sections:

## SCENARIO 1: Credibility Attack
Generate 5-7 cross-examination questions designed to undermine this witness's credibility.
For each question, provide:
- The question (as opposing counsel would ask it)
- The TRAP (what opposing counsel is really trying to establish)
- COACHING NOTE (how the witness should handle this)

## SCENARIO 2: Fact Impeachment
Generate 5-7 questions targeting potential inconsistencies in this witness's testimony.
Same format: Question, Trap, Coaching Note.

## SCENARIO 3: Bias & Motive
Generate 4-5 questions designed to show the witness has bias or ulterior motives.
Same format: Question, Trap, Coaching Note.

## SCENARIO 4: Expert/Technical Challenge (if applicable)
Generate 3-4 questions challenging the witness's qualifications or methodology.
Same format: Question, Trap, Coaching Note.

## OVERALL COACHING NOTES
- Top 3 things this witness MUST remember on the stand
- Phrases to AVOID
- Body language tips
- Key documents the witness should review before testimony

Format your response in clean markdown. Be AGGRESSIVE and REALISTIC — this should genuinely prepare
the witness for a hostile cross-examination. Think like a seasoned trial lawyer who wants to win."""

    response = model.invoke([HumanMessage(content=prompt)])

    return {
        "witness_prep": {
            "witness": witness_name,
            "content": response.content,
            "role": witness_role,
            "goal": witness_goal,
        }
    }


# === Witness Interview Planner (standalone, not part of graph) ===


def generate_interview_plan(state: dict, witness_name: str, witness_role: str = "", interview_type: str = "initial") -> dict:
    """
    Generates a structured pre-trial interview prep sheet for the attorney's meeting with a witness.
    interview_type: 'initial', 'follow_up', or 'pre_testimony'
    Returns: {"interview_plan": {"witness": str, "type": str, "agenda": list, "questions": list,
              "documents": list, "landmines": list, "do_not_ask": list, "follow_ups": list, "content": str}}
    """
    logger.info(f"--- Generating Interview Plan for {witness_name} ({interview_type}) ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"interview_plan": {"witness": witness_name, "type": interview_type, "content": "Error: API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", [])
    conflicts = state.get("consistency_check", [])
    timeline = state.get("timeline", [])
    entities = state.get("entities", [])
    witnesses = state.get("witnesses", [])
    devils_advocate = state.get("devils_advocate_notes", "")
    case_files = state.get("case_files", [])

    # Build context strings
    evidence_ctx = ""
    for e in evidence[:10]:
        if isinstance(e, dict):
            evidence_ctx += f"- {e.get('evidence', e.get('item', 'Unknown'))}: {e.get('foundation_type', e.get('admissibility', ''))}\n"

    conflict_ctx = ""
    for c in conflicts[:8]:
        if isinstance(c, dict):
            conflict_ctx += f"- {c.get('issue', c.get('contradiction', 'Unknown'))}: {c.get('details', c.get('description', ''))}\n"

    timeline_ctx = ""
    for t in (timeline[:10] if isinstance(timeline, list) else []):
        if isinstance(t, dict):
            timeline_ctx += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    entity_ctx = ""
    for ent in (entities[:10] if isinstance(entities, list) else []):
        if isinstance(ent, dict):
            entity_ctx += f"- {ent.get('name', 'Unknown')} ({ent.get('type', 'Unknown')}): {ent.get('role', ent.get('description', ''))}\n"

    file_list = ""
    for f in case_files:
        fname = os.path.basename(f) if isinstance(f, str) else str(f)
        file_list += f"- {fname}\n"

    # Witness info from analysis
    witness_info = ""
    for w in witnesses:
        if isinstance(w, dict) and w.get("name", "").lower() == witness_name.lower():
            witness_info = f"Known info: Role={w.get('role','?')}, Type={w.get('type','?')}, Goal={w.get('goal','?')}, Notes={w.get('notes', w.get('key_testimony', ''))}"
            break

    devils_ctx = str(devils_advocate)[:1000] if devils_advocate else "None available"

    type_descriptions = {
        "initial": "This is the FIRST meeting with this witness. Focus on: building rapport, understanding their full story, identifying what they know and don't know, discovering new facts, and assessing credibility/reliability.",
        "follow_up": "This is a FOLLOW-UP meeting. Focus on: filling gaps from initial interview, verifying specific facts, addressing inconsistencies found since last meeting, preparing for specific case developments, and refining testimony.",
        "pre_testimony": "This is a PRE-TESTIMONY preparation session. Focus on: reviewing what they will testify about, preparing for cross-examination, reviewing key documents they'll be asked about, courtroom procedures and demeanor, and final fact-checking."
    }

    prompt = f"""You are an experienced {ctx['role']} preparing for a {interview_type.replace('_', ' ')} interview with witness "{witness_name}" (Role: {witness_role or 'Not specified'}).

{type_descriptions.get(interview_type, type_descriptions['initial'])}

CASE CONTEXT:
{str(summary)[:2000]}

{ctx['our_side'].upper()} STRATEGY:
{str(strategy)[:1500]}

KNOWN ABOUT THIS WITNESS:
{witness_info or 'No prior analysis — this may be a new witness.'}

KEY EVIDENCE/EXHIBITS:
{evidence_ctx or 'None identified'}

KNOWN CONTRADICTIONS/ISSUES:
{conflict_ctx or 'None identified'}

CASE TIMELINE:
{timeline_ctx or 'No timeline built yet'}

KEY ENTITIES/PEOPLE:
{entity_ctx or 'None extracted'}

CASE FILES:
{file_list or 'No files listed'}

DEVIL'S ADVOCATE CONCERNS:
{devils_ctx}

Generate a COMPREHENSIVE interview preparation package with these EXACT section headers:

## INTERVIEW AGENDA
Create a structured agenda with estimated time for each topic area. Include:
- Rapport building / intro (always first)
- Each major topic area to cover
- Document review portions
- Wrap-up and next steps
Format each item as: **[Time Est.]** Topic — Purpose

## KEY QUESTIONS
Organize questions by topic area. For each topic area, provide:
### [Topic Name]
- Question with [PURPOSE: why you're asking this]
Include at least 4-5 topic areas with 3-5 questions each.
Questions should be OPEN-ENDED for initial interviews, more FOCUSED for follow-ups and pre-testimony.

## DOCUMENTS TO BRING
List specific documents from the case files that should be reviewed during this interview.
For each: the document name, WHY it's relevant to this witness, and WHEN in the interview to introduce it.

## LANDMINE ALERTS
Based on known contradictions, devil's advocate concerns, and case weaknesses:
- Potential problem areas this witness might reveal
- Topics where their story might conflict with other evidence
- Sensitive areas to approach carefully
- Warning signs to watch for during the interview
Flag each as: HIGH RISK / MODERATE RISK / LOW RISK

## DO NOT ASK
Topics the attorney should AVOID asking about:
- Privilege-sensitive areas (attorney-client, work product)
- Questions that could open harmful doors at trial
- Topics that could create discoverable material you don't want
- Areas where the witness's answer could hurt your case
Explain WHY each topic should be avoided.

## FOLLOW-UP TASKS
After the interview, what should the attorney do:
- Documents/records to obtain
- Other witnesses to contact
- Investigations to pursue
- Items to verify independently
- Updates needed to case strategy

Format your entire response in clean markdown using the exact section headers above."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])
    content = response.content

    # Parse sections from the markdown headers
    sections_parsed = {}
    current_heading = None
    current_body = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                sections_parsed[current_heading] = "\n".join(current_body).strip()
            current_heading = stripped[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_heading is not None:
        sections_parsed[current_heading] = "\n".join(current_body).strip()

    return {
        "interview_plan": {
            "witness": witness_name,
            "role": witness_role,
            "type": interview_type,
            "content": content,
            "sections": sections_parsed,
        }
    }



def analyze_deposition(state, deposition_text):
    """
    Analyzes a deposition transcript against case documents to generate
    an impeachment table highlighting contradictions.
    """
    logger.info("--- Analyzing Deposition ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm: return {"deposition_analysis": "Error: API Key missing."}

    case_summary = state.get("case_summary", "No case summary.")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", "")

    ctx = get_case_context(state)
    prompt = f"""
    You are an {ctx['role']} conducting deposition analysis.

    TASK: Compare the deposition transcript below against the case documents and identify
    every contradiction, inconsistency, prior inconsistent statement, and impeachable moment.

    {CITATION_INSTRUCTION}

    CASE SUMMARY:
    {case_summary}

    {ctx['our_side'].upper()} STRATEGY:
    {strategy}

    EVIDENCE ON FILE:
    {str(evidence)[:5000]}

    DEPOSITION TRANSCRIPT:
    {deposition_text}

    OUTPUT FORMAT:

    ## Impeachment Table

    | # | Deposition Statement | Line/Page | Contradicting Evidence | Source Document | Impeachment Strategy |
    |---|---|---|---|---|---|
    | 1 | "I never saw the defendant" | p.12, L.5 | Officer report states witness identified defendant | [[source: Police_Report.pdf, p.3]] | Confront with prior ID |

    ## Key Takeaways
    - Bullet points summarizing the most impactful contradictions
    - Note any admissions that help {ctx['our_side']}
    - Note any areas where the witness was evasive or non-responsive

    ## Recommended Cross-Examination Strategy
    - Specific recommendations for using these contradictions at trial
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    return {"deposition_analysis": response.content}


def generate_deposition_outline(state: dict, witness_name: str, witness_role: str = "",
                                 topics: str = "") -> dict:
    """
    Generates a structured deposition outline for a specific witness.
    Includes topic areas, key questions, exhibit references, impeachment traps,
    and estimated duration per topic.
    Returns: {"deposition_outline": {"witness": str, "role": str, "topics": [...]}}
    """
    logger.info(f"--- Generating Deposition Outline for {witness_name} ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"deposition_outline": {"witness": witness_name, "role": witness_role, "topics": [], "error": "API Key missing."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    witnesses = state.get("witnesses", [])
    evidence = state.get("evidence_foundations", [])
    timeline = state.get("timeline", [])
    case_files = state.get("case_files", [])
    consistency = state.get("consistency_check", [])
    cross_exam = state.get("cross_examination_plan", [])

    witness_info = ""
    for w in (witnesses[:15] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            wname = w.get("name", "")
            if wname.lower() == witness_name.lower():
                witness_info = str(w)
            else:
                witness_info += f"- {wname}: {w.get('role', '')} ({w.get('alignment', '')})\n"

    file_list = "\n".join([f"- {os.path.basename(f)}" for f in case_files]) if case_files else "No files."

    timeline_str = ""
    for t in (timeline[:15] if isinstance(timeline, list) else []):
        if isinstance(t, dict):
            timeline_str += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    cross_str = ""
    for cx in (cross_exam[:20] if isinstance(cross_exam, list) else []):
        if isinstance(cx, dict):
            if witness_name.lower() in cx.get("witness", "").lower():
                cross_str += f"- {cx.get('question', cx.get('topic', ''))}\n"

    prompt = f"""You are an elite {ctx['role']} preparing a DEPOSITION OUTLINE for a witness.

WITNESS: {witness_name}
ROLE: {witness_role or 'Unknown'}
{"ATTORNEY-SPECIFIED TOPICS: " + topics if topics else ""}

CASE SUMMARY:
{str(summary)[:3000]}

{ctx['our_side'].upper()} STRATEGY:
{str(strategy)[:2000]}

WITNESS DETAILS:
{witness_info or 'No specific details available.'}

CASE FILES (potential exhibits to reference):
{file_list}

KEY TIMELINE:
{timeline_str or 'No timeline available.'}

EXISTING CROSS-EXAM QUESTIONS FOR THIS WITNESS:
{cross_str or 'None generated yet.'}

KNOWN CONTRADICTIONS:
{str(consistency)[:2000]}

EVIDENCE ANALYSIS:
{str(evidence)[:3000]}

Generate a COMPREHENSIVE deposition outline. Return a JSON object:
{{
    "witness": "{witness_name}",
    "role": "{witness_role}",
    "estimated_total_duration": "e.g., 2-3 hours",
    "opening_instructions": "How to begin the deposition (stipulations, ground rules)",
    "topics": [
        {{
            "topic_number": 1,
            "title": "Topic area name",
            "objective": "What you are trying to establish in this section",
            "estimated_minutes": 15,
            "questions": [
                {{
                    "question": "The actual question to ask",
                    "purpose": "Brief note on WHY (for attorney eyes only)",
                    "follow_up": "Anticipated follow-up if witness answers a certain way",
                    "exhibit_reference": "Exhibit or document to use (if any)",
                    "is_trap": false,
                    "trap_explanation": ""
                }}
            ],
            "impeachment_opportunities": ["Cross-ref to known contradictions or documents"],
            "documents_needed": ["List of exhibits to have ready for this topic"]
        }}
    ],
    "closing_questions": ["Standard closing questions (corrections, additions, read-and-sign)"],
    "key_documents_to_bring": ["Complete list of documents the attorney should bring"],
    "strategic_notes": "Overall deposition strategy notes"
}}

RULES:
- Organize topics from least threatening to most threatening (build up)
- Include 5-8 topic areas with 4-8 questions each
- Mark trap questions clearly
- Reference specific case documents/exhibits where relevant
- Include must-ask closing-the-door questions that prevent the witness from changing their story later
- For {ctx['opponent']}'s witnesses, focus on locking in favorable testimony and exposing weaknesses
- For {ctx['our_side']}'s witnesses, focus on preserving helpful testimony

Return ONLY the JSON object, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        outline = json.loads(content)
    except (json.JSONDecodeError, Exception):
        outline = {
            "witness": witness_name,
            "role": witness_role,
            "topics": [],
            "raw_output": response.content,
            "_parse_error": True
        }

    return {"deposition_outline": outline}


# === AI Document Comparison / Inconsistency Finder ===
