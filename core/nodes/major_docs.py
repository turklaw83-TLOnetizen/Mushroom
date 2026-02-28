# ---- Major Document Drafting Functions ------------------------------------
# Outline generation, section-by-section drafting, citation library.
# Called on demand from ui/pages/major_docs_ui.py — NOT part of the main graph.

import json
import logging
import re
from datetime import date

from core.nodes._common import *

logger = logging.getLogger(__name__)


# ---- Document Type Definitions -------------------------------------------

DOC_TYPES = {
    "Appellate Brief": ["Opening Brief", "Reply Brief", "Amicus Brief"],
    "Post-Conviction Relief": ["PCR Petition", "Habeas Corpus", "Coram Nobis"],
    "Civil Complaint": ["Initial Complaint", "Amended Complaint", "Counterclaim", "Third-Party Complaint"],
    "Appellate Motion": ["Motion for Extension", "Motion to Stay", "Motion for Rehearing"],
    "Major Motion": ["Motion for Summary Judgment", "Motion to Dismiss", "Motion for New Trial"],
    "Custom Document": [],
}


# ---- Outline Generation -------------------------------------------------

def generate_document_outline(state: AgentState, doc_type: str, doc_subtype: str,
                               custom_instructions: str = "",
                               target_length: str = "Standard (~15-25 pages)",
                               tone: str = "Formal/Persuasive") -> dict:
    """Generate a structured section-by-section outline for a major document.

    Returns: {"outline": [...], "document_title": "..."}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return {"error": "No LLM configured. Please set an API key."}

    ctx = get_case_context(state)

    # Gather all available case materials
    case_summary = state.get("case_summary", "")
    strategy = state.get("strategy_notes", "")
    research = state.get("legal_research_data", [])
    elements = state.get("legal_elements", [])
    evidence = state.get("evidence_foundations", [])
    witnesses = state.get("witnesses", [])
    timeline = state.get("timeline", [])
    charges = state.get("charges", [])
    existing_docs = state.get("drafted_documents", [])

    research_summary = ""
    if research:
        research_summary = "\n".join(
            f"- {r.get('query', '')}: {r.get('summary', '')[:200]}"
            for r in research[:10] if isinstance(r, dict)
        )

    elements_summary = ""
    if elements:
        elements_summary = "\n".join(
            f"- {e.get('charge', '')}: {e.get('element', '')} (strength: {e.get('strength', '')})"
            for e in elements[:20] if isinstance(e, dict)
        )

    prompt = f"""You are a Senior Appellate Attorney drafting a {doc_type} ({doc_subtype}).

{ctx.get('directives_block', '')}

ROLE: {ctx.get('role', 'Attorney')}
CASE TYPE: {ctx.get('case_type_label', state.get('case_type', ''))}
CLIENT: {state.get('client_name', '[Client]')}
TONE: {tone}
TARGET LENGTH: {target_length}

CASE SUMMARY:
{case_summary[:3000] if case_summary else '[No case summary available — outline based on document type structure]'}

CHARGES/CLAIMS:
{json.dumps(charges[:10], indent=2) if charges else '[None specified]'}

STRATEGY NOTES:
{strategy[:2000] if strategy else '[No strategy notes]'}

LEGAL RESEARCH:
{research_summary or '[No research data]'}

LEGAL ELEMENTS:
{elements_summary or '[No elements mapped]'}

CUSTOM INSTRUCTIONS:
{custom_instructions or '[None]'}

TASK:
Generate a detailed section-by-section outline for this {doc_type} ({doc_subtype}).
Each section should include:
- section_num: Roman numeral (I, II, III, etc.)
- title: Section heading
- description: 2-3 sentence description of what this section covers and the key arguments/facts to include
- estimated_pages: Estimated page count for this section

Also provide the formal document title (e.g., "OPENING BRIEF OF APPELLANT").

Return JSON ONLY:
{{
    "document_title": "TITLE IN ALL CAPS",
    "outline": [
        {{"section_num": "I", "title": "...", "description": "...", "estimated_pages": 2}},
        ...
    ]
}}
"""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    result = extract_json(response.content)

    if result and isinstance(result, dict) and "outline" in result:
        return result
    else:
        # Fallback: return raw text if JSON extraction fails
        return {
            "document_title": f"{doc_subtype.upper()}",
            "outline": [{"section_num": "I", "title": "Introduction", "description": response.content[:500], "estimated_pages": 2}],
            "raw_response": response.content,
        }


# ---- Section Drafting ----------------------------------------------------

def draft_document_section(state: AgentState, section: dict, outline: list,
                            previous_sections: list, citation_library: list,
                            doc_type: str, tone: str = "Formal/Persuasive",
                            specific_instructions: str = "") -> dict:
    """Draft a single section of a major document with full context.

    Returns: {"content": "...", "citations_used": [...]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)

    # Build outline summary
    outline_text = "\n".join(
        f"  {s.get('section_num', '')}. {s.get('title', '')} — {s.get('description', '')}"
        for s in outline
    )

    # Build previous sections context (last 3 sections for continuity)
    prev_text = ""
    if previous_sections:
        for ps in previous_sections[-3:]:
            prev_text += f"\n--- {ps.get('section_num', '')}. {ps.get('title', '')} ---\n"
            content = ps.get("content", "")
            # Truncate long sections to last 1000 chars for continuity
            if len(content) > 1500:
                prev_text += f"[...]\n{content[-1000:]}\n"
            else:
                prev_text += f"{content}\n"

    # Build citation library reference
    cite_text = ""
    if citation_library:
        cite_text = "AVAILABLE CITATIONS (use ONLY these — do NOT fabricate citations):\n"
        for c in citation_library:
            cite_text += f"  - {c.get('case_name', '')} {c.get('citation', '')}: {c.get('holding', '')[:150]}\n"

    case_summary = state.get("case_summary", "")
    strategy = state.get("strategy_notes", "")
    evidence = state.get("evidence_foundations", [])
    timeline = state.get("timeline", [])
    witnesses = state.get("witnesses", [])

    # Relevant evidence snippets
    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    section_num = section.get("section_num", "")
    section_title = section.get("title", "")
    section_desc = section.get("description", "")
    section_instructions = section.get("instructions", "")

    prompt = f"""You are a Senior {ctx.get('role', 'Attorney')} drafting Section {section_num} of a {doc_type}.

{ctx.get('directives_block', '')}

TONE: {tone}
CLIENT: {state.get('client_name', '[Client]')}

FULL DOCUMENT OUTLINE:
{outline_text}

CURRENT SECTION TO DRAFT:
  Number: {section_num}
  Title: {section_title}
  Description: {section_desc}
  {f'Special Instructions: {section_instructions}' if section_instructions else ''}
  {f'Additional Instructions: {specific_instructions}' if specific_instructions else ''}

CASE SUMMARY:
{case_summary[:3000] if case_summary else '[No summary]'}

STRATEGY:
{strategy[:2000] if strategy else '[No strategy]'}

EVIDENCE:
{evidence_text or '[No evidence data]'}

{cite_text}

{CITATION_INSTRUCTION}

PREVIOUS SECTIONS (for continuity and to avoid repetition):
{prev_text if prev_text else '[This is the first section]'}

TASK:
Draft Section {section_num}: {section_title}

Requirements:
1. Write in professional legal tone ({tone}).
2. Use specific facts from the case materials with source citations.
3. If citing case law, use ONLY citations from the AVAILABLE CITATIONS list above. Do NOT fabricate or hallucinate any citations.
4. Include [PLACEHOLDER] tags for information you cannot determine (e.g., [DATE], [JUDGE NAME]).
5. Maintain continuity with previous sections — do not repeat arguments already made.
6. Use proper legal formatting: topic sentences, IRAC structure where appropriate, block quotes for key evidence.
7. Write substantively and thoroughly — this is a publication-ready filing, not a summary.

OUTPUT:
Return the section content ONLY. Do not include the section heading (it will be added automatically).
"""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    content = response.content if hasattr(response, 'content') else str(response)

    # Extract citations used
    citations_used = []
    if citation_library:
        for c in citation_library:
            case_name = c.get("case_name", "")
            citation = c.get("citation", "")
            if case_name and case_name.lower() in content.lower():
                citations_used.append(c)
            elif citation and citation in content:
                citations_used.append(c)

    return {
        "content": content,
        "citations_used": citations_used,
    }


# ---- Citation Library Builder --------------------------------------------

def build_citation_library(state: AgentState, additional_citations: list = None) -> list:
    """Extract and organize all case citations from case materials.

    Returns: list of {"case_name", "citation", "holding", "relevance", "source"}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=4096)
    if not llm:
        return additional_citations or []

    # Gather all textual materials that might contain citations
    sources = []
    case_summary = state.get("case_summary", "")
    if case_summary:
        sources.append(f"CASE SUMMARY:\n{case_summary[:3000]}")

    research = state.get("legal_research_data", [])
    if research:
        for r in research[:10]:
            if isinstance(r, dict):
                sources.append(f"RESEARCH ({r.get('query', '')}):\n{r.get('summary', '')[:500]}")

    evidence = state.get("evidence_foundations", [])
    if evidence:
        ev_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')}"
            for e in evidence[:15] if isinstance(e, dict)
        )
        sources.append(f"EVIDENCE FOUNDATIONS:\n{ev_text}")

    existing_docs = state.get("drafted_documents", [])
    if existing_docs:
        for d in existing_docs[:5]:
            if isinstance(d, dict):
                sources.append(f"DRAFTED DOC ({d.get('title', '')}):\n{d.get('content', '')[:500]}")

    all_text = "\n\n---\n\n".join(sources)

    prompt = f"""You are a legal citation specialist. Extract ALL case citations, statutes, and legal authorities mentioned in the following case materials.

MATERIALS:
{all_text[:8000]}

TASK:
Identify every legal citation. For each, provide:
- case_name: Full case name (e.g., "Miranda v. Arizona")
- citation: Standard citation (e.g., "384 U.S. 436 (1966)")
- holding: One-sentence summary of the relevant holding
- relevance: How it relates to this case
- source: Where in the materials you found it

Return JSON array ONLY:
[
    {{"case_name": "...", "citation": "...", "holding": "...", "relevance": "...", "source": "..."}},
    ...
]

If no citations are found, return an empty array: []
"""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    result = extract_json(response.content, expect_list=True)

    citations = []
    if isinstance(result, list):
        citations = [c for c in result if isinstance(c, dict) and c.get("case_name")]

    # Merge with additional manually-added citations
    if additional_citations:
        existing_names = {c.get("case_name", "").lower() for c in citations}
        for ac in additional_citations:
            if isinstance(ac, dict) and ac.get("case_name", "").lower() not in existing_names:
                citations.append(ac)

    return citations


# ---- Table of Authorities ------------------------------------------------

def generate_table_of_authorities(sections: list, citation_library: list) -> str:
    """Generate a formatted table of authorities from drafted sections.

    Pure Python — no LLM call. Scans section content for citation references.
    """
    if not citation_library:
        return ""

    # Track which citations appear and on which "pages" (sections)
    found = {}
    for si, sec in enumerate(sections):
        content = sec.get("content", "")
        for cite in citation_library:
            case_name = cite.get("case_name", "")
            citation = cite.get("citation", "")
            key = f"{case_name}, {citation}"
            if case_name and (case_name.lower() in content.lower() or citation in content):
                if key not in found:
                    found[key] = {"cite": cite, "sections": []}
                found[key]["sections"].append(sec.get("section_num", str(si + 1)))

    if not found:
        return "No authorities cited."

    # Categorize
    cases = []
    statutes = []
    other = []

    for key, info in sorted(found.items()):
        cite = info["cite"]
        sections_str = ", ".join(info["sections"])
        entry = f"  {key} .... Section{'s' if len(info['sections']) > 1 else ''} {sections_str}"

        citation_text = cite.get("citation", "").lower()
        if any(kw in citation_text for kw in ["u.s.c.", "stat.", "code", "rev.", "ann."]):
            statutes.append(entry)
        elif any(kw in citation_text for kw in ["u.s.", "f.", "s.ct.", "s.w.", "n.e.", "so.", "a."]):
            cases.append(entry)
        else:
            other.append(entry)

    lines = ["TABLE OF AUTHORITIES", ""]
    if cases:
        lines.append("Cases:")
        lines.extend(cases)
        lines.append("")
    if statutes:
        lines.append("Statutes and Rules:")
        lines.extend(statutes)
        lines.append("")
    if other:
        lines.append("Other Authorities:")
        lines.extend(other)
        lines.append("")

    return "\n".join(lines)


# ---- Smart Brief Review Agent -------------------------------------------

def review_brief(state: AgentState, sections: list, outline: list,
                 citation_library: list, doc_type: str) -> dict:
    """AI review of the assembled brief for quality, consistency, and citations.

    Returns: {"overall_score": int, "grade": str, "issues": [...],
              "strengths": [...], "suggestions": [...]}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    # Assemble full document text
    full_doc = ""
    for sec in sections:
        sec_num = sec.get("section_num", "")
        sec_title = sec.get("title", "")
        content = sec.get("content", "")
        full_doc += f"\n\n--- SECTION {sec_num}: {sec_title} ---\n{content}"

    # Build citation library reference
    cite_names = ", ".join(
        f"{c.get('case_name', '')} {c.get('citation', '')}"
        for c in citation_library
    ) if citation_library else "[No citation library provided]"

    prompt = f"""You are a Senior Appellate Review Attorney conducting a rigorous quality review of a {doc_type}.

CITATION LIBRARY (these are the ONLY authorized citations):
{cite_names}

FULL DOCUMENT:
{full_doc[:20000]}

TASK: Conduct a comprehensive review. Evaluate:

1. **CITATION INTEGRITY**: Are all cited cases from the authorized citation library? Any fabricated or hallucinated citations? Any citations used incorrectly?

2. **LOGICAL FLOW**: Does each section build logically on the previous? Are there contradictions between sections? Is the argument structure coherent?

3. **ARGUMENT COMPLETENESS**: Does the brief adequately address all relevant issues? Are there missing arguments or under-developed points?

4. **STRUCTURAL COMPLIANCE**: Is the structure appropriate for a {doc_type}? Are required sections present?

5. **TONE & STYLE**: Is the tone consistent throughout? Is it appropriately formal and persuasive?

6. **PLACEHOLDERS**: List any remaining [PLACEHOLDER] tags that need to be filled.

7. **FACTUAL CONSISTENCY**: Are facts stated consistently across sections?

Return JSON ONLY:
{{
    "overall_score": 0-100,
    "grade": "A+/A/B/C/D/F",
    "issues": [
        {{"category": "citation|logic|completeness|structure|tone|placeholder|factual",
          "severity": "high|medium|low",
          "section": "section number or 'global'",
          "description": "what the issue is",
          "fix": "suggested fix"}}
    ],
    "strengths": ["strength 1", "strength 2", ...],
    "suggestions": ["suggestion 1", "suggestion 2", ...]
}}
"""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    result = extract_json(response.content)

    if result and isinstance(result, dict) and "overall_score" in result:
        return result

    # Fallback
    return {
        "overall_score": 0,
        "grade": "?",
        "issues": [{"category": "parse_error", "severity": "low", "section": "global",
                     "description": "Could not parse review output", "fix": "Re-run review"}],
        "strengths": [],
        "suggestions": [],
        "raw_response": response.content,
    }


# ---- Opposing Counsel Brief Analyzer -----------------------------------

def analyze_opposing_brief(state: AgentState, opposing_text: str,
                            citation_library: list = None) -> dict:
    """Analyze opposing party's brief: extract arguments, map against evidence, generate counters.

    Returns: {"opponent_arguments": [...], "opponent_citations": [...],
              "counter_arguments": [...], "weaknesses": [...], "response_strategy": "..."}
    """
    llm = get_llm(state.get("current_model"), max_output_tokens=8192)
    if not llm:
        return {"error": "No LLM configured."}

    ctx = get_case_context(state)
    case_summary = state.get("case_summary", "")
    evidence = state.get("evidence_foundations", [])
    strategy = state.get("strategy_notes", "")

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.get('item', '')}: {e.get('admissibility', '')} (source: {e.get('source_ref', '')})"
            for e in evidence[:15] if isinstance(e, dict)
        )

    our_cites = ""
    if citation_library:
        our_cites = "\n".join(
            f"- {c.get('case_name', '')} {c.get('citation', '')}: {c.get('holding', '')[:100]}"
            for c in citation_library
        )

    prompt = f"""You are a Senior Litigation Strategist analyzing the opposing party's brief.

{ctx.get('directives_block', '')}

ROLE: {ctx.get('role', 'Attorney')}
CLIENT: {state.get('client_name', '[Client]')}

OUR CASE SUMMARY:
{case_summary[:3000] if case_summary else '[No summary available]'}

OUR EVIDENCE:
{evidence_text or '[No evidence data]'}

OUR STRATEGY:
{strategy[:2000] if strategy else '[No strategy]'}

OUR CITATION LIBRARY:
{our_cites or '[No citations]'}

OPPOSING PARTY'S BRIEF:
{opposing_text[:15000]}

TASK: Analyze the opposing brief thoroughly.

1. Extract their main arguments (numbered)
2. Identify their key citations and legal authorities
3. Identify their factual claims
4. For each argument, develop a counter-argument using our evidence and law
5. Identify weaknesses in their position
6. Develop an overall response strategy

Return JSON ONLY:
{{
    "opponent_arguments": [
        {{"number": 1, "argument": "...", "section_ref": "...", "strength": "strong|moderate|weak"}}
    ],
    "opponent_citations": [
        {{"case_name": "...", "citation": "...", "purpose": "what they use it for"}}
    ],
    "counter_arguments": [
        {{"opposing_arg_number": 1, "counter": "...", "supporting_evidence": "...", "supporting_law": "..."}}
    ],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "response_strategy": "overall strategic recommendation..."
}}
"""

    response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
    result = extract_json(response.content)

    if result and isinstance(result, dict) and "opponent_arguments" in result:
        return result

    return {
        "opponent_arguments": [],
        "opponent_citations": [],
        "counter_arguments": [],
        "weaknesses": [],
        "response_strategy": response.content[:2000] if hasattr(response, 'content') else "Parse error",
        "raw_response": response.content if hasattr(response, 'content') else "",
    }


# ---- Cross-Model Citation Verification ---------------------------------

def verify_citations_cross_model(state: AgentState, sections: list,
                                   citation_library: list,
                                   verification_model: str = "gemini") -> dict:
    """Verify citations using a DIFFERENT model than the one that drafted.

    Returns: {"verified": [...], "flagged": [...], "summary": "X of Y verified"}
    """
    llm = get_llm(verification_model, max_output_tokens=8192)
    if not llm:
        return {"error": f"Verification model '{verification_model}' not available. Check API key."}

    # Collect citations actually used in sections
    all_text = "\n".join(s.get("content", "") for s in sections)
    used_citations = []
    for c in citation_library:
        name = c.get("case_name", "")
        cite = c.get("citation", "")
        if name and (name.lower() in all_text.lower() or cite in all_text):
            used_citations.append(c)

    if not used_citations:
        return {"verified": [], "flagged": [], "summary": "No citations found in text."}

    # Batch into groups of 5
    results_verified = []
    results_flagged = []

    for batch_start in range(0, len(used_citations), 5):
        batch = used_citations[batch_start:batch_start + 5]

        citations_text = ""
        for i, c in enumerate(batch, 1):
            # Find surrounding context in the brief
            name = c.get("case_name", "")
            context_snippet = ""
            for s in sections:
                content = s.get("content", "")
                idx = content.lower().find(name.lower())
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(content), idx + len(name) + 200)
                    context_snippet = content[start:end]
                    break

            citations_text += f"""
CITATION {i}:
  Case Name: {c.get('case_name', '')}
  Citation: {c.get('citation', '')}
  Claimed Holding: {c.get('holding', '')}
  Context in Brief: "{context_snippet[:300]}"
"""

        prompt = f"""You are a legal citation verification specialist. Your job is to independently verify legal citations. You must be EXTREMELY careful and honest.

For each citation below, verify:
1. Does this case actually exist? (real case name + correct citation)
2. Is the citation format correct (volume, reporter, page, year)?
3. Does the case actually hold what is claimed in the "Claimed Holding"?
4. Is this still good law (not overruled)?

CITATIONS TO VERIFY:
{citations_text}

Return JSON array ONLY — one object per citation:
[
    {{
        "case_name": "...",
        "citation": "...",
        "exists": true/false,
        "citation_correct": true/false,
        "holding_accurate": true/false,
        "still_good_law": true/false,
        "confidence": 0-100,
        "notes": "explanation of any concerns..."
    }}
]
"""

        response = invoke_with_retry(llm, [HumanMessage(content=prompt)])
        batch_results = extract_json(response.content, expect_list=True)

        if isinstance(batch_results, list):
            for vr in batch_results:
                if not isinstance(vr, dict):
                    continue
                # Flagged if any check fails or confidence < 70
                is_flagged = (
                    not vr.get("exists", True)
                    or not vr.get("citation_correct", True)
                    or not vr.get("holding_accurate", True)
                    or not vr.get("still_good_law", True)
                    or vr.get("confidence", 100) < 70
                )
                if is_flagged:
                    results_flagged.append(vr)
                else:
                    results_verified.append(vr)

    total = len(results_verified) + len(results_flagged)
    summary = f"{len(results_verified)} of {total} citations verified"
    if results_flagged:
        summary += f", {len(results_flagged)} flagged for review"

    return {
        "verified": results_verified,
        "flagged": results_flagged,
        "summary": summary,
    }


# ---- Auto-Fetch Case PDFs ---------------------------------------------

def fetch_case_pdfs(citation_library: list, case_id: str, case_mgr) -> dict:
    """Fetch PDF copies of cited cases from free legal databases.

    Best-effort: tries DuckDuckGo + CourtListener. Returns results dict.
    """
    import os
    import re as _re

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

    try:
        import requests
    except ImportError:
        requests = None

    saved = []
    not_found = []
    errors = []

    for cite in citation_library:
        case_name = cite.get("case_name", "")
        citation = cite.get("citation", "")
        if not case_name:
            continue

        safe_name = _re.sub(r'[^\w\s-]', '', case_name).strip().replace(' ', '_')[:60]
        target_filename = f"cited_cases/{safe_name}.pdf"

        # Check if already saved
        existing = case_mgr.get_case_files(case_id)
        if any(target_filename in f or safe_name in os.path.basename(f) for f in existing):
            saved.append({"case_name": case_name, "filename": target_filename, "source": "already exists"})
            continue

        pdf_url = None
        source = ""

        # 1. Try DuckDuckGo search for PDF
        if DDGS is not None and pdf_url is None:
            try:
                ddgs = DDGS()
                query = f'"{case_name}" {citation} filetype:pdf'
                results = list(ddgs.text(query, max_results=5))
                for r in results:
                    url = r.get("href", "") or r.get("link", "")
                    if url.lower().endswith(".pdf"):
                        pdf_url = url
                        source = url.split("/")[2] if "/" in url else "web"
                        break
                    # Check justia, courtlistener, etc.
                    if any(d in url.lower() for d in ["justia.com", "courtlistener.com", "law.cornell.edu"]):
                        pdf_url = url
                        source = url.split("/")[2] if "/" in url else "web"
                        break
            except Exception as e:
                logger.debug("DuckDuckGo search failed for %s: %s", case_name, e)

        # 2. Try CourtListener API
        if pdf_url is None and requests is not None:
            try:
                api_url = f"https://www.courtlistener.com/api/rest/v4/search/?q={citation}&type=o&format=json"
                resp = requests.get(api_url, timeout=10, headers={"User-Agent": "AllRise-Beta/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    results_list = data.get("results", [])
                    if results_list:
                        # Get the absolute_url for the first result
                        abs_url = results_list[0].get("absolute_url", "")
                        if abs_url:
                            pdf_url = f"https://www.courtlistener.com{abs_url}"
                            source = "courtlistener.com"
            except Exception as e:
                logger.debug("CourtListener API failed for %s: %s", case_name, e)

        # 3. Download if URL found
        if pdf_url and requests is not None:
            try:
                resp = requests.get(pdf_url, timeout=30,
                                    headers={"User-Agent": "AllRise-Beta/1.0"},
                                    allow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    case_mgr.save_file(case_id, resp.content, target_filename)
                    saved.append({"case_name": case_name, "filename": target_filename, "source": source})
                    continue
            except Exception as e:
                logger.debug("Download failed for %s: %s", case_name, e)
                errors.append(f"{case_name}: download error — {str(e)[:100]}")
                continue

        not_found.append(case_name)

    return {
        "saved": saved,
        "not_found": not_found,
        "errors": errors,
    }
