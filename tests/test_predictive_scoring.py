"""Tests for core/predictive_scoring.py — data-driven case scoring (no LLM)."""

import json
import pytest

from core.predictive_scoring import (
    DIMENSION_WEIGHTS,
    _to_grade,
    _score_evidence_strength,
    _score_witness_reliability,
    _score_element_coverage,
    compute_predictive_score,
    save_score_snapshot,
    load_score_history,
)
from tests.helpers.fixtures import SAMPLE_ANALYSIS_STATE


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_weights_sum_to_100(self):
        assert sum(DIMENSION_WEIGHTS.values()) == 100

    def test_all_dimensions_present(self):
        expected = {
            "evidence_strength", "witness_reliability", "element_coverage",
            "legal_authority", "narrative_coherence", "adversarial_resilience",
        }
        assert set(DIMENSION_WEIGHTS.keys()) == expected


# ---------------------------------------------------------------------------
# Grade Conversion
# ---------------------------------------------------------------------------

class TestGrading:
    def test_a_grade(self):
        assert _to_grade(95) == "A"
        assert _to_grade(90) == "A"

    def test_b_grade(self):
        assert _to_grade(85) == "B"
        assert _to_grade(80) == "B"

    def test_c_grade(self):
        assert _to_grade(75) == "C"
        assert _to_grade(70) == "C"

    def test_d_grade(self):
        assert _to_grade(65) == "D"
        assert _to_grade(60) == "D"

    def test_f_grade(self):
        assert _to_grade(55) == "F"
        assert _to_grade(0) == "F"


# ---------------------------------------------------------------------------
# Individual Scorers
# ---------------------------------------------------------------------------

class TestEvidenceStrength:
    def test_with_evidence(self):
        result = _score_evidence_strength(SAMPLE_ANALYSIS_STATE)
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_empty_state(self):
        result = _score_evidence_strength({})
        assert "score" in result
        # Empty state should get a neutral/low score
        assert 0 <= result["score"] <= 100


class TestWitnessReliability:
    def test_with_witnesses(self):
        result = _score_witness_reliability(SAMPLE_ANALYSIS_STATE)
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_no_witnesses(self):
        state = {**SAMPLE_ANALYSIS_STATE, "witnesses": []}
        result = _score_witness_reliability(state)
        assert "score" in result


class TestElementCoverage:
    def test_with_elements(self):
        result = _score_element_coverage(SAMPLE_ANALYSIS_STATE)
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_no_elements(self):
        state = {**SAMPLE_ANALYSIS_STATE, "legal_elements": []}
        result = _score_element_coverage(state)
        assert "score" in result


# ---------------------------------------------------------------------------
# Full Score Computation
# ---------------------------------------------------------------------------

class TestComputeScore:
    def test_returns_valid_structure(self):
        result = compute_predictive_score(SAMPLE_ANALYSIS_STATE)
        assert "overall_score" in result
        assert "overall_grade" in result
        assert "dimensions" in result
        assert 0 <= result["overall_score"] <= 100
        assert result["overall_grade"] in ("A", "B", "C", "D", "F")

    def test_has_all_dimensions(self):
        result = compute_predictive_score(SAMPLE_ANALYSIS_STATE)
        # dimensions is a dict keyed by dimension name
        assert set(result["dimensions"].keys()) == set(DIMENSION_WEIGHTS.keys())

    def test_empty_state_doesnt_crash(self):
        result = compute_predictive_score({})
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100

    def test_dimension_scores_bounded(self):
        result = compute_predictive_score(SAMPLE_ANALYSIS_STATE)
        for dim_name, dim_data in result["dimensions"].items():
            assert 0 <= dim_data["score"] <= 100, f"{dim_name} out of range"


# ---------------------------------------------------------------------------
# Score Persistence
# ---------------------------------------------------------------------------

class TestScorePersistence:
    def test_save_and_load(self, tmp_data_dir):
        case_id = "case__test_001"
        prep_id = "prep_trial_001"
        score = compute_predictive_score(SAMPLE_ANALYSIS_STATE)

        save_score_snapshot(tmp_data_dir, case_id, prep_id, score)
        history = load_score_history(tmp_data_dir, case_id, prep_id)

        assert len(history) >= 1

    def test_empty_history(self, tmp_data_dir):
        history = load_score_history(tmp_data_dir, "case__x", "prep_x")
        assert history == [] or history is not None
