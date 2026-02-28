# ---- Graph Construction & Node Registry ------------------------------------
import logging

from langgraph.graph import END, START, StateGraph

from core.state import AgentState
from core.nodes.analysis import (
    analyze_case, develop_strategy, extract_entities,
    generate_consistency_check, generate_devils_advocate,
    generate_elements_map, generate_evidence_foundations,
    generate_investigation_plan, generate_mock_jury,
    generate_timeline, generate_voir_dire,
)
from core.nodes.examination import generate_cross_questions, generate_direct_questions
from core.nodes.research import conduct_legal_research
from core.nodes.civil import generate_medical_chronology, generate_demand_letter

logger = logging.getLogger(__name__)

def build_graph(prep_type: str = "trial"):
    """Builds a prep-type-specific analysis graph.

    - trial: Full graph (all 14 nodes)
    - prelim_hearing: Subset -- no voir dire, mock jury
    - motion_hearing: Minimal -- analyzer -> strategist -> elements + research + investigation
    """
    workflow = StateGraph(AgentState)

    # Core nodes (always included)
    workflow.add_node("analyzer", analyze_case)
    workflow.add_node("strategist", develop_strategy)
    workflow.add_node("elements_mapper", generate_elements_map)
    workflow.add_node("investigation_planner", generate_investigation_plan)
    workflow.add_node("consistency_checker", generate_consistency_check)

    workflow.add_edge(START, "analyzer")
    workflow.add_edge("analyzer", "strategist")

    if prep_type == "motion_hearing":
        # Minimal graph for motion hearings
        workflow.add_node("legal_researcher", conduct_legal_research)
        workflow.add_node("devils_advocate", generate_devils_advocate)

        workflow.add_edge("strategist", "elements_mapper")
        workflow.add_edge("strategist", "consistency_checker")
        workflow.add_edge("strategist", "legal_researcher")
        workflow.add_edge("strategist", "devils_advocate")
        workflow.add_edge("elements_mapper", "investigation_planner")

        workflow.add_edge("investigation_planner", END)
        workflow.add_edge("consistency_checker", END)
        workflow.add_edge("legal_researcher", END)
        workflow.add_edge("devils_advocate", END)

    elif prep_type == "prelim_hearing":
        # Subset graph -- no voir dire, no mock jury, no direct exam
        workflow.add_node("entity_extractor", extract_entities)
        workflow.add_node("cross_examiner", generate_cross_questions)
        workflow.add_node("timeline_generator", generate_timeline)
        workflow.add_node("devils_advocate", generate_devils_advocate)
        workflow.add_node("foundations_agent", generate_evidence_foundations)
        workflow.add_node("legal_researcher", conduct_legal_research)

        workflow.add_edge(START, "entity_extractor")  # Parallel with analyzer

        workflow.add_edge("strategist", "cross_examiner")
        workflow.add_edge("strategist", "timeline_generator")
        workflow.add_edge("strategist", "devils_advocate")
        workflow.add_edge("strategist", "foundations_agent")
        workflow.add_edge("strategist", "consistency_checker")
        workflow.add_edge("strategist", "elements_mapper")
        workflow.add_edge("strategist", "legal_researcher")
        workflow.add_edge("elements_mapper", "investigation_planner")

        workflow.add_edge("cross_examiner", END)
        workflow.add_edge("timeline_generator", END)
        workflow.add_edge("devils_advocate", END)
        workflow.add_edge("foundations_agent", END)
        workflow.add_edge("consistency_checker", END)
        workflow.add_edge("investigation_planner", END)
        workflow.add_edge("entity_extractor", END)
        workflow.add_edge("legal_researcher", END)

    else:
        # Full trial graph (all nodes)
        workflow.add_node("entity_extractor", extract_entities)
        workflow.add_node("voir_dire_agent", generate_voir_dire)
        workflow.add_node("cross_examiner", generate_cross_questions)
        workflow.add_node("direct_examiner", generate_direct_questions)
        workflow.add_node("timeline_generator", generate_timeline)
        workflow.add_node("devils_advocate", generate_devils_advocate)
        workflow.add_node("foundations_agent", generate_evidence_foundations)
        workflow.add_node("mock_jury", generate_mock_jury)
        workflow.add_node("legal_researcher", conduct_legal_research)

        workflow.add_edge(START, "entity_extractor")  # Parallel with analyzer (no dependency on case_summary)
        workflow.add_edge("analyzer", "voir_dire_agent")

        workflow.add_edge("strategist", "cross_examiner")
        workflow.add_edge("strategist", "direct_examiner")
        workflow.add_edge("strategist", "timeline_generator")
        workflow.add_edge("strategist", "devils_advocate")
        workflow.add_edge("strategist", "foundations_agent")
        workflow.add_edge("strategist", "consistency_checker")
        workflow.add_edge("strategist", "elements_mapper")
        workflow.add_edge("strategist", "mock_jury")
        workflow.add_edge("strategist", "legal_researcher")
        workflow.add_edge("elements_mapper", "investigation_planner")

        workflow.add_edge("cross_examiner", END)
        workflow.add_edge("direct_examiner", END)
        workflow.add_edge("timeline_generator", END)
        workflow.add_edge("devils_advocate", END)
        workflow.add_edge("foundations_agent", END)
        workflow.add_edge("consistency_checker", END)
        workflow.add_edge("investigation_planner", END)
        workflow.add_edge("entity_extractor", END)
        workflow.add_edge("voir_dire_agent", END)
        workflow.add_edge("mock_jury", END)
        workflow.add_edge("legal_researcher", END)

    return workflow.compile()


# -- Mapping from node name -> function --------------------------------------

_NODE_FUNCTIONS = {
    "analyzer": analyze_case,
    "strategist": develop_strategy,
    "elements_mapper": generate_elements_map,
    "investigation_planner": generate_investigation_plan,
    "consistency_checker": generate_consistency_check,
    "legal_researcher": conduct_legal_research,
    "devils_advocate": generate_devils_advocate,
    "entity_extractor": extract_entities,
    "cross_examiner": generate_cross_questions,
    "direct_examiner": generate_direct_questions,
    "timeline_generator": generate_timeline,
    "foundations_agent": generate_evidence_foundations,
    "voir_dire_agent": generate_voir_dire,
    "mock_jury": generate_mock_jury,
    "medical_chronology_agent": generate_medical_chronology,
    "demand_letter_agent": generate_demand_letter,
}


def build_graph_selective(selected_nodes: set, prep_type: str = "trial"):
    """Builds a graph containing ONLY the selected nodes.

    'analyzer' and 'strategist' are always included as the core pipeline.
    Other nodes are only added if they appear in selected_nodes.
    If elements_mapper is excluded, investigation_planner is also excluded
    (it depends on elements_mapper).

    Returns (compiled_graph, node_count).
    """
    workflow = StateGraph(AgentState)

    # Core nodes -- always needed for the pipeline
    always_include = {"analyzer", "strategist"}
    active = always_include | (selected_nodes & set(_NODE_FUNCTIONS.keys()))

    # investigation_planner depends on elements_mapper
    if "investigation_planner" in active and "elements_mapper" not in active:
        active.discard("investigation_planner")

    # Determine which nodes are available for this prep type
    if prep_type == "motion_hearing":
        available = {"analyzer", "strategist", "elements_mapper", "investigation_planner",
                     "consistency_checker", "legal_researcher", "devils_advocate"}
    elif prep_type == "prelim_hearing":
        available = {"analyzer", "strategist", "elements_mapper", "investigation_planner",
                     "consistency_checker", "legal_researcher", "devils_advocate",
                     "entity_extractor", "cross_examiner", "timeline_generator",
                     "foundations_agent"}
    else:  # trial
        available = set(_NODE_FUNCTIONS.keys())

    # Only include nodes that are both selected and available for this prep type
    active = active & available

    # Add nodes
    for node_name in active:
        workflow.add_node(node_name, _NODE_FUNCTIONS[node_name])

    # Entry point
    workflow.add_edge(START, "analyzer")
    workflow.add_edge("analyzer", "strategist")

    # entity_extractor runs parallel from START (no dependency on case_summary)
    if "entity_extractor" in active:
        workflow.add_edge(START, "entity_extractor")

    # voir_dire_agent depends on case_summary from analyzer
    if "voir_dire_agent" in active:
        workflow.add_edge("analyzer", "voir_dire_agent")

    # Edges from strategist to its dependents
    strategist_targets = [
        "cross_examiner", "direct_examiner", "timeline_generator",
        "devils_advocate", "foundations_agent", "consistency_checker",
        "elements_mapper", "mock_jury", "legal_researcher",
        "medical_chronology_agent"
    ]
    has_strategist_target = False
    for target in strategist_targets:
        if target in active:
            workflow.add_edge("strategist", target)
            has_strategist_target = True

    # elements_mapper -> investigation_planner dependency
    if "elements_mapper" in active and "investigation_planner" in active:
        workflow.add_edge("elements_mapper", "investigation_planner")

    # Terminal edges to END for all leaf nodes
    leaf_nodes = active - {"analyzer"}  # analyzer always leads to strategist
    # strategist is a leaf only if nothing depends on it
    if not has_strategist_target:
        workflow.add_edge("strategist", END)

    for node_name in active:
        if node_name in ("analyzer", "strategist"):
            continue
        # elements_mapper is not a leaf if investigation_planner follows it
        if node_name == "elements_mapper" and "investigation_planner" in active:
            continue
        workflow.add_edge(node_name, END)

    return workflow.compile(), len(active)

# Node labels for progress display

NODE_LABELS = {
    "analyzer": "Analyzing Case Documents",
    "strategist": "Developing Strategy",
    "elements_mapper": "Mapping Legal Elements",
    "investigation_planner": "Planning Investigation",
    "consistency_checker": "Checking Consistency",
    "legal_researcher": "Conducting Legal Research",
    "devils_advocate": "Running Devil's Advocate",
    "entity_extractor": "Extracting Entities",
    "cross_examiner": "Generating Cross-Examination",
    "direct_examiner": "Generating Direct-Examination",
    "timeline_generator": "Building Timeline",
    "foundations_agent": "Analyzing Evidence Foundations",
    "voir_dire_agent": "Preparing Voir Dire",
    "mock_jury": "Simulating Mock Jury",
}


def get_node_count(prep_type: str = "trial") -> int:
    """Returns the total number of nodes for a given prep type."""
    if prep_type == "motion_hearing":
        return 7
    elif prep_type == "prelim_hearing":
        return 12
    else:
        return 14

# Export the default (trial) compiled graph for backward compat

run_legal_agent = build_graph("trial")


initial_state = {
    "case_files": [],
    "raw_documents": [],
    "case_summary": "",
    "charges": [],
    "strategy_notes": "",
    "devils_advocate_notes": "",
    "evidence_foundations": [],
    "consistency_check": [],
    "legal_elements": [],
    "investigation_plan": [],
    "witnesses": [],
    "timeline": [],
    "cross_examination_plan": [],
    "direct_examination_plan": [],
    "current_model": "xai",
    "statute_text": "",
    "jury_instructions": "",
    "jury_instructions": "",
    "entities": [],
    "relationships": [],
    "voir_dire": {},
    "case_id": "",
    "mock_jury_feedback": [],
    "mock_jury_feedback": [],
    "drafted_documents": [],
    "legal_research_data": [],
    "research_summary": "",
    "strategy_chat_history": [],
    "deposition_analysis": "",
    "case_type": "criminal",
    "medical_records_analysis": {},
    "prep_type": "trial",
    "prep_name": "",
    "client_name": "",
    "attorney_directives": [],
    "media_analysis": {},
    "spreadsheet_analysis": {},
    "medical_chronology": {},
    "demand_letter": {},
}
