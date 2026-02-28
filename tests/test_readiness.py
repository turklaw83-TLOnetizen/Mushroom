# ---- Tests for core/readiness.py ------------------------------------------

import pytest
from core.readiness import (
    compute_readiness_score,
    readiness_color,
    readiness_label,
)


class TestComputeReadinessScore:
    def test_empty_state(self):
        score, grade, breakdown = compute_readiness_score({})
        assert score == 0
        assert grade == "F"
        assert all(not v for v in breakdown.values())

    def test_full_state(self, sample_state):
        score, grade, breakdown = compute_readiness_score(sample_state)
        assert score > 0
        # case_summary, charges, timeline, witnesses, investigation_plan, strategy_notes, entities
        # should all be complete
        completed = [k for k, v in breakdown.items() if v]
        assert len(completed) >= 5

    def test_partial_state(self):
        state = {
            "case_summary": "Some summary",
            "charges": [{"name": "Theft"}],
        }
        score, grade, breakdown = compute_readiness_score(state)
        assert 0 < score < 100

    def test_score_never_exceeds_100(self, sample_state):
        score, grade, breakdown = compute_readiness_score(sample_state)
        assert score <= 100

    def test_breakdown_correct_length(self):
        score, grade, breakdown = compute_readiness_score({})
        assert len(breakdown) == 15

    def test_grade_letters(self):
        # Empty = F
        score, grade, _ = compute_readiness_score({})
        assert grade == "F"

    def test_returns_tuple(self):
        result = compute_readiness_score({})
        assert isinstance(result, tuple)
        assert len(result) == 3


class TestReadinessColor:
    def test_green(self):
        assert readiness_color(85) == "#28a745"

    def test_amber(self):
        assert readiness_color(60) == "#ffc107"

    def test_red(self):
        assert readiness_color(20) == "#dc3545"


class TestReadinessLabel:
    def test_trial_ready(self):
        assert readiness_label(95) == "Trial Ready"

    def test_not_started(self):
        assert readiness_label(10) == "Not Started"

    def test_in_progress(self):
        assert readiness_label(55) == "In Progress"
