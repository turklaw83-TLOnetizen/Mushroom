"""Tests for background worker safety mechanisms.

Covers stale detection, heartbeat, concurrent start prevention,
and atomic progress file writes across:
  - core/bg_analysis.py
  - core/ingestion_worker.py
  - core/ocr_worker.py
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def case_dirs(tmp_path):
    """Create a minimal case directory layout for progress/status files."""
    case_id = "test_case__abc"
    prep_id = "prep_001"

    case_dir = tmp_path / "data" / "cases" / case_id
    prep_dir = case_dir / "preparations" / prep_id
    prep_dir.mkdir(parents=True)

    return {
        "data_dir": str(tmp_path / "data" / "cases"),
        "case_dir": str(case_dir),
        "case_id": case_id,
        "prep_id": prep_id,
        "prep_dir": str(prep_dir),
    }


# ===========================================================================
# 1. bg_analysis.py  --  stale detection, atomic writes, concurrent guard
# ===========================================================================


class TestBgAnalysisStaleDetection:
    """Verify that get_analysis_progress resets stale 'running' states."""

    def test_stale_running_resets_to_error(self, case_dirs):
        """A progress stuck 'running' for >5 min should auto-correct to 'error'."""
        from core import bg_analysis

        # Temporarily override the DATA_DIR used by bg_analysis
        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            prep_id = case_dirs["prep_id"]

            # Write a progress file that looks stale (started 10 min ago, no update)
            stale_time = (datetime.now() - timedelta(minutes=10)).isoformat()
            progress = {
                "status": "running",
                "started_at": stale_time,
                "node_started_at": stale_time,
                "nodes_completed": 3,
                "total_nodes": 14,
                "current_node": "strategist",
            }
            path = bg_analysis._progress_path(case_id, prep_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(progress, f)

            # Reading progress should detect stale and fix it
            result = bg_analysis.get_analysis_progress(case_id, prep_id)
            assert result["status"] == "error"
            assert "stale" in result.get("error", "").lower()
        finally:
            bg_analysis.DATA_DIR = original_data_dir

    def test_recent_running_stays_running(self, case_dirs):
        """Progress updated within 5 min should remain 'running'."""
        from core import bg_analysis

        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            prep_id = case_dirs["prep_id"]

            recent_time = datetime.now().isoformat()
            progress = {
                "status": "running",
                "started_at": recent_time,
                "node_started_at": recent_time,
                "nodes_completed": 2,
                "total_nodes": 14,
            }
            path = bg_analysis._progress_path(case_id, prep_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(progress, f)

            result = bg_analysis.get_analysis_progress(case_id, prep_id)
            assert result["status"] == "running"
        finally:
            bg_analysis.DATA_DIR = original_data_dir


class TestBgAnalysisIsRunning:
    """Verify is_analysis_running() includes stale detection."""

    def test_stale_returns_false(self, case_dirs):
        """is_analysis_running should return False for a stale worker."""
        from core import bg_analysis

        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            prep_id = case_dirs["prep_id"]

            stale_time = (datetime.now() - timedelta(minutes=10)).isoformat()
            progress = {
                "status": "running",
                "started_at": stale_time,
                "node_started_at": stale_time,
                "nodes_completed": 5,
                "total_nodes": 14,
                "current_node": "legal_researcher",
                "completed_nodes": [],
                "per_node_times": {},
                "skipped_nodes": [],
                "est_tokens_so_far": 0,
            }
            path = bg_analysis._progress_path(case_id, prep_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(progress, f)

            assert bg_analysis.is_analysis_running(case_id, prep_id) is False

            # Verify it also wrote an error status back to disk
            with open(path, "r") as f:
                updated = json.load(f)
            assert updated["status"] == "error"
            assert "stale" in updated.get("error", "").lower() or "crashed" in updated.get("error", "").lower()
        finally:
            bg_analysis.DATA_DIR = original_data_dir

    def test_no_progress_returns_false(self, case_dirs):
        """When no progress file exists, is_analysis_running should return False."""
        from core import bg_analysis

        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            assert bg_analysis.is_analysis_running(case_dirs["case_id"], case_dirs["prep_id"]) is False
        finally:
            bg_analysis.DATA_DIR = original_data_dir


class TestBgAnalysisAtomicWrite:
    """Verify _write_progress uses tmp file + os.replace pattern."""

    def test_write_progress_creates_file(self, case_dirs):
        """_write_progress should create a valid JSON file."""
        from core import bg_analysis

        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            prep_id = case_dirs["prep_id"]

            progress = {
                "status": "running",
                "nodes_completed": 1,
                "total_nodes": 10,
            }
            bg_analysis._write_progress(case_id, prep_id, progress)

            path = bg_analysis._progress_path(case_id, prep_id)
            assert os.path.exists(path)

            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded["status"] == "running"
            assert loaded["nodes_completed"] == 1
        finally:
            bg_analysis.DATA_DIR = original_data_dir

    def test_write_progress_no_leftover_tmp(self, case_dirs):
        """After _write_progress, no .tmp files should remain."""
        from core import bg_analysis

        original_data_dir = bg_analysis.DATA_DIR
        bg_analysis.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            prep_id = case_dirs["prep_id"]

            bg_analysis._write_progress(case_id, prep_id, {"status": "complete"})

            prep_dir = os.path.dirname(bg_analysis._progress_path(case_id, prep_id))
            tmp_files = [f for f in os.listdir(prep_dir) if f.endswith(".tmp")]
            assert len(tmp_files) == 0
        finally:
            bg_analysis.DATA_DIR = original_data_dir


# ===========================================================================
# 2. ingestion_worker.py  --  stale detection, heartbeat, concurrent start
# ===========================================================================


class TestIngestionStaleDetection:
    """Verify get_ingestion_status resets stale workers."""

    def test_stale_running_resets_to_none(self, case_dirs):
        """Ingestion status stuck >5 min should auto-reset to 'none'."""
        from core import ingestion_worker

        original_data_dir = ingestion_worker.DATA_DIR
        ingestion_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            stale_time = (datetime.now() - timedelta(minutes=10)).isoformat()
            status_data = {
                "status": "running",
                "progress": 50,
                "message": "Processing file.pdf...",
                "updated_at": stale_time,
            }
            path = ingestion_worker._status_path(case_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(status_data, f)

            result = ingestion_worker.get_ingestion_status(case_id)
            assert result["status"] == "none"
        finally:
            ingestion_worker.DATA_DIR = original_data_dir

    def test_recent_running_stays_running(self, case_dirs):
        """Ingestion status updated recently should remain 'running'."""
        from core import ingestion_worker

        original_data_dir = ingestion_worker.DATA_DIR
        ingestion_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            recent_time = datetime.now().isoformat()
            status_data = {
                "status": "running",
                "progress": 50,
                "message": "Processing file.pdf...",
                "updated_at": recent_time,
            }
            path = ingestion_worker._status_path(case_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(status_data, f)

            result = ingestion_worker.get_ingestion_status(case_id)
            assert result["status"] == "running"
        finally:
            ingestion_worker.DATA_DIR = original_data_dir


class TestIngestionHeartbeat:
    """Verify heartbeat refreshes updated_at timestamp."""

    def test_set_status_updates_timestamp(self, case_dirs):
        """Each call to set_ingestion_status should refresh updated_at."""
        from core import ingestion_worker

        original_data_dir = ingestion_worker.DATA_DIR
        ingestion_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]

            ingestion_worker.set_ingestion_status(case_id, "running", 10, "Processing...")
            status1 = ingestion_worker.get_ingestion_status(case_id)
            ts1 = status1["updated_at"]

            # Small delay to ensure timestamp changes
            time.sleep(0.05)

            ingestion_worker.set_ingestion_status(case_id, "running", 20, "Still processing...")
            status2 = ingestion_worker.get_ingestion_status(case_id)
            ts2 = status2["updated_at"]

            assert ts2 > ts1, "Heartbeat should advance the timestamp"
        finally:
            ingestion_worker.DATA_DIR = original_data_dir


class TestIngestionConcurrentStart:
    """Verify only one ingestion worker runs per case."""

    def test_start_returns_false_when_running(self, case_dirs):
        """start_background_ingestion should refuse if already running."""
        from core import ingestion_worker

        original_data_dir = ingestion_worker.DATA_DIR
        ingestion_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]

            # Simulate an already-running status
            ingestion_worker.set_ingestion_status(case_id, "running", 50, "Processing...")

            mock_cm = MagicMock()
            result = ingestion_worker.start_background_ingestion(case_id, mock_cm, "anthropic")
            assert result is False
        finally:
            ingestion_worker.DATA_DIR = original_data_dir


class TestIngestionAtomicWrite:
    """Verify _save_file_cache uses tmp + os.replace pattern."""

    def test_save_file_cache_atomic(self, tmp_path):
        """_save_file_cache should produce a valid JSON file with no tmp leftovers."""
        from core.ingestion_worker import _save_file_cache

        cache_path = str(tmp_path / "ingestion_cache.json")
        cache_data = {"file.pdf:1234": [{"page_content": "text", "metadata": {}}]}

        _save_file_cache(cache_path, cache_data)

        assert os.path.exists(cache_path)
        with open(cache_path, "r") as f:
            loaded = json.load(f)
        assert "file.pdf:1234" in loaded

        # No leftover .tmp files
        tmp_files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")]
        assert len(tmp_files) == 0


# ===========================================================================
# 3. ocr_worker.py  --  stale detection, concurrent start prevention
# ===========================================================================


class TestOcrStaleDetection:
    """Verify get_ocr_status resets stale workers (10 min threshold)."""

    def test_stale_running_resets_to_idle(self, case_dirs):
        """OCR status stuck >10 min should auto-reset to 'idle'."""
        from core import ocr_worker

        original_data_dir = ocr_worker.DATA_DIR
        ocr_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            stale_time = (datetime.now() - timedelta(minutes=15)).isoformat()
            status_data = {
                "status": "running",
                "files_done": 2,
                "files_total": 10,
                "updated_at": stale_time,
            }
            path = ocr_worker._status_path(case_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(status_data, f)

            result = ocr_worker.get_ocr_status(case_id)
            assert result["status"] == "idle"
        finally:
            ocr_worker.DATA_DIR = original_data_dir

    def test_recent_running_stays_running(self, case_dirs):
        """OCR status updated recently should remain 'running'."""
        from core import ocr_worker

        original_data_dir = ocr_worker.DATA_DIR
        ocr_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            recent_time = datetime.now().isoformat()
            status_data = {
                "status": "running",
                "files_done": 2,
                "files_total": 10,
                "updated_at": recent_time,
            }
            path = ocr_worker._status_path(case_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(status_data, f)

            result = ocr_worker.get_ocr_status(case_id)
            assert result["status"] == "running"
        finally:
            ocr_worker.DATA_DIR = original_data_dir


class TestOcrConcurrentStart:
    """Verify only one OCR worker runs per case."""

    def test_start_returns_false_when_alive(self, case_dirs):
        """start_ocr_worker should refuse if a thread is already alive."""
        from core import ocr_worker

        original_workers = ocr_worker._active_workers.copy()
        try:
            case_id = case_dirs["case_id"]

            # Insert a mock alive thread
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            ocr_worker._active_workers[case_id] = mock_thread

            mock_cm = MagicMock()
            result = ocr_worker.start_ocr_worker(case_id, mock_cm, "anthropic")
            assert result is False
        finally:
            ocr_worker._active_workers = original_workers

    def test_start_returns_false_when_status_running(self, case_dirs):
        """start_ocr_worker should refuse if status file says 'running'."""
        from core import ocr_worker

        original_data_dir = ocr_worker.DATA_DIR
        original_workers = ocr_worker._active_workers.copy()
        ocr_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]

            # Ensure no existing thread reference
            ocr_worker._active_workers.pop(case_id, None)

            # Write a running status (recent enough to not be stale)
            recent_time = datetime.now().isoformat()
            status_data = {
                "status": "running",
                "files_done": 0,
                "files_total": 5,
                "updated_at": recent_time,
            }
            path = ocr_worker._status_path(case_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(status_data, f)

            mock_cm = MagicMock()
            result = ocr_worker.start_ocr_worker(case_id, mock_cm, "anthropic")
            assert result is False
        finally:
            ocr_worker.DATA_DIR = original_data_dir
            ocr_worker._active_workers = original_workers


class TestOcrStatusWrite:
    """Verify _set_status writes atomically."""

    def test_set_status_creates_valid_json(self, case_dirs):
        """_set_status should produce a readable JSON status file."""
        from core import ocr_worker

        original_data_dir = ocr_worker.DATA_DIR
        ocr_worker.DATA_DIR = case_dirs["data_dir"]
        try:
            case_id = case_dirs["case_id"]
            ocr_worker._set_status(
                case_id, status="running", current_file="test.pdf",
                files_done=1, files_total=5,
            )

            path = ocr_worker._status_path(case_id)
            assert os.path.exists(path)
            with open(path, "r") as f:
                data = json.load(f)
            assert data["status"] == "running"
            assert data["current_file"] == "test.pdf"
            assert "updated_at" in data
        finally:
            ocr_worker.DATA_DIR = original_data_dir
