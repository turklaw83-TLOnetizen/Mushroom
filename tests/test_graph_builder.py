# ---- Tests for core/nodes/graph_builder.py --------------------------------

import pytest

from core.nodes.graph_builder import (
    NODE_LABELS,
    _NODE_FUNCTIONS,
    build_graph,
    build_graph_selective,
    get_node_count,
    initial_state,
)


# -- All expected node names across the full node registry ------------------

ALL_NODE_NAMES = {
    "analyzer", "strategist", "elements_mapper", "investigation_planner",
    "consistency_checker", "legal_researcher", "devils_advocate",
    "entity_extractor", "cross_examiner", "direct_examiner",
    "timeline_generator", "foundations_agent", "voir_dire_agent", "mock_jury",
}

TRIAL_NODES = ALL_NODE_NAMES  # trial uses all 14
PRELIM_NODES = {
    "analyzer", "strategist", "elements_mapper", "investigation_planner",
    "consistency_checker", "legal_researcher", "devils_advocate",
    "entity_extractor", "cross_examiner", "timeline_generator",
    "foundations_agent",
    # NOTE: prelim has 12 nodes total but only 11 unique names because
    # the count includes the nodes added; see build_graph for details.
}
MOTION_NODES = {
    "analyzer", "strategist", "elements_mapper", "investigation_planner",
    "consistency_checker", "legal_researcher", "devils_advocate",
}


class TestBuildGraph:
    """Tests for build_graph() -- compiles a LangGraph for each prep type."""

    @pytest.mark.parametrize("prep_type", ["trial", "prelim_hearing", "motion_hearing"])
    def test_returns_compiled_graph(self, prep_type):
        graph = build_graph(prep_type)
        # A compiled LangGraph has an invoke method
        assert hasattr(graph, "invoke"), f"Graph for {prep_type} lacks invoke()"

    def test_default_prep_type_is_trial(self):
        graph = build_graph()
        assert hasattr(graph, "invoke")

    @pytest.mark.parametrize("prep_type", ["trial", "prelim_hearing", "motion_hearing"])
    def test_no_exception_for_valid_prep_types(self, prep_type):
        # Should complete without raising
        build_graph(prep_type)

    def test_unknown_prep_type_defaults_to_trial(self):
        # The else branch handles unknown prep types identically to trial
        graph = build_graph("some_unknown_type")
        assert hasattr(graph, "invoke")


class TestGetNodeCount:
    """Tests for get_node_count() -- expected counts per prep type."""

    def test_trial_has_14_nodes(self):
        assert get_node_count("trial") == 14

    def test_prelim_has_12_nodes(self):
        assert get_node_count("prelim_hearing") == 12

    def test_motion_has_7_nodes(self):
        assert get_node_count("motion_hearing") == 7

    def test_default_is_trial(self):
        assert get_node_count() == 14

    def test_unknown_defaults_to_trial(self):
        assert get_node_count("something_else") == 14


class TestNodeLabels:
    """Tests for NODE_LABELS constant."""

    def test_has_all_expected_nodes(self):
        for node_name in ALL_NODE_NAMES:
            assert node_name in NODE_LABELS, f"Missing label for {node_name}"

    def test_all_labels_are_non_empty_strings(self):
        for node_name, label in NODE_LABELS.items():
            assert isinstance(label, str), f"Label for {node_name} is not a string"
            assert len(label) > 0, f"Label for {node_name} is empty"

    def test_label_count_matches_all_nodes(self):
        assert len(NODE_LABELS) == len(ALL_NODE_NAMES)


class TestNodeFunctions:
    """Tests for _NODE_FUNCTIONS constant -- maps node names to callables."""

    def test_all_standard_nodes_have_functions(self):
        for node_name in ALL_NODE_NAMES:
            assert node_name in _NODE_FUNCTIONS, f"Missing function for {node_name}"

    def test_all_values_are_callable(self):
        for node_name, func in _NODE_FUNCTIONS.items():
            assert callable(func), f"Function for {node_name} is not callable"

    def test_includes_civil_nodes(self):
        # _NODE_FUNCTIONS has extra civil-specific nodes beyond the base 14
        assert "medical_chronology_agent" in _NODE_FUNCTIONS
        assert "demand_letter_agent" in _NODE_FUNCTIONS

    def test_superset_of_all_node_names(self):
        # _NODE_FUNCTIONS includes the 14 standard nodes plus civil extras
        assert ALL_NODE_NAMES.issubset(set(_NODE_FUNCTIONS.keys()))


class TestBuildGraphSelective:
    """Tests for build_graph_selective() -- builds a graph with only selected nodes."""

    def test_always_includes_analyzer_and_strategist(self):
        # Even with an empty selected set, core nodes are present
        graph, count = build_graph_selective(set(), "trial")
        assert count >= 2  # at least analyzer + strategist

    def test_empty_set_returns_just_core_nodes(self):
        graph, count = build_graph_selective(set(), "trial")
        # Only analyzer and strategist should be active
        assert count == 2

    def test_returns_compiled_graph(self):
        graph, count = build_graph_selective({"elements_mapper"}, "trial")
        assert hasattr(graph, "invoke")

    def test_returns_correct_count(self):
        selected = {"elements_mapper", "investigation_planner", "devils_advocate"}
        graph, count = build_graph_selective(selected, "trial")
        # analyzer + strategist + 3 selected = 5
        assert count == 5

    def test_removes_investigation_planner_when_elements_mapper_excluded(self):
        # investigation_planner depends on elements_mapper, so it must be dropped
        selected = {"investigation_planner"}
        graph, count = build_graph_selective(selected, "trial")
        # Should only have analyzer + strategist (investigation_planner discarded)
        assert count == 2

    def test_keeps_investigation_planner_when_elements_mapper_included(self):
        selected = {"elements_mapper", "investigation_planner"}
        graph, count = build_graph_selective(selected, "trial")
        # analyzer + strategist + elements_mapper + investigation_planner = 4
        assert count == 4

    def test_respects_motion_prep_type_availability(self):
        # Requesting trial-only nodes under motion should exclude them
        selected = {"voir_dire_agent", "mock_jury", "cross_examiner", "devils_advocate"}
        graph, count = build_graph_selective(selected, "motion_hearing")
        # Only devils_advocate is available for motion (plus core analyzer + strategist)
        assert count == 3  # analyzer + strategist + devils_advocate

    def test_respects_prelim_prep_type_availability(self):
        # voir_dire and mock_jury are not available in prelim
        selected = {"voir_dire_agent", "mock_jury", "cross_examiner"}
        graph, count = build_graph_selective(selected, "prelim_hearing")
        # cross_examiner is available, voir_dire and mock_jury are not
        assert count == 3  # analyzer + strategist + cross_examiner

    def test_trial_allows_all_standard_nodes(self):
        graph, count = build_graph_selective(ALL_NODE_NAMES, "trial")
        assert count == len(ALL_NODE_NAMES)

    def test_ignores_unknown_node_names(self):
        selected = {"nonexistent_node", "another_fake"}
        graph, count = build_graph_selective(selected, "trial")
        # Unknown names are silently ignored; only core nodes remain
        assert count == 2

    def test_entity_extractor_parallel_from_start(self):
        # entity_extractor should run parallel with analyzer from START
        # If included, the graph should compile without errors
        selected = {"entity_extractor"}
        graph, count = build_graph_selective(selected, "trial")
        assert count == 3  # analyzer + strategist + entity_extractor

    def test_voir_dire_depends_on_analyzer(self):
        # voir_dire_agent gets an edge from analyzer; should compile fine
        selected = {"voir_dire_agent"}
        graph, count = build_graph_selective(selected, "trial")
        assert count == 3  # analyzer + strategist + voir_dire_agent

    def test_all_strategist_targets_compile(self):
        # Each node that depends on strategist should compile individually
        strategist_targets = [
            "cross_examiner", "direct_examiner", "timeline_generator",
            "devils_advocate", "foundations_agent", "consistency_checker",
            "elements_mapper", "mock_jury", "legal_researcher",
        ]
        for target in strategist_targets:
            graph, count = build_graph_selective({target}, "trial")
            assert count == 3, f"Expected 3 nodes for {target}, got {count}"
            assert hasattr(graph, "invoke"), f"Graph with {target} failed to compile"


class TestInitialState:
    """Tests for the initial_state constant."""

    def test_has_all_required_keys(self):
        required_keys = [
            "case_files", "raw_documents", "case_summary", "charges",
            "strategy_notes", "devils_advocate_notes", "evidence_foundations",
            "consistency_check", "legal_elements", "investigation_plan",
            "witnesses", "timeline", "cross_examination_plan",
            "direct_examination_plan", "current_model", "entities",
            "relationships", "voir_dire", "case_id", "mock_jury_feedback",
            "drafted_documents", "legal_research_data", "research_summary",
            "strategy_chat_history", "deposition_analysis", "case_type",
            "prep_type", "prep_name", "client_name", "attorney_directives",
            "medical_records_analysis", "medical_chronology", "demand_letter",
            "media_analysis", "spreadsheet_analysis",
        ]
        for key in required_keys:
            assert key in initial_state, f"Missing required key: {key}"

    def test_list_keys_are_lists(self):
        list_keys = [
            "case_files", "raw_documents", "charges", "evidence_foundations",
            "consistency_check", "legal_elements", "investigation_plan",
            "witnesses", "timeline", "cross_examination_plan",
            "direct_examination_plan", "entities", "relationships",
            "mock_jury_feedback", "drafted_documents", "legal_research_data",
            "strategy_chat_history", "attorney_directives",
        ]
        for key in list_keys:
            assert isinstance(initial_state[key], list), f"{key} should be a list"

    def test_dict_keys_are_dicts(self):
        dict_keys = [
            "voir_dire", "medical_records_analysis", "medical_chronology",
            "demand_letter", "media_analysis", "spreadsheet_analysis",
        ]
        for key in dict_keys:
            assert isinstance(initial_state[key], dict), f"{key} should be a dict"

    def test_string_keys_are_strings(self):
        string_keys = [
            "case_summary", "strategy_notes", "devils_advocate_notes",
            "current_model", "case_id", "research_summary",
            "deposition_analysis", "case_type", "prep_type", "prep_name",
            "client_name",
        ]
        for key in string_keys:
            assert isinstance(initial_state[key], str), f"{key} should be a string"

    def test_default_model_is_xai(self):
        assert initial_state["current_model"] == "xai"

    def test_default_case_type_is_criminal(self):
        assert initial_state["case_type"] == "criminal"

    def test_default_prep_type_is_trial(self):
        assert initial_state["prep_type"] == "trial"

    def test_all_lists_start_empty(self):
        for key, value in initial_state.items():
            if isinstance(value, list):
                assert len(value) == 0, f"{key} should start empty"

    def test_all_dicts_start_empty(self):
        for key, value in initial_state.items():
            if isinstance(value, dict):
                assert len(value) == 0, f"{key} should start empty"
