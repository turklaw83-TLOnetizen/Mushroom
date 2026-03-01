# --- Sub-module of core.nodes ---------------------------------------------------
import logging

from core.nodes._common import *
from core.ingest import DocumentIngester

logger = logging.getLogger(__name__)


def analyze_case(state: AgentState):
    """
    Node 1: Analyzes the raw documents to extract charges/claims and key facts.
    """
    logger.info("--- Analyzing Case ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"case_summary": "Error: API Key missing."}
    ctx = get_case_context(state)

    # Context handling with source attribution
    if state.get("max_context_mode"):
        context_text = format_docs_with_sources(state["raw_documents"])
    else:
        context_text = format_docs_with_sources(state["raw_documents"], max_docs=50)

    prompt = f"""
    You are an {ctx['role']}.
    Analyze the following case documents ({ctx['doc_types']}).

    {ctx['analyze_instruction']}

    {CITATION_INSTRUCTION}

    CASE DOCUMENTS:
    {context_text}
    """

    response = invoke_with_retry(llm, [SystemMessage(content=f"You are a helpful legal assistant.{ctx['directives_block']}{ctx.get('module_notes_block', '')}"), HumanMessage(content=prompt)])
    return {"case_summary": response.content}


def extract_entities(state: AgentState):
    """
    Node 11: Extracts People, Places, Dates, and Organizations.
    """
    logger.info("--- Extracting Entities ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"entities": []}

    # Context handling with source attribution
    if state.get("max_context_mode"):
        context_text = format_docs_with_sources(state["raw_documents"])
    else:
        context_text = format_docs_with_sources(state["raw_documents"], max_docs=50)

    prompt = f"""
    1. Extract all important ENTITIES from the case documents (People, Places, Organizations).
    2. Extract KEY RELATIONSHIPS between them (e.g., "Officer Smith" arrested "John Doe", "Gun" found at "Main St").

    {CITATION_INSTRUCTION}

    Format as JSON with two lists:
    {{
      "entities": [{{ "id": "Officer Smith", "type": "PERSON", "context": "Arresting Officer", "source_ref": "[[source: report.pdf, p.1]]" }}],
      "relationships": [{{ "source": "Officer Smith", "target": "John Doe", "relation": "Arrested", "source_ref": "[[source: report.pdf, p.2]]" }}]
    }}

    CASE DOCUMENTS:
    {context_text}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    content = response.content

    # Parsing
    entities = []
    relationships = []
    data = extract_json(content)
    if isinstance(data, dict):
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])
    else:
        logger.warning("Entity JSON parsing failed -- no valid JSON found in response")

    return {"entities": entities, "relationships": relationships}


def develop_strategy(state: AgentState):
    """
    Node 2: Develops a strategy AND classifies witnesses.
    """
    logger.info("--- Developing Strategy ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"strategy_notes": "Error: API Key missing.", "witnesses": []}
    ctx = get_case_context(state)

    prompt = f"""
    Based on the case summary, develop a preliminary hearing defense strategy.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}
    CRITICAL STEP: Identify and classify ALL potential witnesses.
    For each witness, determine if they are likely:
    - "State": Prosecution witness (Hostile).
    - "Defense": Defense witness (Friendly).
    - "Swing": Could be either.

    ALSO: Extract any CONTACT INFORMATION (Phone, Email, Address, or "Unknown").

    {CITATION_INSTRUCTION}

    Provide the output as JSON for the witnesses section, and markdown for strategy.

    Format:
    STRATEGY:
    [Your strategy notes here -- cite sources for each key factual claim]

    WITNESSES:
    [
      {{"name": "Officer Jones", "type": "State", "goal": "Impeach on timeline", "contact_info": "555-0199"}},
      {{"name": "Jane Doe", "type": "Defense", "goal": "Establish alibi", "contact_info": "Unknown"}}
    ]

    CASE SUMMARY:
    {state['case_summary']}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    content = response.content

    # Naive parsing for the prototype (Production would use structured output parser)

    witnesses = []
    strategy = content

    try:
        # Extract JSON block
        json_match = re.search(r"\[\s*\{.*?\}\s*\]", content, re.DOTALL)
        if json_match:
            witnesses = json.loads(json_match.group(0))
            # Remove the JSON from strategy text for cleanliness
            strategy = content.replace(json_match.group(0), "").replace("WITNESSES:", "")
    except Exception as e:
        logger.warning(f"Error parsing witnesses: {e}")
        # Fallback: empty list, Agent will just generate general questions

    return {"strategy_notes": strategy, "witnesses": witnesses, "witness_contacts": witnesses}


def refine_strategy(state, instruction: str, chat_history: list):
    """
    Standalone function: Refines the current strategy based on attorney instructions.
    Returns updated strategy_notes and appended chat_history.
    """
    logger.info(f"--- Refining Strategy: {instruction[:60]}... ---")
    llm = get_llm(state.get("current_model"))
    if not llm:
        return {"strategy_notes": state.get("strategy_notes", ""), "strategy_chat_history": chat_history}

    current_strategy = state.get("strategy_notes", "")
    case_summary = state.get("case_summary", "")
    charges = state.get("charges", [])

    # Build message history for multi-turn context
    messages = [
        SystemMessage(content=f"""You are a {get_case_context(state)['strategy_role']}. You are refining a litigation strategy based on the attorney's instructions.

CURRENT STRATEGY:
{current_strategy}

CASE SUMMARY:
{case_summary}

{get_case_context(state)['claims_label'].upper()}:
{charges}

RULES:
- Rewrite the ENTIRE strategy, incorporating the attorney's instruction.
- Maintain the same markdown format as the original strategy.
- Keep everything from the original that the attorney did NOT ask to change.
- Be specific and actionable.
- After the updated strategy, add a brief "Changes Made" section summarizing what you changed and why.""")
    ]

    # Add conversation history for multi-turn
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(SystemMessage(content=msg["content"]))

    # Add current instruction
    messages.append(HumanMessage(content=instruction))

    response = invoke_with_retry(llm, messages)
    updated_strategy = response.content

    # Build a short summary of what changed for the chat display

    changes_section = ""
    changes_match = re.search(r"(?:Changes Made|## Changes|### Changes).*", updated_strategy, re.DOTALL | re.IGNORECASE)
    if changes_match:
        changes_section = changes_match.group(0)

    # Update chat history
    new_history = chat_history + [
        {"role": "user", "content": instruction},
        {"role": "assistant", "content": changes_section if changes_section else "Strategy updated based on your instructions."}
    ]

    return {"strategy_notes": updated_strategy, "strategy_chat_history": new_history}


def generate_timeline(state: AgentState):
    """
    Node 5: Generates a chronological timeline of events.
    """
    logger.info("--- Generating Timeline ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"timeline": []}

    ctx = get_case_context(state)
    prompt = f"""
    Based on the case documents, create a chronological timeline of ALL relevant events.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}
    Extract specific dates and times.

    {CITATION_INSTRUCTION}

    Format as JSON list:
    [{{ "year": 2023, "month": 1, "day": 15, "time": "14:00", "headline": "Defendant seen at bar", "text": "Witness Statement A claims defendant ordered a beer...", "source": "[[source: Witness_Statement_A.pdf, p.3]]" }}]

    Sort by date/time.

    CASE SUMMARY:
    {state['case_summary']}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    content = response.content

    timeline_data = []
    try:

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            timeline_data = json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Timeline JSON parsing failed: {e}")

    return {"timeline": timeline_data}


def generate_devils_advocate(state: AgentState):
    """
    Node 6: Critiques the defense strategy (Prosecution perspective).
    """
    logger.info("--- Generating Devil's Advocate ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"devils_advocate_notes": "Error: API Key missing."}

    ctx = get_case_context(state)
    prompt = f"""
    {ctx['devil_role']}
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}
    1. Anticipate their arguments.
    2. Explain how you would counter them.
    3. Point out gaps in their evidence.

    {CITATION_INSTRUCTION}

    STRATEGY TO CRITIQUE:
    {state['strategy_notes']}

    CASE SUMMARY:
    {state['case_summary']}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    return {"devils_advocate_notes": response.content}


def generate_evidence_foundations(state: AgentState):
    """
    Node 7: Analyzes physical/documentary evidence for admissibility.
    """
    logger.info("--- Generating Evidence Foundations ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=16384)
    if not llm: return {"evidence_foundations": []}

    # Filter docs: prioritize evidence-relevant tagged documents
    _file_tags = state.get("_file_tags", {})
    _filtered_docs = filter_docs_by_relevance(
        state['raw_documents'], "foundations_agent", _file_tags,
    )
    if state.get("max_context_mode"):
        raw_docs_text = format_docs_with_sources(_filtered_docs)
    else:
        raw_docs_text = format_docs_with_sources(_filtered_docs, max_chars=10000)

    ctx = get_case_context(state)
    prompt = f'''You are a seasoned trial attorney conducting an exhaustive evidence audit.
{ctx['directives_block']}{ctx.get('module_notes_block', '')}
Identify ALL potential PHYSICAL and DOCUMENTARY exhibits mentioned in the case materials.
Be EXHAUSTIVE — list every piece of physical evidence, every document, every digital item,
every photo, every recording, every lab report, every receipt mentioned anywhere in the case.

For EACH individual item, provide:
1. "item": Specific name/description of the item
2. "admissibility": The exact legal predicate questions/steps to ADMIT it (Friendly approach).
3. "attack": The specific objections or chain-of-custody attacks to SUPPRESS it (Hostile approach).
4. "source_ref": Citation to the source document

You should identify at least 5-10 exhibits from typical case materials.
Return one JSON object PER exhibit — do NOT consolidate multiple items into a single entry.

{CITATION_INSTRUCTION}

CRITICAL: Return ONLY valid JSON. No markdown fences, no commentary.

Format as a JSON list:
[
  {{ "item": "Body-worn camera footage from Officer Smith", "admissibility": "Authenticate through Officer Smith testimony, establish recording was in normal course of duty, foundation under FRE 901(a)", "attack": "Challenge completeness — was camera turned off/on during encounter? Request full unedited footage. Argue prejudicial impact under FRE 403", "source_ref": "[[source: Police_Report.pdf, p.2]]" }},
  {{ "item": "Toxicology report dated 01/15/2026", "admissibility": "Introduce through lab technician, establish chain of custody from blood draw to lab, certify under FRE 902(11)", "attack": "Challenge chain of custody at collection point, question calibration of testing equipment, Confrontation Clause if technician unavailable", "source_ref": "[[source: Lab_Results.pdf, p.1]]" }},
  {{ "item": "Defendant's cell phone records", "admissibility": "Authenticate through custodian of records affidavit from carrier, business records exception FRE 803(6)", "attack": "Challenge whether records show defendant personally used the phone, privacy/4th Amendment if obtained without warrant", "source_ref": "[[source: Discovery_Response.pdf, p.5]]" }}
]

CASE SUMMARY:
{state['case_summary']}

CASE DOCUMENTS:
{raw_docs_text}
'''

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        return {"evidence_foundations": parsed}
    # Fallback: wrap raw text so downstream always gets a list
    return {"evidence_foundations": [{"item": "See raw analysis", "admissibility": response.content, "attack": "", "_raw": True}]}


def generate_elements_map(state: AgentState):
    """
    Node 9: Maps evidence to legal elements of the offense.
    """
    logger.info("--- Mapping Legal Elements ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"legal_elements": []}

    charges = state.get("charges", [])

    legal_context = "" # Initialize

    # Check if charges is a list of dicts (New Format)
    if isinstance(charges, list) and len(charges) > 0 and isinstance(charges[0], dict):
        legal_context = "Analyze the evidence against the following SPECIFIC CHARGES:\n"
        for i, c in enumerate(charges):
            # Using simple concatenation to avoid f-string complexity issues
            legal_context += f"--- CHARGE {i+1} ---\n"
            legal_context += f"OFFENSE: {c.get('name', 'Unknown')}\n"
            legal_context += f"STATUTE #: {c.get('statute_number', 'N/A')}\n"
            legal_context += f"SEVERITY: {c.get('level', '')} {c.get('class', '')}\n\n"
            legal_context += f"STATUTE DEFINITION:\n{c.get('statute_text', 'N/A')}\n\n"
            legal_context += f"JURY INSTRUCTIONS:\n{c.get('jury_instructions', 'N/A')}\n"
            legal_context += "--------------------------------------------------\n"

    else:
        # Fallback for legacy state
        legal_context = "(No specific charges defined. Infer potential charges from facts.)"

    # Use triple single quotes to avoid conflicts with double quotes in JSON
    ctx = get_case_context(state)
    prompt = f'''
    Analyze the case evidence against the specific LEGAL ELEMENTS of the provided {ctx['claims_label']}.
    The standard of proof is: {ctx['burden']}.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}

    {legal_context}

    For EACH element of EACH charge:
    1. Identify the element.
    2. List specific evidence supporting it.
    3. Grade the case strength for {ctx['opponent']} (High/Medium/Low).

    {CITATION_INSTRUCTION}

    Format as JSON list:
    [{{ "charge": "Assault 2", "element": "Intent to cause injury", "evidence": "Threatening texts [[source: texts.pdf, p.3]]", "strength": "High" }}]

    CASE SUMMARY:
    {state['case_summary']}
    '''

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        return {"legal_elements": parsed}
    # Fallback: wrap raw text so downstream always gets a list
    return {"legal_elements": [{"charge": "See raw analysis", "element": response.content, "evidence": "", "strength": "", "_raw": True}]}


def generate_investigation_plan(state: AgentState):
    """
    Node 10: Generates an investigation to-do list.
    """
    logger.info("--- Planning Investigation ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"investigation_plan": []}

    # Gather context
    ctx = get_case_context(state)
    strategy = state.get('strategy_notes', 'No strategy defined.')
    elements = state.get('legal_elements', [])
    conflicts = state.get('consistency_check', [])

    prompt = f'''
    Act as a Lead Detective for the Defense.
    Create a TARGETED Investigation Plan to win this case.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}

    {CITATION_INSTRUCTION}

    DEFENSE STRATEGY:
    {strategy}

    LEGAL WEAKNESSES (Elements):
    {str(elements)[:5000]}

    FACTUAL CONFLICTS:
    {str(conflicts)[:5000]}

    CASE SUMMARY:
    {state['case_summary']}

    INSTRUCTIONS:
    1. Suggest actions that strictly support the Strategy (e.g. if Alibi, find visuals of location).
    2. Suggest actions to exploit the Weaknesses identified.
    3. Suggest actions to resolve the Conflicts (e.g. pull phone records to fix timeline).
    4. Ignore generic steps unless critical.

    Format as JSON list:
    [{{ "action": "Subpoena 7-11 Surveillance", "reason": "Corroborate Alibi (Strategy) [[source: alibi_witness.pdf, p.1]]", "priority": "High" }}]
    '''

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        return {"investigation_plan": parsed}
    # Fallback: wrap raw text so downstream always gets a list
    return {"investigation_plan": [{"action": "See raw analysis", "reason": response.content, "priority": "Medium", "_raw": True}]}


def generate_voir_dire(state: AgentState):
    """
    Node 12: Generates Voir Dire (Jury Selection) strategy.
    """
    logger.info("--- Generating Voir Dire ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"voir_dire": {}}

    ctx = get_case_context(state)
    strategy = state.get('strategy_notes', 'No strategy defined.')
    case_summary = state.get('case_summary', '')
    charges = state.get('charges', [])

    prompt = f"""
    You are a Jury Consultant.
    Develop a Voir Dire strategy for this case.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}

    DEFENSE STRATEGY:
    {strategy}

    CASE SUMMARY:
    {case_summary}

    CHARGES:
    {str(charges)}

    {CITATION_INSTRUCTION}

    TASKS:
    1. Define the IDEAL JUROR (Demographics, beliefs, experiences).
    2. Define RED FLAGS (Jurors to strike).
    3. Draft 5-10 Open-Ended Voir Dire questions to reveal bias.

    Format as JSON:
    {{
      "ideal_juror": "...",
      "red_flags": "...",
      "questions": [
        {{ "question": "...", "goal": "Reveal bias against..." }},
        {{ "question": "...", "goal": "..." }}
      ]
    }}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    parsed = extract_json(response.content)
    if isinstance(parsed, dict):
        return {"voir_dire": parsed}
    # Fallback: wrap raw text so downstream always gets a dict
    return {"voir_dire": {"ideal_juror": response.content, "red_flags": "", "questions": [], "_raw": True}}


def generate_mock_jury(state: AgentState):
    """
    Simulates a focus group of diverse jurors voting on the current case strategy.
    """
    llm = get_llm(state.get("current_model"))
    if not llm: return {"mock_jury_feedback": []}

    ctx = get_case_context(state)
    strategy = state.get('strategy_notes', 'No strategy defined.')
    case_summary = state.get('case_summary', '')

    prompt = f"""
    You are a Focus Group Moderator simulating a diverse jury.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}

    CASE SUMMARY:
    {case_summary}

    DEFENSE STRATEGY:
    {strategy}

    TASK:
    Simulate 5 distinct jurors reacting to this strategy.

    JUROR PERSONAS:
    1. The Skeptic (Logical, needs hard proof)
    2. The Emotional (Empathetic, focuses on victims/defendants)
    3. The Authoritarian (Respects law & order, trusts police)
    4. The Wildcard (Unpredictable, focuses on odd details)
    5. The Foreperson (tries to build consensus)

    For EACH juror, provide:
    - Verdict (Guilty/Not Guilty/Undecided)
    - Reaction (1-2 sentences on why)

    Format as JSON list:
    [
      {{ "juror": "The Skeptic", "verdict": "Not Guilty", "reaction": "The evidence is too circumstantial." }},
      ...
    ]
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    content = response.content

    feedback = []
    try:

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            feedback = json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Mock jury JSON parsing failed: {e}")

    return {"mock_jury_feedback": feedback}


def generate_consistency_check(state: AgentState):
    """
    Node 8: Checks for factual inconsistencies across documents using RAG.
    """
    logger.info("--- Checking Consistency (RAG) ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"consistency_check": []}

    # RAG Retrieval
    # We search for terms likely to reveal conflicts
    query = "inconsistent statement contradiction difference in time location alibi versus"

    # Get case_id from somewhere? State doesn't have it.
    # Workaround: We can't easily get case_id here without passing it in state.
    # Assumption: The vector store is named "case_{case_id}".
    # But wait, 'analyze_case' doesn't know the ID.
    # We need to add 'case_id' to AgentState.

    # FALLBACK for now: existing logic if case_id missing, but we should add case_id to state in app.py
    # Let's assume state has 'case_id'.
    case_id = state.get("case_id")
    context_text = ""

    if case_id:
        try:
            ingester = DocumentIngester()
            vectorstore = ingester.get_vector_store(case_id)
            # Fetch top 20 chunks related to conflict
            results = vectorstore.similarity_search(query, k=20)
            context_text = format_docs_with_sources(results)
            logger.info(f"RAG: Retrieved {len(results)} chunks for consistency check.")
        except Exception as e:
            logger.warning(f"RAG Error: {e}")
            _file_tags = state.get("_file_tags", {})
            _filtered_docs = filter_docs_by_relevance(
                state['raw_documents'], "consistency_checker", _file_tags,
            )
            context_text = format_docs_with_sources(_filtered_docs, max_chars=10000)
    else:
        _file_tags = state.get("_file_tags", {})
        _filtered_docs = filter_docs_by_relevance(
            state['raw_documents'], "consistency_checker", _file_tags,
        )
        context_text = format_docs_with_sources(_filtered_docs, max_chars=10000)

    ctx = get_case_context(state)
    prompt = f'''
    You are an expert impartial investigator.
    {ctx['directives_block']}{ctx.get('module_notes_block', '')}
    Review the provided Evidence Snippets (retrieved via search for contradictions).
    Identify FACTUAL CONTRADICTIONS or INCONSISTENCIES (e.g., mismatched times, descriptions, sequences).

    {CITATION_INSTRUCTION}

    Format as JSON list:
    [{{ "fact": "Car Color", "source_a": "[[source: WitnessA.pdf, p.2]] Witness A: Red", "source_b": "[[source: OfficerB.pdf, p.1]] Officer B: Blue", "notes": "Major discrepancy" }}]

    CASE SUMMARY:
    {state['case_summary']}

    EVIDENCE SNIPPETS:
    {context_text}
    '''

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        return {"consistency_check": parsed}
    # Fallback: wrap raw text so downstream always gets a list
    return {"consistency_check": [{"fact": "See raw analysis", "source_a": response.content, "source_b": "", "notes": "", "_raw": True}]}
