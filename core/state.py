# ---- Agent State & Case Context ------------------------------------------
# AgentState TypedDict for LangGraph, case-type context system, and
# streaming callback infrastructure.

import logging
import threading as _threading
from typing import Any, Dict, List, TypedDict

from core.config import CONFIG

logger = logging.getLogger(__name__)


# ---- State Definition ----------------------------------------------------

class AgentState(TypedDict):
    """
    Represents the state of the legal analysis workflow.
    Used by LangGraph as the shared state dict for the analysis DAG.
    """
    case_files: List[str]
    raw_documents: List[Any]           # LangChain Document objects
    case_summary: str
    charges: List[Dict]                # [{name, statute_number, level, class, statute_text, jury_instructions}]
    strategy_notes: str                # Markdown
    devils_advocate_notes: str
    evidence_foundations: List[Dict]    # [{item, admissibility, attack, source_ref}]
    consistency_check: List[Dict]      # [{fact, source_a, source_b, notes}]
    legal_elements: List[Dict]         # [{charge, element, evidence, strength}]
    investigation_plan: List[Dict]     # [{action, reason, priority}]
    witnesses: List[Dict]              # [{name, type, goal, contact_info}]
    timeline: List[Dict]               # [{year, month, day, time, headline, text, source}]
    cross_examination_plan: List[Dict]
    direct_examination_plan: List[Dict]
    current_model: str
    max_context_mode: bool
    entities: List[Dict]               # [{id, type, context, source_ref}]
    voir_dire: Dict                    # {ideal_juror, red_flags, questions: [{question, goal}]}
    witness_contacts: List[Dict]
    case_id: str
    relationships: List[Dict]          # [{source, target, relation, source_ref}]
    mock_jury_feedback: List[Dict]     # [{juror, verdict, reaction}]
    drafted_documents: List[Dict]
    legal_research_data: List[Dict]
    research_summary: str
    strategy_chat_history: List[Dict]
    deposition_analysis: str
    case_type: str                     # criminal/criminal-juvenile/civil-plaintiff/civil-defendant/civil-juvenile
    medical_records_analysis: Dict
    medical_chronology: Dict
    demand_letter: Dict
    prep_type: str                     # trial/prelim_hearing/motion_hearing
    prep_name: str
    client_name: str
    attorney_directives: List[Dict]    # [{text, category}]
    media_analysis: Dict
    spreadsheet_analysis: Dict
    major_document_drafts: List[Dict]  # [{id, doc_type, title, outline, sections, citation_library, status, ...}]


# ---- Case Type Context ---------------------------------------------------

def get_case_context(state: dict) -> dict:
    """
    Returns role-appropriate terminology based on the case type.
    Allows all prompts to dynamically adapt to criminal or civil cases.
    """
    case_type = state.get("case_type", "criminal")

    if case_type == "civil-plaintiff":
        context = {
            "role": "plaintiff's litigation attorney",
            "opponent": "the defendant",
            "our_side": "the plaintiff",
            "our_party": "Plaintiff",
            "claims_label": "claims / causes of action",
            "burden": "preponderance of the evidence",
            "case_type_desc": "Civil (Plaintiff)",
            "analyze_instruction": "List all potential claims and causes of action. Summarize the defendant's likely defenses. List all individuals mentioned.",
            "doc_types": "Complaints, Contracts, Correspondence, Medical Records",
            "strategy_role": "Senior Litigation Strategist (Plaintiff Side)",
            "devil_role": "You are a skilled defense attorney. Review the plaintiff's litigation strategy and identify every weakness.",
            "evidence_goal": "Analyze evidence supporting the plaintiff's claims",
            "search_prefix": "Civil litigation",
        }
    elif case_type == "civil-defendant":
        context = {
            "role": "civil defense litigation attorney",
            "opponent": "the plaintiff",
            "our_side": "the defendant",
            "our_party": "Defendant",
            "claims_label": "claims against our client",
            "burden": "preponderance of the evidence (plaintiff's burden)",
            "case_type_desc": "Civil (Defense)",
            "analyze_instruction": "List all claims alleged against our client. Summarize the plaintiff's theory of liability. List all individuals mentioned.",
            "doc_types": "Complaints, Answers, Contracts, Discovery Documents",
            "strategy_role": "Senior Defense Strategist (Civil Defense)",
            "devil_role": "You are a skilled plaintiff's attorney. Review the defense strategy and identify every weakness.",
            "evidence_goal": "Analyze evidence that undermines the plaintiff's claims or supports our defenses",
            "search_prefix": "Civil defense",
        }
    elif case_type == "civil-juvenile":
        context = {
            "role": "juvenile civil litigation attorney",
            "opponent": "the opposing party",
            "our_side": "the juvenile / family",
            "our_party": "Juvenile/Family",
            "claims_label": "claims / petitions",
            "burden": "preponderance of the evidence",
            "case_type_desc": "Civil (Juvenile)",
            "analyze_instruction": "List all claims or petitions filed. Identify the juvenile's best interests. Summarize the opposing party's position. List all individuals mentioned including guardians ad litem.",
            "doc_types": "Petitions, Social Worker Reports, School Records, Medical Records, Guardian ad Litem Reports",
            "strategy_role": "Juvenile Civil Advocate",
            "devil_role": "You are a skilled opposing counsel in juvenile proceedings. Review the strategy and identify every weakness, focusing on the best-interests standard.",
            "evidence_goal": "Analyze evidence supporting the juvenile's best interests and the family's position",
            "search_prefix": "Juvenile civil proceedings",
        }
    elif case_type == "criminal-juvenile":
        context = {
            "role": "juvenile defense attorney",
            "opponent": "the prosecution / State",
            "our_side": "the juvenile respondent",
            "our_party": "Juvenile Respondent",
            "claims_label": "delinquency allegations",
            "burden": "beyond a reasonable doubt",
            "case_type_desc": "Criminal (Juvenile)",
            "analyze_instruction": "List all delinquency allegations. Summarize the prosecution's theory. List all individuals mentioned including probation officers and guardians. Note any diversion or rehabilitative options.",
            "doc_types": "Petitions, Police Reports, Probation Reports, School Records, Psychological Evaluations",
            "strategy_role": "Juvenile Defense Strategist",
            "devil_role": "You are a skilled juvenile prosecutor. Review the defense strategy and identify every weakness, considering both adjudication risk and disposition alternatives.",
            "evidence_goal": "Analyze evidence for admissibility and defense value, with special attention to rehabilitative alternatives and mitigating factors",
            "search_prefix": "Juvenile criminal defense strategy for",
        }
    else:  # criminal (default)
        context = {
            "role": "expert criminal defense attorney",
            "opponent": "the prosecution",
            "our_side": "the defense",
            "our_party": "Defendant",
            "claims_label": "charges",
            "burden": "beyond a reasonable doubt",
            "case_type_desc": "Criminal Defense",
            "analyze_instruction": "List all potential charges. Summarize the prosecution's theory of the case. List all individuals mentioned.",
            "doc_types": "Affidavits/Police Reports",
            "strategy_role": "Senior Defense Strategist",
            "devil_role": "You are a skilled Prosecutor. Review the proposed Defense Strategy and identify every weakness.",
            "evidence_goal": "Analyze evidence for admissibility and defense value",
            "search_prefix": "Criminal defense strategy for",
        }

    # -- Inject client identity when set --
    client_name = state.get("client_name", "")
    if client_name:
        context["client_name"] = client_name
        context["our_side"] = f"{context['our_side']} ({client_name})"
        context["analyze_instruction"] += f" Our client is specifically: {client_name}. Orient all analysis from their perspective."
    else:
        context["client_name"] = ""

    # -- Overlay prep-type-specific context --
    prep_type = state.get("prep_type", "trial")
    prep_name = state.get("prep_name", "")

    if prep_type == "prelim_hearing":
        context["burden"] = "probable cause"
        context["strategy_role"] = f"Preliminary Hearing Strategist ({context['case_type_desc']})"
        context["analyze_instruction"] += " Focus specifically on whether probable cause exists for each element."
        context["evidence_goal"] = "Analyze whether the State can establish PROBABLE CAUSE for each element"
        context["prep_label"] = "Preliminary Hearing"
    elif prep_type == "motion_hearing":
        motion_title = prep_name or "Motion"
        context["strategy_role"] = f"Motion Advocate -- {motion_title}"
        context["analyze_instruction"] = f"Focus analysis specifically on the legal issues relevant to: {motion_title}. Identify the key facts, legal standards, and arguments."
        context["evidence_goal"] = f"Analyze evidence relevant to {motion_title}"
        context["search_prefix"] = f"{context['search_prefix']} {motion_title}"
        context["prep_label"] = motion_title
    else:
        context["prep_label"] = "Trial"

    # -- Attorney Directives -- highest-priority override --
    directives = state.get("attorney_directives", [])
    if directives:
        _category_labels = {
            "fact": "ESTABLISHED FACT",
            "strategy": "STRATEGIC DIRECTION",
            "instruction": "INSTRUCTION",
        }
        lines = []
        for d in directives:
            label = _category_labels.get(d.get("category", "instruction"), "INSTRUCTION")
            lines.append(f"[{label}] {d.get('text', '')}")
        block = (
            "\n\n[!] ATTORNEY DIRECTIVES -- THESE OVERRIDE ALL OTHER ANALYSIS [!]\n"
            "The following instructions come directly from the attorney on this case.\n"
            "You MUST treat stated facts as TRUE regardless of what documents say.\n"
            "You MUST follow strategic directions exactly.\n"
            "You MUST obey all instructions without question.\n\n"
            + "\n".join(lines) + "\n"
        )
        context["directives_block"] = block
    else:
        context["directives_block"] = ""

    # -- Attorney Module Notes -- persistent notes injected into re-analysis --
    module_notes = state.get("_attorney_module_notes", {})
    if module_notes:
        note_lines = []
        for module_name, note_text in module_notes.items():
            if note_text and note_text.strip():
                label = module_name.replace("_", " ").title()
                note_lines.append(f"[{label}] {note_text.strip()}")
        if note_lines:
            context["module_notes_block"] = (
                "\n\n[ATTORNEY MODULE NOTES]\n"
                "The attorney has left the following notes on previous analysis results.\n"
                "You MUST take these notes into account. They may contain corrections,\n"
                "additional context, or strategic guidance for this specific module.\n\n"
                + "\n".join(note_lines) + "\n"
            )
        else:
            context["module_notes_block"] = ""
    else:
        context["module_notes_block"] = ""

    return context


# ---- Streaming Callback Infrastructure -----------------------------------
# Uses threading.local() so each thread has its own callback.
# This prevents multi-case analysis threads from clobbering each other's
# stream callbacks when running concurrently.

_stream_local = _threading.local()


def set_stream_callback(fn):
    """Set a per-thread callback that receives every LLM token as it's generated.

    Each thread gets its own callback, so concurrent analysis runs on
    different cases never interfere with each other.
    """
    _stream_local.callback = fn


def clear_stream_callback():
    """Remove the per-thread streaming callback."""
    _stream_local.callback = None


def get_stream_callback():
    """Return the current thread's streaming callback (or None)."""
    return getattr(_stream_local, "callback", None)
