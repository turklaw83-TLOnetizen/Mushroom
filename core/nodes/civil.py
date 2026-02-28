# ---- Sub-module of core.nodes ------------------------------------------------
import logging

from core.nodes._common import *

logger = logging.getLogger(__name__)


def analyze_medical_records(state, med_records_text):
    """
    Analyzes medical records for civil litigation.
    Returns a comprehensive evaluation with 7 sub-analyses:
    - treatment_timeline, gap_analysis, causation_map, damages_estimate,
    - pre_existing_conditions, ime_critique, icd_cpt_decoder
    """
    logger.info("--- Analyzing Medical Records ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm: return {"medical_records_analysis": {"error": "API Key missing."}}

    case_summary = state.get("case_summary", "No case summary available.")
    ctx = get_case_context(state)

    prompt = f"""
    You are a medical-legal analyst assisting a {ctx['role']} in a civil case.
    Analyze the following medical records and provide a COMPREHENSIVE evaluation.

    CASE SUMMARY:
    {case_summary}

    MEDICAL RECORDS:
    {med_records_text}

    Return your analysis as valid JSON with EXACTLY these 7 keys:

    {{
        "treatment_timeline": [
            {{
                "date": "YYYY-MM-DD",
                "provider": "Dr. Name / Facility",
                "type": "ER Visit | Follow-up | Surgery | Imaging | Therapy | Rx",
                "diagnosis": "diagnosis given",
                "procedure": "what was done",
                "notes": "key findings or observations"
            }}
        ],

        "gap_analysis": [
            {{
                "gap_start": "YYYY-MM-DD",
                "gap_end": "YYYY-MM-DD",
                "gap_days": 30,
                "between": "Provider A → Provider B",
                "risk_level": "HIGH | MEDIUM | LOW",
                "opposing_argument": "What opposing counsel will argue about this gap",
                "counter_argument": "How to explain/defend this gap"
            }}
        ],

        "causation_map": [
            {{
                "injury": "e.g., L4-L5 herniated disc",
                "mechanism": "How the incident caused this injury",
                "pre_existing": true/false,
                "aggravation": "If pre-existing, how incident aggravated it",
                "supporting_evidence": "Medical evidence supporting causation",
                "strength": "STRONG | MODERATE | WEAK"
            }}
        ],

        "damages_estimate": {{
            "past_medical": 0.00,
            "future_medical": 0.00,
            "past_pain_suffering": "Description and suggested range",
            "future_pain_suffering": "Description and suggested range",
            "lost_wages_past": "Estimate if data available",
            "lost_wages_future": "Estimate if data available",
            "total_specials": 0.00,
            "multiplier_range": "2x-5x based on severity",
            "settlement_range": "Low - High estimate",
            "itemized_bills": [
                {{"provider": "...", "amount": 0.00, "service": "..."}}
            ],
            "notes": "Key factors affecting valuation"
        }},

        "pre_existing_conditions": [
            {{
                "condition": "e.g., degenerative disc disease",
                "documented_since": "date or approximate timeframe",
                "current_status": "How it presents now post-incident",
                "eggshell_argument": "How to use eggshell plaintiff doctrine",
                "defense_attack": "How defense will use this against us",
                "counter_strategy": "How to neutralize the defense argument"
            }}
        ],

        "ime_critique": {{
            "examiner": "Dr. Name if identified",
            "bias_indicators": [
                "Specific findings suggesting bias (e.g., exam lasted only 10 minutes)"
            ],
            "omissions": [
                "Key findings or tests the IME examiner failed to address"
            ],
            "contradictions": [
                "Where IME contradicts treating physician records"
            ],
            "attack_points": [
                "Specific areas to challenge on cross-examination"
            ],
            "overall_reliability": "LOW | MODERATE | HIGH"
        }},

        "icd_cpt_decoder": [
            {{
                "code": "M54.5",
                "type": "ICD-10 | CPT",
                "medical_term": "Low back pain",
                "plain_language": "Chronic lower back pain lasting more than 3 months",
                "relevance": "How this relates to the case/injury claim"
            }}
        ]
    }}

    IMPORTANT INSTRUCTIONS:
    - Extract EVERY date, provider, and procedure mentioned
    - Flag ALL gaps in treatment greater than 14 days
    - For causation, consider biomechanics and mechanism of injury
    - Damages should reflect actual billed amounts where stated; estimate where not
    - If IME report is not present, set ime_critique to {{"examiner": "No IME found", "bias_indicators": [], "omissions": [], "contradictions": [], "attack_points": [], "overall_reliability": "N/A"}}
    - Decode ALL medical codes found in the records
    - Be thorough — this analysis will be used for litigation strategy

    Return ONLY the JSON object, no markdown fences or extra text.
    """

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])

    # Parse the JSON response
    try:
        content = response.content.strip()
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        result = json.loads(content)
    except (json.JSONDecodeError, Exception):
        # If JSON parsing fails, return the raw content for display
        result = {"raw_analysis": response.content}

    return {"medical_records_analysis": result}


# === Node 16: Medical Chronology Agent (Civil Only) ===


def generate_medical_chronology(state):
    """
    Dedicated medical chronology agent for civil cases.
    Produces an attorney-usable chronological narrative of all medical
    treatment, distinct from the litigation-focused medical_records_analysis.
    """
    logger.info("--- Generating Medical Chronology ---")
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"medical_chronology": {"error": "API Key missing."}}

    case_summary = state.get("case_summary", "No case summary available.")
    ctx = get_case_context(state)
    full_text = state.get("full_text", "")

    prompt = f"""
    You are a medical chronology specialist assisting a {ctx['role']} in a civil case.
    Your job is to organize ALL medical information from the case documents into a
    clear, chronological, attorney-friendly format.

    CASE SUMMARY:
    {case_summary}

    CASE DOCUMENTS:
    {full_text[:80000]}

    Return your analysis as valid JSON with EXACTLY these 6 keys:

    {{
        "entries": [
            {{
                "date": "YYYY-MM-DD",
                "provider": "Dr. Name / Facility",
                "specialty": "Orthopedic | ER | Radiology | PT | PCP | Pain Mgmt | Neurology | Other",
                "visit_type": "ER Visit | Office Visit | Surgery | Imaging | Physical Therapy | IME | Telehealth | Rx Refill",
                "chief_complaint": "Patient's stated reason for visit",
                "diagnoses": ["ICD code or diagnosis given"],
                "procedures": ["What was done"],
                "medications": ["Prescribed or administered"],
                "referrals": ["Referred to whom"],
                "work_status": "Full duty | Light duty | Off work | Not addressed",
                "narrative": "One-paragraph plain-English summary of this visit in context of overall treatment",
                "key_quotes": ["Important direct quotes from the medical record"]
            }}
        ],

        "treatment_gaps": [
            {{
                "gap_start": "YYYY-MM-DD",
                "gap_end": "YYYY-MM-DD",
                "gap_days": 30,
                "between_providers": "Dr. A → Dr. B",
                "risk_level": "HIGH | MEDIUM | LOW",
                "explanation": "Possible reason for gap and how to address it"
            }}
        ],

        "provider_summary": [
            {{
                "name": "Dr. John Smith",
                "specialty": "Orthopedic Surgery",
                "facility": "City Medical Center",
                "first_visit": "YYYY-MM-DD",
                "last_visit": "YYYY-MM-DD",
                "total_visits": 5,
                "role_in_treatment": "Primary treating physician for spinal injuries"
            }}
        ],

        "medication_timeline": [
            {{
                "medication": "Gabapentin 300mg",
                "prescribed_by": "Dr. Smith",
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD or ongoing",
                "purpose": "Nerve pain management",
                "changes": "Increased to 600mg on YYYY-MM-DD"
            }}
        ],

        "injury_progression": [
            {{
                "injury": "L4-L5 herniated disc",
                "initial_presentation": "Description at first mention",
                "progression": [
                    {{"date": "YYYY-MM-DD", "status": "Description of condition at this point"}}
                ],
                "current_status": "Description of current condition",
                "prognosis": "Doctor's stated prognosis if available"
            }}
        ],

        "overall_narrative": "A 2-4 paragraph narrative summary of the entire medical treatment history in chronological order, written in clear language suitable for inclusion in a demand letter or trial brief. This should tell the story of the patient's medical journey from incident to present."
    }}

    IMPORTANT INSTRUCTIONS:
    - Extract EVERY date, provider, facility, and procedure mentioned in ALL documents
    - Include ALL visits even routine follow-ups — attorneys need the complete picture
    - Flag treatment gaps greater than 14 days
    - Use exact dates from records, not approximations
    - The overall_narrative should read like a story, not a list
    - Include direct quotes from records where they strengthen the narrative
    - Note work status changes — these directly impact damages
    - Track medication escalation/de-escalation as it shows injury severity
    """

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            elif "```" in raw:
                raw = raw[:raw.rfind("```")]
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "entries": [],
            "treatment_gaps": [],
            "provider_summary": [],
            "medication_timeline": [],
            "injury_progression": [],
            "overall_narrative": raw if 'raw' in dir() else "Failed to parse medical chronology."
        }
    except Exception as e:
        result = {"error": str(e)}

    return {"medical_chronology": result}



def generate_demand_letter(state, params=None):
    """
    Generates a professional demand letter for civil litigation.
    Uses case summary, medical records analysis, medical chronology, and damages
    data to produce a formal demand letter with configurable tone and amount.

    Args:
        state: Agent state dict with case data
        params: Optional dict with {recipient, tone, demand_amount, deadline, custom_instructions}

    Returns: {"demand_letter": {"letter_text": str, "metadata": dict}}
    """
    if params is None:
        params = {}

    model = get_llm(state.get("current_model", "xai"))
    ctx = get_case_context(state)

    # Gather case data
    case_summary = state.get("case_summary", "")
    med_analysis = state.get("medical_records_analysis", {})
    med_chronology = state.get("medical_chronology", {})
    strategy = state.get("analysis", {}).get("strategy", "")
    client_name = state.get("client_name", "[Client Name]")

    # Extract damages data if available
    damages = {}
    if isinstance(med_analysis, dict):
        damages = med_analysis.get("damages_estimate", {})

    # Params
    recipient = params.get("recipient", "[Insurance Company / Opposing Party]")
    recipient_address = params.get("recipient_address", "[Address]")
    tone = params.get("tone", "moderate")  # aggressive, moderate, conservative
    demand_amount = params.get("demand_amount", "")
    deadline = params.get("deadline", "30 days")
    custom_instructions = params.get("custom_instructions", "")
    attorney_name = params.get("attorney_name", "[Attorney Name]")
    firm_name = params.get("firm_name", "[Firm Name]")

    tone_guidance = {
        "aggressive": "Use assertive, forceful language. Emphasize the strength of the case, the severity of injuries, and the certainty of a favorable verdict at trial. Reference specific legal precedents that support a high award. Clearly state the consequences of not settling.",
        "moderate": "Use professional, firm but balanced language. Present the facts clearly, acknowledge the strengths of the case without being confrontational. Express willingness to negotiate while maintaining a strong position.",
        "conservative": "Use respectful, measured language. Emphasize good faith and the benefits of resolution. Present the facts objectively and express openness to reasonable discussion. Suitable for cases where the relationship matters or liability is contested."
    }.get(tone, "Use professional, firm but balanced language.")

    prompt = f"""You are a senior civil litigation attorney drafting a formal demand letter.

GENERATE A PROFESSIONAL DEMAND LETTER using the following case information:

== CLIENT ==
Client: {client_name}
Role: {ctx['our_party']}

== RECIPIENT ==
To: {recipient}
Address: {recipient_address}

== CASE SUMMARY ==
{case_summary[:8000] if case_summary else 'No case summary available.'}

== MEDICAL RECORDS ANALYSIS ==
{json.dumps(damages, indent=2)[:3000] if damages else 'No damages data available.'}

== MEDICAL CHRONOLOGY ==
{json.dumps(med_chronology, indent=2)[:3000] if med_chronology else 'No chronology available.'}

== CASE STRATEGY ==
{str(strategy)[:2000] if strategy else 'No strategy available.'}

== PARAMETERS ==
- Tone: {tone.upper()} — {tone_guidance}
- Demand Amount: {demand_amount if demand_amount else 'Determine an appropriate amount based on the damages analysis'}
- Response Deadline: {deadline}
- Attorney: {attorney_name}
- Firm: {firm_name}
{f'- Special Instructions: {custom_instructions}' if custom_instructions else ''}

Produce the letter in STANDARD DEMAND LETTER FORMAT with these sections:

1. **Header** — Date, recipient info, RE line with claim/case number
2. **Introduction** — Identify the parties, state the purpose
3. **Liability Statement** — Facts establishing fault/liability
4. **Injuries & Treatment Summary** — Chronological overview of medical treatment
5. **Damages** — Itemized (past medical, future medical, lost wages, pain & suffering)
6. **Demand** — Specific dollar amount with justification
7. **Deadline & Consequences** — Response deadline and next steps if not resolved
8. **Closing** — Professional sign-off

Return as JSON:
{{
  "letter_text": "<the full formatted demand letter text>",
  "summary": "<one-paragraph summary of the letter>",
  "sections": {{
    "liability": "<liability section text>",
    "injuries": "<injuries section text>",
    "damages_breakdown": "<damages section text>",
    "demand_amount_stated": "<the stated demand amount>"
  }},
  "metadata": {{
    "recipient": "{recipient}",
    "tone": "{tone}",
    "demand_amount": "{demand_amount if demand_amount else 'auto-calculated'}",
    "deadline": "{deadline}",
    "date_generated": "<today's date>"
  }}
}}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            elif "```" in raw:
                raw = raw[:raw.rfind("```")]
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "letter_text": raw if 'raw' in dir() else "Failed to generate demand letter.",
            "summary": "",
            "sections": {},
            "metadata": {"recipient": recipient, "tone": tone, "demand_amount": demand_amount, "deadline": deadline}
        }
    except Exception as e:
        result = {"error": str(e)}

    return {"demand_letter": result}



def analyze_media_forensic(state: dict, transcript: str, source_name: str = "", media_type: str = "audio") -> dict:
    """
    Performs deep forensic analysis of an audio/video transcript.
    Returns 6-part analysis: speakers, timeline, admissions,
    inconsistencies, procedural compliance, and evidence flags.
    """
    logger.info("--- Analyzing Media Forensic: %s ---", source_name)
    model = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not model:
        return {"media_analysis": {}}

    case_summary = state.get("case_summary", "")
    case_type = state.get("case_type", "criminal")
    raw_docs_snippet = str(state.get("raw_documents", ""))[:5000]

    prompt = f"""You are a forensic media analyst for a {case_type} case. Analyze this {media_type} transcript thoroughly.

TRANSCRIPT ({source_name}):
{transcript}

CASE CONTEXT:
{case_summary}

OTHER EVIDENCE SNIPPET:
{raw_docs_snippet}

Provide a comprehensive analysis in exactly this JSON format:
{{
  "speakers": [
    {{
      "label": "Speaker identifier (e.g., Officer Smith, Defendant, Dispatch, Unknown Male)",
      "role": "Their role in the case",
      "key_quotes": ["Direct quotes attributed to this speaker"],
      "demeanor_notes": "Observable tone/behavior from language (agitated, calm, evasive, etc.)"
    }}
  ],
  "timeline": [
    {{
      "timestamp": "Approximate time or sequence marker",
      "event": "What happened at this point",
      "speaker": "Who was speaking/acting",
      "significance": "Legal significance of this moment"
    }}
  ],
  "admissions": [
    {{
      "speaker": "Who made the admission",
      "statement": "Exact quote or close paraphrase",
      "type": "Type: spontaneous_utterance | admission_against_interest | excited_utterance | confession | miranda_waiver | other",
      "legal_significance": "Why this matters for the case",
      "admissibility_notes": "Potential hearsay exceptions or admissibility issues"
    }}
  ],
  "inconsistencies": [
    {{
      "statement_in_recording": "What was said in the recording",
      "conflicts_with": "What document/report/testimony it conflicts with",
      "nature": "Type of inconsistency (factual, temporal, identity, etc.)",
      "impeachment_value": "high | medium | low",
      "suggested_use": "How to use this at trial"
    }}
  ],
  "procedural_compliance": {{
    "miranda_given": "yes | no | unclear | not_applicable",
    "miranda_timing": "When Miranda was given relative to questioning",
    "recording_gaps": ["Any gaps, pauses, or edits detected in the recording"],
    "chain_of_custody_concerns": ["Issues with the recording's integrity"],
    "identification_procedures": "Any show-up, lineup, or ID procedure issues",
    "coercion_indicators": ["Any signs of coerced statements or improper pressure"],
    "overall_compliance": "Summary of procedural compliance"
  }},
  "evidence_flags": [
    {{
      "type": "Type: exculpatory | brady_material | impeachment | corroborative | aggravating | mitigating",
      "description": "What was found",
      "location_in_transcript": "Where in the transcript this appears",
      "recommended_action": "What the attorney should do with this"
    }}
  ],
  "overall_assessment": "2-3 sentence summary of the recording's overall evidentiary value and key takeaways"
}}

IMPORTANT:
- Be thorough — identify ALL speakers even if unnamed
- Flag ANY statement that could be an admission or spontaneous utterance
- Compare statements against the case summary and other evidence for inconsistencies
- For {case_type} cases, pay special attention to {'Miranda, consent, and use of force' if case_type == 'criminal' else 'liability admissions, damages acknowledgment, and prior inconsistent statements'}
- Return ONLY the JSON, no markdown fences"""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        analysis = json.loads(content)
    except (json.JSONDecodeError, Exception):
        analysis = {
            "speakers": [],
            "timeline": [],
            "admissions": [],
            "inconsistencies": [],
            "procedural_compliance": {},
            "evidence_flags": [],
            "overall_assessment": response.content[:2000],
            "_parse_error": True
        }

    # Store with source key for multi-file support
    existing = state.get("media_analysis", {}) or {}
    existing[source_name or "unknown"] = analysis
    return {"media_analysis": existing}


# === Spreadsheet / Excel Analysis ===


def analyze_spreadsheet(state: dict, spreadsheet_text: str, source_name: str = "", sheet_info: str = "") -> dict:
    """
    AI analysis of spreadsheet/Excel data for legal relevance.
    Returns 5-part analysis: summary, financial, timeline, findings, cross-reference.
    """
    logger.info("--- Analyzing Spreadsheet: %s ---", source_name)
    model = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not model:
        return {"spreadsheet_analysis": {}}

    case_summary = state.get("case_summary", "")
    case_type = state.get("case_type", "criminal")

    prompt = f"""You are a forensic data analyst reviewing spreadsheet evidence for a {case_type} case.

SPREADSHEET DATA ({source_name}):
{sheet_info}
{spreadsheet_text[:15000]}

CASE CONTEXT:
{case_summary}

Provide a comprehensive analysis in exactly this JSON format:
{{
  "data_summary": {{
    "description": "What this spreadsheet contains and its likely purpose",
    "record_count": "Number of rows/records",
    "key_columns": ["List of the most important column headers"],
    "data_types": "Types of data present (financial, dates, names, addresses, etc.)",
    "date_range": "Earliest to latest date found, if applicable",
    "completeness": "Assessment of data quality — missing fields, blank rows, etc."
  }},
  "financial_analysis": {{
    "has_financial_data": true,
    "total_amounts": "Summary of monetary totals if present",
    "anomalies": [
      {{
        "description": "What is unusual",
        "rows_affected": "Which rows/entries",
        "significance": "Why this matters legally"
      }}
    ],
    "patterns": ["Regular patterns, recurring amounts, suspicious timing, round numbers, etc."]
  }},
  "timeline_data": {{
    "has_dates": true,
    "chronological_events": [
      {{
        "date": "Date found",
        "event": "What happened per the data",
        "significance": "Legal relevance"
      }}
    ],
    "gaps": ["Any suspicious gaps in chronological data"],
    "clustering": "Any dates that cluster together unusually"
  }},
  "key_findings": [
    {{
      "finding": "Specific discovery from the data",
      "supporting_data": "The rows/values that support this",
      "legal_relevance": "How this helps or hurts the case",
      "priority": "high | medium | low"
    }}
  ],
  "cross_reference": {{
    "matches_case_facts": ["Data points that confirm known case facts"],
    "contradicts_case_facts": ["Data points that contradict known facts"],
    "new_leads": ["New information not previously known from other evidence"],
    "suggested_follow_up": ["Additional investigation steps based on the data"]
  }},
  "overall_assessment": "2-3 sentence summary of the spreadsheet's evidentiary value"
}}

IMPORTANT:
- If no financial data exists, set has_financial_data to false and skip financial details
- If no date columns exist, set has_dates to false
- Focus on legally relevant findings — fraud indicators, timeline gaps, quantity discrepancies
- For {case_type} cases, pay special attention to {'financial records, phone records, and surveillance logs' if case_type == 'criminal' else 'billing records, damages calculations, and contract terms'}
- Return ONLY the JSON, no markdown fences"""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        analysis = json.loads(content)
    except (json.JSONDecodeError, Exception):
        analysis = {
            "data_summary": {},
            "financial_analysis": {},
            "timeline_data": {},
            "key_findings": [],
            "cross_reference": {},
            "overall_assessment": response.content[:2000],
            "_parse_error": True
        }

    existing = state.get("spreadsheet_analysis", {}) or {}
    existing[source_name or "unknown"] = analysis
    return {"spreadsheet_analysis": existing}


# -- Challenge This -- Devil's Advocate per finding -------------------------


def compare_documents(state: dict, doc_a_name: str, doc_b_name: str) -> dict:
    """
    Deep comparison of two case documents to find contradictions,
    timeline discrepancies, omissions, and impeachment opportunities.
    Returns: {"document_comparison": {"doc_a": str, "doc_b": str, ...}}
    """
    logger.info("--- Comparing Documents: %s vs %s ---", doc_a_name, doc_b_name)
    model = get_llm(state.get("current_model", "xai"), max_output_tokens=8192)
    if not model:
        return {"document_comparison": {"doc_a": doc_a_name, "doc_b": doc_b_name, "error": "API Key missing."}}

    raw_docs = state.get("raw_documents", [])
    if not raw_docs:
        return {"document_comparison": {"doc_a": doc_a_name, "doc_b": doc_b_name, "error": "No documents loaded."}}

    doc_a_content = ""
    doc_b_content = ""
    for d in raw_docs:
        source = d.metadata.get("source", "Unknown") if hasattr(d, "metadata") else "Unknown"
        content = d.page_content if hasattr(d, "page_content") else str(d)
        src_base = os.path.basename(source) if source else ""
        if src_base == doc_a_name or source == doc_a_name:
            doc_a_content += content + "\n"
        elif src_base == doc_b_name or source == doc_b_name:
            doc_b_content += content + "\n"

    if not doc_a_content:
        return {"document_comparison": {"doc_a": doc_a_name, "doc_b": doc_b_name, "error": f"Could not find content for '{doc_a_name}'."}}
    if not doc_b_content:
        return {"document_comparison": {"doc_a": doc_a_name, "doc_b": doc_b_name, "error": f"Could not find content for '{doc_b_name}'."}}

    ctx = get_case_context(state)
    summary = state.get("case_summary", "")

    prompt = f"""You are a meticulous {ctx['role']} performing a DEEP DOCUMENT COMPARISON.

Your task is to compare these two documents and identify EVERY contradiction, inconsistency,
discrepancy, and omission between them. This is critical for impeachment and trial preparation.

=== DOCUMENT A: {doc_a_name} ===
{doc_a_content[:8000]}

=== DOCUMENT B: {doc_b_name} ===
{doc_b_content[:8000]}

CASE CONTEXT:
{str(summary)[:2000]}

Return a JSON object:
{{
    "doc_a": "{doc_a_name}",
    "doc_b": "{doc_b_name}",
    "overall_relationship": "supports | contradicts | supplements | mixed",
    "agreement_level": "high | moderate | low",
    "summary": "2-3 sentence summary of the comparison",
    "contradictions": [
        {{
            "id": 1,
            "category": "factual | temporal | identity | quantity | sequence | omission",
            "doc_a_says": "What Document A states (include specific text)",
            "doc_b_says": "What Document B states (include specific text)",
            "severity": "critical | significant | minor",
            "impeachment_value": "high | medium | low",
            "explanation": "Why this matters and how it could be used at trial",
            "suggested_question": "A question to ask about this contradiction in cross-exam"
        }}
    ],
    "timeline_discrepancies": [
        {{
            "event": "What event has a timeline issue",
            "doc_a_time": "Time/date per Document A",
            "doc_b_time": "Time/date per Document B",
            "gap": "Duration of discrepancy",
            "significance": "Why this matters"
        }}
    ],
    "omissions": [
        {{
            "present_in": "doc_a or doc_b",
            "missing_from": "doc_a or doc_b",
            "detail": "What information is present in one but absent from the other",
            "significance": "Why this omission matters"
        }}
    ],
    "corroborations": [
        {{
            "fact": "What fact both documents agree on",
            "significance": "Why this agreement matters for the case"
        }}
    ],
    "impeachment_strategy": "Overall strategy for using these contradictions at trial"
}}

RULES:
- Be EXTREMELY thorough — check dates, times, names, quantities, sequences
- Even small discrepancies can be valuable for impeachment
- Note when one document OMITS something present in the other
- Identify which contradictions are most useful for {ctx['our_side']}
- Suggest specific cross-examination questions for key contradictions

Return ONLY the JSON object, no markdown fences."""

    response = invoke_with_retry(model, [HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
        comparison = json.loads(content)
    except (json.JSONDecodeError, Exception):
        comparison = {
            "doc_a": doc_a_name,
            "doc_b": doc_b_name,
            "raw_output": response.content,
            "_parse_error": True
        }

    return {"document_comparison": comparison}


# === Exhibit List Builder ===
