"""
core.nodes -- Legal analysis node functions.

This package was split from the original monolithic nodes.py for maintainability.
All public symbols are re-exported here so existing imports continue to work:
    from core.nodes import analyze_case  # works

PERFORMANCE: Uses lazy callables so that ``from core.nodes import X`` is instant.
The heavy LangChain / LLM imports only happen when a function is first *called*,
not when it is imported.  This cuts ~25 seconds from first-page-load time.
"""

import importlib


class _Lazy:
    """Proxy that defers the real import until the function is called."""
    __slots__ = ("_mod_path", "_name", "_real")

    def __init__(self, mod_path: str, name: str):
        object.__setattr__(self, "_mod_path", mod_path)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_real", None)

    def _resolve(self):
        real = object.__getattribute__(self, "_real")
        if real is None:
            mod = importlib.import_module(object.__getattribute__(self, "_mod_path"))
            real = getattr(mod, object.__getattribute__(self, "_name"))
            object.__setattr__(self, "_real", real)
        return real

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __repr__(self):
        return f"<lazy {self._mod_path}.{self._name}>"


# ---- Lazy-exported symbols ------------------------------------------------
# Mapping: name -> (module_path, real_name)

# Common utilities
CITATION_INSTRUCTION = _Lazy("core.nodes._common", "CITATION_INSTRUCTION")
extract_json = _Lazy("core.nodes._common", "extract_json")
format_docs_with_sources = _Lazy("core.nodes._common", "format_docs_with_sources")

# Core analysis pipeline nodes
analyze_case = _Lazy("core.nodes.analysis", "analyze_case")
develop_strategy = _Lazy("core.nodes.analysis", "develop_strategy")
extract_entities = _Lazy("core.nodes.analysis", "extract_entities")
generate_consistency_check = _Lazy("core.nodes.analysis", "generate_consistency_check")
generate_devils_advocate = _Lazy("core.nodes.analysis", "generate_devils_advocate")
generate_elements_map = _Lazy("core.nodes.analysis", "generate_elements_map")
generate_evidence_foundations = _Lazy("core.nodes.analysis", "generate_evidence_foundations")
generate_investigation_plan = _Lazy("core.nodes.analysis", "generate_investigation_plan")
generate_mock_jury = _Lazy("core.nodes.analysis", "generate_mock_jury")
generate_timeline = _Lazy("core.nodes.analysis", "generate_timeline")
generate_voir_dire = _Lazy("core.nodes.analysis", "generate_voir_dire")
refine_strategy = _Lazy("core.nodes.analysis", "refine_strategy")

# Witness/examination functions
analyze_deposition = _Lazy("core.nodes.examination", "analyze_deposition")
generate_cross_questions = _Lazy("core.nodes.examination", "generate_cross_questions")
generate_deposition_outline = _Lazy("core.nodes.examination", "generate_deposition_outline")
generate_direct_questions = _Lazy("core.nodes.examination", "generate_direct_questions")
generate_interview_plan = _Lazy("core.nodes.examination", "generate_interview_plan")
generate_witness_prep = _Lazy("core.nodes.examination", "generate_witness_prep")

# Research & drafting
analyze_lexis_results = _Lazy("core.nodes.research", "analyze_lexis_results")
challenge_finding = _Lazy("core.nodes.research", "challenge_finding")
conduct_legal_research = _Lazy("core.nodes.research", "conduct_legal_research")
generate_cheat_sheet = _Lazy("core.nodes.research", "generate_cheat_sheet")
generate_client_report = _Lazy("core.nodes.research", "generate_client_report")
generate_draft_document = _Lazy("core.nodes.research", "generate_draft_document")
generate_lexis_queries = _Lazy("core.nodes.research", "generate_lexis_queries")
generate_statements = _Lazy("core.nodes.research", "generate_statements")

# Civil / specialized tools
analyze_media_forensic = _Lazy("core.nodes.civil", "analyze_media_forensic")
analyze_medical_records = _Lazy("core.nodes.civil", "analyze_medical_records")
analyze_spreadsheet = _Lazy("core.nodes.civil", "analyze_spreadsheet")
compare_documents = _Lazy("core.nodes.civil", "compare_documents")
generate_demand_letter = _Lazy("core.nodes.civil", "generate_demand_letter")
generate_medical_chronology = _Lazy("core.nodes.civil", "generate_medical_chronology")

# Exhibit/utility/conflict tools
evaluate_case_theory = _Lazy("core.nodes.tools", "evaluate_case_theory")
evaluate_missing_discovery = _Lazy("core.nodes.tools", "evaluate_missing_discovery")
generate_cross_reference_matrix = _Lazy("core.nodes.tools", "generate_cross_reference_matrix")
generate_exhibit_list = _Lazy("core.nodes.tools", "generate_exhibit_list")
generate_exhibit_plan = _Lazy("core.nodes.tools", "generate_exhibit_plan")
generate_jury_instructions = _Lazy("core.nodes.tools", "generate_jury_instructions")
predict_opponent_strategy = _Lazy("core.nodes.tools", "predict_opponent_strategy")
process_voice_note = _Lazy("core.nodes.tools", "process_voice_note")
scan_conflicts = _Lazy("core.nodes.tools", "scan_conflicts")

# Major document drafting
generate_document_outline = _Lazy("core.nodes.major_docs", "generate_document_outline")
draft_document_section = _Lazy("core.nodes.major_docs", "draft_document_section")
build_citation_library = _Lazy("core.nodes.major_docs", "build_citation_library")
generate_table_of_authorities = _Lazy("core.nodes.major_docs", "generate_table_of_authorities")
review_brief = _Lazy("core.nodes.major_docs", "review_brief")
analyze_opposing_brief = _Lazy("core.nodes.major_docs", "analyze_opposing_brief")
verify_citations_cross_model = _Lazy("core.nodes.major_docs", "verify_citations_cross_model")
fetch_case_pdfs = _Lazy("core.nodes.major_docs", "fetch_case_pdfs")

# Graph construction & registry
NODE_LABELS = _Lazy("core.nodes.graph_builder", "NODE_LABELS")
_NODE_FUNCTIONS = _Lazy("core.nodes.graph_builder", "_NODE_FUNCTIONS")
build_graph = _Lazy("core.nodes.graph_builder", "build_graph")
build_graph_selective = _Lazy("core.nodes.graph_builder", "build_graph_selective")
get_node_count = _Lazy("core.nodes.graph_builder", "get_node_count")
initial_state = _Lazy("core.nodes.graph_builder", "initial_state")
