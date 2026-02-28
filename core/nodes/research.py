# ---- Sub-module of core.nodes ------------------------------------------------
import logging

try:
    from langchain_community.tools import DuckDuckGoSearchRun
except ImportError:
    DuckDuckGoSearchRun = None

from core.nodes._common import *

logger = logging.getLogger(__name__)

def generate_draft_document(state: AgentState, doc_type: str, specific_context: str = ""):
    """
    Generates a legal document based on case state and user request.
    NOT a node in the main graph, but called on demand.
    """
    llm = get_llm(state.get("current_model"))
    if not llm: return {}

    strategy = state.get('strategy_notes', '')
    case_summary = state.get('case_summary', '')
    charges = state.get('charges', [])

    prompt = f"""
    You are a Senior Legal Associate. Draft a legal document.

    CASE SUMMARY:
    {case_summary}

    CHARGES:
    {charges}

    DEFENSE STRATEGY:
    {strategy}

    DOCUMENT TYPE: {doc_type}
    SPECIFIC INSTRUCTIONS: {specific_context}

    {CITATION_INSTRUCTION}

    TASK:
    Draft the {doc_type}.
    - Use professional legal tone.
    - Reference specific facts from the case summary where relevant with source citations.
    - Include placeholders like [DATE], [JUDGE NAME] where needed.
    - If it's a Motion, include the standard caption header template.

    OUTPUT:
    Return ONLY the document text.
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])

    new_doc = {
        "title": f"{doc_type} - {date.today()}",
        "type": doc_type,
        "content": response.content,
        "created_at": str(date.today())
    }

    # Append to existing
    current_docs = state.get("drafted_documents", [])
    if not isinstance(current_docs, list):
        current_docs = []
    updated_docs = current_docs + [new_doc]

    return {"drafted_documents": updated_docs}


def conduct_legal_research(state: AgentState):
    """
    Node 13: Conducts web-based legal research using DuckDuckGo.
    """
    logger.info("--- Conducting Legal Research ---")
    llm = get_llm(state.get("current_model"))
    if not llm: return {"research_summary": "Error: API Key missing."}

    # Initialize search tool (graceful fallback if ddgs not installed)
    search = None
    try:
        if DuckDuckGoSearchRun is not None:
            search = DuckDuckGoSearchRun()
    except (ImportError, Exception) as e:
        logger.warning(f"DuckDuckGo search unavailable: {e}")

    # Context
    strategy = state.get('strategy_notes', '')
    charges = state.get('charges', [])
    case_summary = state.get('case_summary', '')
    ctx = get_case_context(state)

    # 1. Generate Search Queries
    prompt = f"""
    You are a Legal Research Assistant.
    {ctx['directives_block']}
    Based on the case facts and strategy, generate 3 specific search queries to find relevant case law or statutes.
    This is a {ctx['case_type_desc']} case. Focus on:
    - State-specific statutes (if state is known or implied, otherwise general).
    - Precedents for the specific {ctx['claims_label']}.
    - Legal theories mentioned in the strategy.

    CASE SUMMARY:
    {case_summary}

    CHARGES:
    {charges}

    STRATEGY:
    {strategy}

    Format as JSON list of strings:
    ["query 1", "query 2", "query 3"]
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    queries = []
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        queries = parsed
    else:
        logger.warning("Legal research query parsing failed -- falling back to default query")
        queries = [f"{ctx['search_prefix']} {charges[0].get('name') if charges else 'general'}"]

    # 2. Execute Searches (skip if search tool unavailable)
    results = []
    if search is not None:
        for q in queries:
            try:
                logger.info(f"Searching: {q}")
                res = search.invoke(q)
                results.append({"query": q, "result": res})
            except Exception as e:
                logger.warning(f"Search error for {q}: {e}")
                results.append({"query": q, "result": "Error executing search."})
    else:
        logger.info("Web search unavailable -- using LLM knowledge only")

    # 3. Synthesize Results (LLM-only research if no search results)
    if results:
        synthesis_prompt = f"""
    Synthesize the following search results into a Legal Research Memo.

    SEARCH RESULTS:
    {json.dumps(results, indent=2)}

    {CITATION_INSTRUCTION}

    TASK:
    Write a memo summarizing key findings, potential case law, and statutes.
    Cite the sources (URLs or Case Names) found in the search results.
    """
    else:
        synthesis_prompt = f"""You are a Legal Research Assistant. Web search is unavailable.
    Using your legal knowledge, provide a research memo for this case.

    This is a {ctx['case_type_desc']} case.

    CASE SUMMARY:
    {case_summary[:3000]}

    CHARGES/CLAIMS:
    {charges}

    DEFENSE STRATEGY:
    {strategy[:2000]}

    SEARCH QUERIES (what we would have searched for):
    {json.dumps(queries, indent=2)}

    TASK:
    Write a Legal Research Memo covering:
    - Applicable statutes and legal standards
    - Relevant case law and precedents from your training data
    - Potential legal defenses or arguments
    - Procedural considerations

    Note: This research is based on general legal knowledge, not live web results.
    Mark any specific citations as needing verification.
    """

    synthesis = invoke_with_retry(llm, [HumanMessage(content=synthesis_prompt)])

    return {"legal_research_data": results, "research_summary": synthesis.content}


# --- Lexis+ Search Assistant --------------------------------------------------


def generate_lexis_queries(state: AgentState, research_focus: str = ""):
    """
    Generates optimized Lexis+ Boolean search queries from the case context.
    Returns a list of query dicts with search string, description, filters, and relevance.
    """
    logger.info("--- Generating Lexis+ Search Queries ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {"lexis_queries": []}

    strategy = state.get('strategy_notes', '')
    case_summary = state.get('case_summary', '')
    charges = state.get('charges', [])
    case_type = state.get('case_type', 'criminal')

    # Build charges text
    charges_text = ""
    if isinstance(charges, list):
        for c in charges:
            if isinstance(c, dict):
                charges_text += f"- {c.get('name', 'Unknown')}"
                if c.get('statute_number'):
                    charges_text += f" ({c['statute_number']})"
                charges_text += "\n"

    focus_section = ""
    if research_focus:
        focus_section = f"""
    SPECIFIC RESEARCH FOCUS (user requested):
    {research_focus}
    Prioritize queries that address this specific topic.
    """

    prompt = f"""
    You are a Legal Research Expert specializing in Lexis+ search optimization.
    Generate 5 highly targeted Lexis+ Boolean search queries for the case below.

    CASE TYPE: {case_type}

    CASE SUMMARY:
    {case_summary}

    CHARGES/CLAIMS:
    {charges_text if charges_text else "(Not yet defined)"}

    STRATEGY:
    {strategy if strategy else "(Not yet developed)"}
    {focus_section}

    IMPORTANT: Use proper Lexis+ Boolean connectors:
    - "exact phrase" for exact matching
    - AND, OR, NOT for boolean logic
    - /s = within same sentence, /p = within same paragraph
    - w/n = within N words (e.g., w/5 = within 5 words)
    - ! = root expander (e.g., negligen! matches negligent, negligence, negligently)
    - * = universal character (e.g., wom*n matches woman, women)

    For each query provide:
    1. The Lexis+ Boolean search string (ready to paste)
    2. A plain-English description of what it targets
    3. Suggested Lexis+ filters (jurisdiction, date range, court level)
    4. Which aspect of the case it supports

    Format as JSON list:
    [
        {{
            "search_string": "\\"motion to suppress\\" /s (\\"fruit of the poisonous tree\\" OR \\"exclusionary rule\\") AND warrant!",
            "description": "Finds cases about suppressing evidence obtained through improper warrants",
            "filters": {{
                "jurisdiction": "Tennessee",
                "date_range": "Last 10 years",
                "court_level": "All Courts"
            }},
            "case_relevance": "Supports motion to suppress -- Fourth Amendment defense strategy"
        }}
    ]
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    queries = []
    parsed = extract_json(response.content, expect_list=True)
    if isinstance(parsed, list):
        queries = parsed
    else:
        # Fallback: wrap raw text
        queries = [{"search_string": response.content, "description": "AI-generated query (raw)",
                     "filters": {}, "case_relevance": "General research"}]

    return {"lexis_queries": queries}



def analyze_lexis_results(state: AgentState, pasted_text: str, query_context: str = ""):
    """
    Analyzes raw text pasted from Lexis+ -- extracts citations, holdings,
    favorability, and strategic use recommendations.
    """
    logger.info("--- Analyzing Lexis+ Results ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"lexis_analysis": {"error": "API Key missing."}}

    case_summary = state.get('case_summary', '')
    strategy = state.get('strategy_notes', '')
    ctx = get_case_context(state)

    query_section = ""
    if query_context:
        query_section = f"""
    ORIGINAL SEARCH QUERY:
    {query_context}
    """

    prompt = f"""
    You are a Senior Legal Research Analyst. Analyze the following case law text
    pasted from Lexis+. Extract and evaluate every case cited or discussed.

    This is a {ctx['case_type_desc']} case.

    OUR STRATEGY:
    {strategy if strategy else "(Not yet developed)"}

    CASE SUMMARY:
    {case_summary}
    {query_section}

    PASTED LEXIS+ TEXT:
    {pasted_text[:15000]}

    TASK:
    For each case found in the pasted text, extract:
    1. Full case citation (case name, volume, reporter, page, court, year)
    2. Key holding(s) -- the core legal principle decided
    3. Relevant facts -- how the facts compare to our case
    4. Favorability -- is this case FAVORABLE, UNFAVORABLE, or NEUTRAL for our side?
    5. Strategic use -- how specifically to use this case (motion support, cross-exam impeachment, jury instruction, appellate authority, etc.)
    6. Key quotes -- the most citation-worthy language from the opinion

    Also provide an overall research summary tying back to our case strategy.

    Format as JSON:
    {{
        "cases": [
            {{
                "citation": "State v. Smith, 456 S.W.3d 123 (Tenn. 2015)",
                "court": "Tennessee Supreme Court",
                "year": "2015",
                "holding": "The court held that...",
                "relevant_facts": "Similar to our case because...",
                "favorability": "FAVORABLE",
                "strategic_use": "Cite in motion to suppress to argue...",
                "key_quotes": ["Quote 1...", "Quote 2..."],
                "strength": "HIGH"
            }}
        ],
        "summary": "Overall research memo tying findings to case strategy...",
        "recommended_next_searches": ["Follow-up query 1", "Follow-up query 2"]
    }}
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])

    analysis = {}
    parsed = extract_json(response.content)
    if isinstance(parsed, dict):
        analysis = parsed
    else:
        analysis = {
            "cases": [],
            "summary": response.content,
            "recommended_next_searches": [],
            "_parse_error": True
        }

    return {"lexis_analysis": analysis}


# --- Standalone Functions (called on-demand, not part of the graph) ---


def generate_client_report(state):
    """
    Generates a plain-language case report suitable for sharing with the client.
    Avoids legal jargon and explains everything in accessible terms.
    """
    logger.info("--- Generating Client Report ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm: return "Error: API Key missing."

    case_summary = state.get("case_summary", "No case summary available.")
    strategy = state.get("strategy_notes", "No strategy developed yet.")
    timeline_data = state.get("timeline", [])
    charges = state.get("charges", [])
    devils_advocate = state.get("devils_advocate_notes", "")

    timeline_str = ""
    if isinstance(timeline_data, list) and timeline_data:
        for evt in timeline_data:
            timeline_str += f"- {evt.get('date', '')} {evt.get('time', '')}: {evt.get('event', '')}\n"
    else:
        timeline_str = str(timeline_data)[:2000] if timeline_data else "No timeline available."

    ctx = get_case_context(state)
    prompt = f"""
    You are a {ctx['role']} writing a case status report for your CLIENT (not another lawyer).
    Write in plain, simple English. Avoid all legal jargon -- if you must use a legal term,
    explain what it means in parentheses. Be honest but reassuring.
    This is a {ctx['case_type_desc']} case.

    {CITATION_INSTRUCTION}

    CASE SUMMARY (internal):
    {case_summary}

    LITIGATION STRATEGY (internal):
    {strategy}

    KEY DATES:
    {timeline_str}

    POTENTIAL CHALLENGES:
    {devils_advocate[:2000]}

    Write the report with these sections:

    # Your Case -- Status Update

    ## What's This Case About?
    (2-3 paragraph plain-language overview of what happened and what the {ctx['claims_label']} are)

    ## What We're Facing
    (Explain the {ctx['claims_label']} in simple terms -- what {ctx['opponent']} says happened, what the potential consequences are)

    ## Our Game Plan
    (Explain the litigation strategy in terms the client can understand)

    ## What Could Go Wrong
    (Honestly explain the risks, but frame them as things you're preparing for)

    ## What Happens Next
    (Next steps, upcoming court dates, what the client needs to do)

    ## Questions to Think About
    (List 3-5 questions you need the client to answer to strengthen the case)

    ---
    *This report was prepared for your review. Please do not share it with anyone
    outside our attorney-client relationship.*
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    return response.content


def generate_cheat_sheet(state: dict) -> dict:
    """
    Generates a condensed one-page courtroom cheat sheet from existing analysis.
    No new document processing -- purely synthesizes what's already in state.
    Returns: {"cheat_sheet": str}
    """
    model = get_llm(state.get("current_model", "xai"))

    # Gather inputs from state
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "No strategy available.")
    witnesses = state.get("witnesses", [])
    cross_exam = state.get("cross_examination_plan", [])
    timeline = state.get("timeline", [])
    evidence = state.get("evidence_foundations", [])
    elements = state.get("legal_elements", [])
    devils_advocate = state.get("devils_advocate_notes", "")
    consistency = state.get("consistency_check", [])

    witness_summary = ""
    for w in witnesses[:10]:
        if isinstance(w, dict):
            witness_summary += f"- {w.get('name', 'Unknown')}: {w.get('role', 'Unknown role')}\n"

    cross_summary = ""
    for cx in cross_exam[:15]:
        if isinstance(cx, dict):
            cross_summary += f"- [{cx.get('witness', 'Unknown')}] {cx.get('question', cx.get('topic', ''))}\n"

    timeline_summary = ""
    for t in timeline[:10]:
        if isinstance(t, dict):
            timeline_summary += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    evidence_summary = ""
    for e in evidence[:10]:
        if isinstance(e, dict):
            evidence_summary += f"- {e.get('evidence', e.get('name', 'Unknown'))}: {e.get('foundation_type', e.get('status', ''))}\n"

    elements_summary = ""
    for el in elements[:10]:
        if isinstance(el, dict):
            elements_summary += f"- {el.get('element', 'Unknown')}: {el.get('status', el.get('strength', ''))}\n"

    prompt = f"""You are a legal assistant creating a QUICK-REFERENCE CHEAT SHEET for use at the courtroom podium.

    CASE SUMMARY: {str(summary)[:2000]}

    STRATEGY: {str(strategy)[:1500]}

    WITNESSES: {witness_summary}

    CROSS-EXAM QUESTIONS: {cross_summary}

    TIMELINE: {timeline_summary}

    EVIDENCE: {evidence_summary}

    LEGAL ELEMENTS: {elements_summary}

    DEVIL'S ADVOCATE: {str(devils_advocate)[:500]}

    CONTRADICTIONS: {str(consistency)[:500]}

    Create a condensed, SCANNABLE courtroom cheat sheet with these exact sections:

    ## CASE THEORY (1 sentence)
    [Single sentence encapsulating the defense theory]

    ## TOP 3 OBJECTIONS TO ANTICIPATE
    1. [Objection + why + response]
    2. [Objection + why + response]
    3. [Objection + why + response]

    ## KEY CROSS-EXAM QUESTIONS (max 2 per witness)
    **[Witness Name]:**
    1. [Question]
    2. [Question]
    [Repeat for each key witness, max 4 witnesses]

    ## CRITICAL DATES
    - [Date: Event -- significance]
    [Max 5 dates]

    ## STRONGEST EVIDENCE
    - [Evidence item + why it's strong]
    [Max 3 items]

    ## BIGGEST VULNERABILITY
    - [Weakness + how to handle/mitigate]
    [Max 2 items]

    ## ELEMENTS STATUS (one line each)
    [Element: Met/Unmet/Weak -- brief note]

    Keep everything BRIEF. This should fit on ONE PRINTED PAGE. Use bullet points, not paragraphs.
    Do NOT include preamble or explanation -- go straight into the sections."""

    response = model.invoke([HumanMessage(content=prompt)])

    return {"cheat_sheet": response.content}


# === Opening & Closing Statement Generator ===


def generate_statements(state: dict, statement_type: str = "opening", tone: str = "measured", audience: str = "jury") -> dict:
    """
    Generates a draft opening or closing statement by synthesizing all analysis.
    statement_type: 'opening' or 'closing'
    tone: 'aggressive', 'measured', or 'empathetic'
    audience: 'jury' or 'bench' (adjusts rhetoric vs legal reasoning)
    Returns: {"statement": {"type": str, "tone": str, "audience": str, "content": str, "sections": list, "word_count": int, "est_minutes": float}}
    """
    logger.info(f"--- Generating {statement_type.title()} Statement ({tone}, {audience}) ---")
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"statement": {"type": statement_type, "tone": tone, "audience": audience, "content": "Error: API Key missing.", "sections": [], "word_count": 0, "est_minutes": 0}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "No summary available.")
    strategy = state.get("strategy_notes", "")
    timeline = state.get("timeline", [])
    witnesses = state.get("witnesses", [])
    elements = state.get("legal_elements", [])
    evidence = state.get("evidence_foundations", [])
    devils_advocate = state.get("devils_advocate_notes", "")
    mock_jury = state.get("mock_jury_feedback", [])

    timeline_str = ""
    for t in (timeline[:12] if isinstance(timeline, list) else []):
        if isinstance(t, dict):
            timeline_str += f"- {t.get('date', '?')}: {t.get('event', t.get('description', ''))}\n"

    witness_str = ""
    for w in (witnesses[:10] if isinstance(witnesses, list) else []):
        if isinstance(w, dict):
            witness_str += f"- {w.get('name', 'Unknown')} ({w.get('role', 'Unknown')})\n"

    elements_str = str(elements)[:3000] if elements else "No elements mapped."
    evidence_str = str(evidence)[:3000] if evidence else "No evidence analyzed."

    # Audience-specific adjustments
    if audience == "bench":
        audience_note = """AUDIENCE: BENCH TRIAL (judge only).
- Replace emotional rhetoric with precise legal reasoning
- Cite legal standards and burden of proof explicitly
- Focus on elements and how evidence satisfies each
- Use formal, respectful tone appropriate for addressing the court
- Reference applicable case law concepts where appropriate
- Less storytelling, more analytical framework"""
    else:
        audience_note = """AUDIENCE: JURY TRIAL.
- Write for laypersons -- avoid legal jargon unless immediately explained
- Use vivid, everyday language and relatable analogies
- Storytelling is powerful -- make the jury see, hear, and feel what happened
- Connect with shared values: fairness, truth, accountability"""

    if statement_type == "opening":
        section_labels = ["THE HOOK", "THE THEME", "THE ROADMAP", "WHAT HAPPENED", "THE LAW", "THE PROMISE", "THE CLOSE"]
        task_instruction = f"""Write a compelling OPENING STATEMENT for {ctx['our_side']}.

{audience_note}

You MUST structure the output with these EXACT section headers (use ## for each):
## THE HOOK
A powerful opening line that captures attention

## THE THEME
A 1-sentence case theme you'll return to throughout trial

## THE ROADMAP
Tell what the evidence will show, witness by witness

## WHAT HAPPENED
Walk through the facts chronologically, using vivid language

## THE LAW
Briefly explain what must be decided

## THE PROMISE
What you will prove and ask them to hold {ctx['opponent']} to their burden

## THE CLOSE
Return to your theme with a memorable final line

RULES:
- Use present tense and active voice for impact
- Do NOT argue -- save that for closing. State what the evidence WILL SHOW.
- Reference specific witnesses by name and what they will say
- Reference specific exhibits you will introduce
- Keep it 3-5 minutes of speaking time (~600-1000 words)"""
    else:
        section_labels = ["THE THEME CALLBACK", "THE EVIDENCE RECAP", "WITNESS CREDIBILITY", "THE LAW APPLICATION", "DEAL WITH WEAKNESSES", "THE EMOTIONAL APPEAL", "THE ASK", "THE FINAL LINE"]
        task_instruction = f"""Write a powerful CLOSING ARGUMENT for {ctx['our_side']}.

{audience_note}

You MUST structure the output with these EXACT section headers (use ## for each):
## THE THEME CALLBACK
Return to your trial theme

## THE EVIDENCE RECAP
Walk through key evidence, connecting each piece to legal elements

## WITNESS CREDIBILITY
Highlight credible witnesses, attack those who were not

## THE LAW APPLICATION
Walk through each element and show how evidence meets/fails it

## DEAL WITH WEAKNESSES
Address {ctx['opponent']}'s strongest points head-on

## THE EMOTIONAL APPEAL
Make them FEEL the weight of their decision

## THE ASK
State exactly what verdict you want and why justice demands it

## THE FINAL LINE
A memorable closing that echoes your theme

RULES:
- NOW you CAN argue, draw inferences, and ask rhetorical questions
- Reference specific testimony: "You heard Officer Smith say..."
- Point out contradictions and inconsistencies
- Use the devil's advocate analysis to preempt the other side's closing
- Keep it 5-8 minutes (~1000-1500 words)"""

    tone_instruction = {
        "aggressive": "Tone: AGGRESSIVE. Strong, declarative sentences. Challenge the other side directly. Show controlled righteous anger.",
        "measured": "Tone: MEASURED. Professional, logical, and persuasive. Build methodically. Let the facts do the work.",
        "empathetic": "Tone: EMPATHETIC. Connect emotionally with the jury. Use storytelling. Make it about real people and real consequences.",
    }.get(tone, "Tone: MEASURED.")

    prompt = f"""You are an elite trial attorney preparing for {ctx['case_type_desc']} proceedings.

{task_instruction}

{tone_instruction}

CASE SUMMARY:
{str(summary)[:3000]}

{ctx['our_side'].upper()} STRATEGY:
{str(strategy)[:2000]}

KEY TIMELINE:
{timeline_str or 'No timeline available.'}

WITNESSES:
{witness_str or 'No witnesses identified.'}

LEGAL ELEMENTS:
{elements_str}

KEY EVIDENCE:
{evidence_str}

DEVIL'S ADVOCATE (opposing side's best arguments):
{str(devils_advocate)[:1500]}

MOCK JURY FEEDBACK:
{str(mock_jury)[:1000] if mock_jury else 'No mock jury data.'}

Write the {statement_type} statement now using the exact section headers specified above."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])
    content = response.content

    # Parse sections from the markdown headers
    sections = []
    current_heading = None
    current_body = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                sections.append({"heading": current_heading, "content": "\n".join(current_body).strip()})
            current_heading = stripped[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_heading is not None:
        sections.append({"heading": current_heading, "content": "\n".join(current_body).strip()})

    word_count = len(content.split())
    est_minutes = round(word_count / 130, 1)  # ~130 words per minute speaking

    return {
        "statement": {
            "type": statement_type,
            "tone": tone,
            "audience": audience,
            "content": content,
            "sections": sections,
            "word_count": word_count,
            "est_minutes": est_minutes,
        }
    }


# === Document Cross-Reference Matrix ===


def challenge_finding(finding_text: str, case_context: str, model_provider: str = "") -> str:
    """
    Takes a specific AI-generated finding and returns a structured
    challenge / counter-argument analysis.
    """
    llm = get_llm(model_provider)

    prompt = f"""You are a senior opposing counsel reviewing defense analysis.
Your job is to CHALLENGE the following AI-generated finding and expose every
weakness, alternative interpretation, and counter-argument.

## The Finding to Challenge
{finding_text}

## Case Context
{case_context[:3000]}

Provide your challenge in this format:

### Counter-Arguments
- (List specific counter-arguments the opposing side would raise)

### Weaknesses in Reasoning
- (Where is the logic thin, speculative, or unsupported?)

### Missing Evidence
- (What facts/documents would be needed to strengthen this finding?)

### Risk Assessment
Rate the finding's reliability: **Strong / Moderate / Weak**
Brief explanation of why.

{CITATION_INSTRUCTION}
Be thorough, adversarial, and constructive."""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    return response.content



# === Deposition Outline Generator ===
