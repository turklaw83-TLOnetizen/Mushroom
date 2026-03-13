"""Tests for core/worker_queue.py — file-based job queue."""

import json
from pathlib import Path

import pytest

from core.worker_queue import (
    queue_worker_request,
    list_pending_requests,
    remove_request,
    move_to_failed,
)


class TestQueueRequest:
    def test_creates_request_file(self, tmp_data_dir):
        req_id = queue_worker_request(tmp_data_dir, "analysis", case_id="c1", prep_id="p1")
        assert req_id is not None
        assert len(req_id) > 0

        # File should exist
        req_dir = Path(tmp_data_dir) / "worker_requests"
        files = list(req_dir.glob("*.json"))
        assert len(files) == 1

    def test_request_contains_params(self, tmp_data_dir):
        queue_worker_request(tmp_data_dir, "analysis", case_id="c1", prep_id="p1")
        requests = list_pending_requests(tmp_data_dir)
        assert len(requests) == 1
        req = requests[0]
        assert req["type"] == "analysis"
        assert req["case_id"] == "c1"
        assert req["prep_id"] == "p1"

    def test_multiple_requests(self, tmp_data_dir):
        queue_worker_request(tmp_data_dir, "analysis", case_id="c1")
        queue_worker_request(tmp_data_dir, "ingestion", case_id="c2")
        queue_worker_request(tmp_data_dir, "ocr", case_id="c3")

        requests = list_pending_requests(tmp_data_dir)
        assert len(requests) == 3
        types = {r["type"] for r in requests}
        assert types == {"analysis", "ingestion", "ocr"}


class TestListPending:
    def test_empty_queue(self, tmp_data_dir):
        results = list_pending_requests(tmp_data_dir)
        assert results == []

    def test_sorted_by_creation(self, tmp_data_dir):
        import time
        queue_worker_request(tmp_data_dir, "analysis", case_id="first")
        time.sleep(0.01)  # ensure distinct timestamps
        queue_worker_request(tmp_data_dir, "analysis", case_id="second")
        time.sleep(0.01)
        queue_worker_request(tmp_data_dir, "analysis", case_id="third")

        requests = list_pending_requests(tmp_data_dir)
        assert len(requests) == 3
        # Verify ordering: first created should come first
        case_ids = [r["case_id"] for r in requests]
        assert case_ids == ["first", "second", "third"]


class TestRemoveRequest:
    def test_removes_existing(self, tmp_data_dir):
        req_id = queue_worker_request(tmp_data_dir, "analysis", case_id="c1")
        assert remove_request(tmp_data_dir, req_id) is True
        assert list_pending_requests(tmp_data_dir) == []

    def test_remove_nonexistent(self, tmp_data_dir):
        assert remove_request(tmp_data_dir, "nonexistent") is False


class TestMoveToFailed:
    def test_moves_to_failed(self, tmp_data_dir):
        req_id = queue_worker_request(tmp_data_dir, "analysis", case_id="c1")
        result = move_to_failed(tmp_data_dir, req_id, error="Test error")
        assert result is True

        # Should be gone from pending
        assert list_pending_requests(tmp_data_dir) == []

        # Should exist in failed/
        failed_dir = Path(tmp_data_dir) / "worker_requests" / "failed"
        files = list(failed_dir.glob("*.json"))
        assert len(files) == 1

        # Should contain error info
        failed = json.loads(files[0].read_text())
        assert failed["error"] == "Test error"
        assert "failed_at" in failed

    def test_move_nonexistent(self, tmp_data_dir):
        assert move_to_failed(tmp_data_dir, "nonexistent") is False
