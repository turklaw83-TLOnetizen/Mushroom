"""
Tests for core.bg_analysis — background analysis worker utilities.

Covers progress I/O, stale detection, stop/clear, constants, and thread safety.
All tests use monkeypatched DATA_DIR so nothing touches real case data.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta

import pytest

import core.bg_analysis as bg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR to a temp directory for every test."""
    monkeypatch.setattr(bg, "DATA_DIR", str(tmp_path / "data" / "cases"))


@pytest.fixture
def case_id():
    return "case__test_001"


@pytest.fixture
def prep_id():
    return "prep__test_001"


def _make_running_progress(started_at=None, node_started_at=None, **overrides):
    """Helper to build a running-status progress dict."""
    now = datetime.now().isoformat()
    base = {
        "status": "running",
        "nodes_completed": 2,
        "total_nodes": 10,
        "current_node": "strategist",
        "current_description": "Developing defense strategy...",
        "started_at": started_at or now,
        "node_started_at": node_started_at or now,
        "est_tokens_so_far": 500,
        "per_node_times": {},
        "skipped_nodes": [],
        "completed_nodes": ["analyzer", "entity_extractor"],
        "stop_requested": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _progress_path
# ---------------------------------------------------------------------------

class TestProgressPath:
    def test_returns_correct_path_format(self, case_id, prep_id):
        path = bg._progress_path(case_id, prep_id)
        assert path.endswith(os.path.join(
            case_id, "preparations", prep_id, "progress.json"
        ))

    def test_path_lives_under_data_dir(self, case_id, prep_id):
        path = bg._progress_path(case_id, prep_id)
        assert path.startswith(bg.DATA_DIR)


# ---------------------------------------------------------------------------
# _write_progress
# ---------------------------------------------------------------------------

class TestWriteProgress:
    def test_creates_progress_json_at_expected_path(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "running"})
        path = bg._progress_path(case_id, prep_id)
        assert os.path.isfile(path)

    def test_creates_parent_directories(self, case_id, prep_id):
        path = bg._progress_path(case_id, prep_id)
        parent = os.path.dirname(path)
        assert not os.path.exists(parent)
        bg._write_progress(case_id, prep_id, {"status": "running"})
        assert os.path.isdir(parent)

    def test_written_data_is_valid_json(self, case_id, prep_id):
        payload = {"status": "complete", "nodes_completed": 5}
        bg._write_progress(case_id, prep_id, payload)
        path = bg._progress_path(case_id, prep_id)
        with open(path, "r") as f:
            data = json.load(f)
        assert data == payload

    def test_overwrites_existing_progress(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "running"})
        bg._write_progress(case_id, prep_id, {"status": "complete"})
        path = bg._progress_path(case_id, prep_id)
        with open(path, "r") as f:
            data = json.load(f)
        assert data["status"] == "complete"

    def test_thread_safe_concurrent_writes(self, case_id, prep_id):
        """Multiple threads writing simultaneously should not corrupt the file."""
        errors = []

        def writer(n):
            try:
                for i in range(20):
                    bg._write_progress(case_id, prep_id, {
                        "status": "running",
                        "writer": n,
                        "iteration": i,
                    })
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent write errors: {errors}"

        # The final file must be valid JSON
        path = bg._progress_path(case_id, prep_id)
        with open(path, "r") as f:
            data = json.load(f)
        assert data["status"] == "running"


# ---------------------------------------------------------------------------
# get_analysis_progress
# ---------------------------------------------------------------------------

class TestGetAnalysisProgress:
    def test_returns_empty_dict_when_no_file(self, case_id, prep_id):
        assert bg.get_analysis_progress(case_id, prep_id) == {}

    def test_reads_written_progress_correctly(self, case_id, prep_id):
        payload = _make_running_progress()
        bg._write_progress(case_id, prep_id, payload)
        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["status"] == "running"
        assert result["nodes_completed"] == 2
        assert result["current_node"] == "strategist"

    def test_detects_stale_analysis_and_marks_error(self, case_id, prep_id):
        """A running analysis with node_started_at > 5 min ago is stale."""
        old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        payload = _make_running_progress(node_started_at=old_time, started_at=old_time)
        bg._write_progress(case_id, prep_id, payload)

        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["status"] == "error"
        assert "stale" in result.get("error", "").lower()
        assert "completed_at" in result

    def test_does_not_flag_fresh_running_analysis_as_stale(self, case_id, prep_id):
        payload = _make_running_progress()
        bg._write_progress(case_id, prep_id, payload)
        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["status"] == "running"

    def test_handles_corrupted_json_gracefully(self, case_id, prep_id):
        """Corrupted JSON on disk should not raise; returns empty dict."""
        path = bg._progress_path(case_id, prep_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{{{not valid json!!!")
        result = bg.get_analysis_progress(case_id, prep_id)
        # After 3 retries with bad JSON, data stays {} so stale detection
        # is skipped and we just get the empty dict back.
        assert isinstance(result, dict)

    def test_completed_analysis_returned_as_is(self, case_id, prep_id):
        payload = {"status": "complete", "nodes_completed": 14, "total_nodes": 14}
        bg._write_progress(case_id, prep_id, payload)
        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["status"] == "complete"

    def test_stale_detection_uses_started_at_fallback(self, case_id, prep_id):
        """If node_started_at is missing, falls back to started_at."""
        old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        payload = {
            "status": "running",
            "nodes_completed": 0,
            "total_nodes": 10,
            "started_at": old_time,
            "stop_requested": False,
        }
        bg._write_progress(case_id, prep_id, payload)
        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# is_analysis_running
# ---------------------------------------------------------------------------

class TestIsAnalysisRunning:
    def test_returns_false_when_no_progress_file(self, case_id, prep_id):
        assert bg.is_analysis_running(case_id, prep_id) is False

    def test_returns_true_for_fresh_running_analysis(self, case_id, prep_id):
        payload = _make_running_progress()
        bg._write_progress(case_id, prep_id, payload)
        assert bg.is_analysis_running(case_id, prep_id) is True

    def test_returns_false_for_completed_analysis(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "complete"})
        assert bg.is_analysis_running(case_id, prep_id) is False

    def test_returns_false_for_error_status(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "error", "error": "boom"})
        assert bg.is_analysis_running(case_id, prep_id) is False

    def test_returns_false_for_stopped_status(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "stopped"})
        assert bg.is_analysis_running(case_id, prep_id) is False

    def test_detects_stale_and_returns_false(self, case_id, prep_id):
        old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        payload = _make_running_progress(node_started_at=old_time, started_at=old_time)
        bg._write_progress(case_id, prep_id, payload)
        assert bg.is_analysis_running(case_id, prep_id) is False

    def test_stale_detection_writes_error_to_disk(self, case_id, prep_id):
        """After detecting stale, progress.json should reflect error status."""
        old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
        payload = _make_running_progress(node_started_at=old_time, started_at=old_time)
        bg._write_progress(case_id, prep_id, payload)

        bg.is_analysis_running(case_id, prep_id)

        path = bg._progress_path(case_id, prep_id)
        with open(path, "r") as f:
            on_disk = json.load(f)
        assert on_disk["status"] == "error"
        assert "crashed" in on_disk.get("error", "").lower() or "stale" in on_disk.get("error", "").lower()


# ---------------------------------------------------------------------------
# is_any_analysis_running
# ---------------------------------------------------------------------------

class TestIsAnyAnalysisRunning:
    def test_returns_false_for_case_with_no_preps_dir(self, case_id):
        assert bg.is_any_analysis_running(case_id) is False

    def test_returns_false_for_case_with_empty_preps_index(self, case_id):
        preps_dir = os.path.join(bg.DATA_DIR, case_id, "preparations")
        os.makedirs(preps_dir, exist_ok=True)
        with open(os.path.join(preps_dir, "preparations.json"), "w") as f:
            json.dump([], f)
        assert bg.is_any_analysis_running(case_id) is False

    def test_returns_true_when_one_prep_is_running(self, case_id, prep_id):
        # Create preps index
        preps_dir = os.path.join(bg.DATA_DIR, case_id, "preparations")
        os.makedirs(preps_dir, exist_ok=True)
        with open(os.path.join(preps_dir, "preparations.json"), "w") as f:
            json.dump([{"id": prep_id, "name": "Trial Prep"}], f)

        # Write running progress for that prep
        payload = _make_running_progress()
        bg._write_progress(case_id, prep_id, payload)

        assert bg.is_any_analysis_running(case_id) is True

    def test_returns_false_when_all_preps_complete(self, case_id):
        preps_dir = os.path.join(bg.DATA_DIR, case_id, "preparations")
        os.makedirs(preps_dir, exist_ok=True)
        p1, p2 = "prep_a", "prep_b"
        with open(os.path.join(preps_dir, "preparations.json"), "w") as f:
            json.dump([{"id": p1}, {"id": p2}], f)

        bg._write_progress(case_id, p1, {"status": "complete"})
        bg._write_progress(case_id, p2, {"status": "complete"})

        assert bg.is_any_analysis_running(case_id) is False

    def test_handles_missing_preps_index_file(self, case_id):
        """preps dir exists but no preparations.json -> returns False."""
        preps_dir = os.path.join(bg.DATA_DIR, case_id, "preparations")
        os.makedirs(preps_dir, exist_ok=True)
        assert bg.is_any_analysis_running(case_id) is False


# ---------------------------------------------------------------------------
# stop_background_analysis
# ---------------------------------------------------------------------------

class TestStopBackgroundAnalysis:
    def test_sets_stop_requested_flag(self, case_id, prep_id):
        payload = _make_running_progress()
        bg._write_progress(case_id, prep_id, payload)

        bg.stop_background_analysis(case_id, prep_id)

        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["stop_requested"] is True

    def test_noop_when_not_running(self, case_id, prep_id):
        """Stopping a non-running analysis should not create a progress file."""
        bg.stop_background_analysis(case_id, prep_id)
        path = bg._progress_path(case_id, prep_id)
        assert not os.path.exists(path)

    def test_noop_when_already_complete(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "complete"})
        bg.stop_background_analysis(case_id, prep_id)
        result = bg.get_analysis_progress(case_id, prep_id)
        # stop_requested should NOT be set when status != running
        assert result.get("stop_requested") is None or result.get("stop_requested") is False

    def test_preserves_existing_progress_data(self, case_id, prep_id):
        payload = _make_running_progress(nodes_completed=5, total_nodes=14)
        bg._write_progress(case_id, prep_id, payload)

        bg.stop_background_analysis(case_id, prep_id)

        result = bg.get_analysis_progress(case_id, prep_id)
        assert result["stop_requested"] is True
        assert result["nodes_completed"] == 5
        assert result["total_nodes"] == 14


# ---------------------------------------------------------------------------
# clear_progress
# ---------------------------------------------------------------------------

class TestClearProgress:
    def test_removes_progress_file(self, case_id, prep_id):
        bg._write_progress(case_id, prep_id, {"status": "complete"})
        path = bg._progress_path(case_id, prep_id)
        assert os.path.isfile(path)

        bg.clear_progress(case_id, prep_id)
        assert not os.path.exists(path)

    def test_safe_when_file_does_not_exist(self, case_id, prep_id):
        """Should not raise if the file is already gone."""
        bg.clear_progress(case_id, prep_id)  # no error


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

class TestModuleConstants:
    ALL_NODES = [
        "analyzer",
        "strategist",
        "elements_mapper",
        "investigation_planner",
        "consistency_checker",
        "legal_researcher",
        "devils_advocate",
        "entity_extractor",
        "cross_examiner",
        "direct_examiner",
        "timeline_generator",
        "foundations_agent",
        "voir_dire_agent",
        "mock_jury",
    ]

    def test_node_descriptions_has_all_14_nodes(self):
        assert len(bg.NODE_DESCRIPTIONS) == 14
        for node in self.ALL_NODES:
            assert node in bg.NODE_DESCRIPTIONS, f"Missing description for {node}"

    def test_node_descriptions_values_are_nonempty_strings(self):
        for node, desc in bg.NODE_DESCRIPTIONS.items():
            assert isinstance(desc, str) and len(desc) > 0, (
                f"NODE_DESCRIPTIONS[{node!r}] should be a non-empty string"
            )

    def test_node_result_keys_maps_all_14_nodes(self):
        assert len(bg.NODE_RESULT_KEYS) == 14
        for node in self.ALL_NODES:
            assert node in bg.NODE_RESULT_KEYS, f"Missing result keys for {node}"

    def test_node_result_keys_values_are_nonempty_lists(self):
        for node, keys in bg.NODE_RESULT_KEYS.items():
            assert isinstance(keys, list) and len(keys) > 0, (
                f"NODE_RESULT_KEYS[{node!r}] should be a non-empty list"
            )

    def test_node_descriptions_and_result_keys_cover_same_nodes(self):
        assert set(bg.NODE_DESCRIPTIONS.keys()) == set(bg.NODE_RESULT_KEYS.keys())
