# ---- Tests for core/storage/json_backend.py -------------------------------

import json
import os
from pathlib import Path

import pytest

from core.storage.json_backend import JSONStorageBackend


class TestCaseCRUD:
    def test_create_case(self, storage, sample_case_metadata):
        case_id = sample_case_metadata["id"]
        storage.create_case(case_id, sample_case_metadata)
        assert storage.case_exists(case_id)

    def test_list_cases(self, populated_storage):
        storage, case_id = populated_storage
        cases = storage.list_cases()
        assert len(cases) == 1
        assert cases[0]["id"] == case_id

    def test_list_cases_excludes_archived(self, storage, sample_case_metadata):
        case_id = sample_case_metadata["id"]
        sample_case_metadata["status"] = "archived"
        storage.create_case(case_id, sample_case_metadata)
        assert len(storage.list_cases(include_archived=False)) == 0
        assert len(storage.list_cases(include_archived=True)) == 1

    def test_get_case_metadata(self, populated_storage, sample_case_metadata):
        storage, case_id = populated_storage
        meta = storage.get_case_metadata(case_id)
        assert meta["name"] == sample_case_metadata["name"]

    def test_update_case_metadata(self, populated_storage):
        storage, case_id = populated_storage
        meta = storage.get_case_metadata(case_id)
        meta["client_name"] = "Updated Client"
        storage.update_case_metadata(case_id, meta)
        reloaded = storage.get_case_metadata(case_id)
        assert reloaded["client_name"] == "Updated Client"

    def test_delete_case(self, populated_storage):
        storage, case_id = populated_storage
        storage.delete_case(case_id)
        assert not storage.case_exists(case_id)

    def test_case_not_exists(self, storage):
        assert not storage.case_exists("nonexistent")
        assert storage.get_case_metadata("nonexistent") == {}


class TestFileManagement:
    def test_save_and_list_files(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "test.pdf", b"PDF content here")
        files = storage.get_case_files(case_id)
        basenames = [os.path.basename(f) for f in files]
        assert "test.pdf" in basenames

    def test_delete_file(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "delete_me.pdf", b"data")
        assert storage.delete_file(case_id, "delete_me.pdf")
        basenames = [os.path.basename(f) for f in storage.get_case_files(case_id)]
        assert "delete_me.pdf" not in basenames

    def test_delete_nonexistent_file(self, populated_storage):
        storage, case_id = populated_storage
        assert not storage.delete_file(case_id, "nope.pdf")

    def test_get_file_path(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "test.txt", b"hello")
        path = storage.get_file_path(case_id, "test.txt")
        assert Path(path).exists()


class TestPreparations:
    def test_create_and_list_preparations(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        preps = [{"id": "prep1", "type": "trial", "name": "Trial Prep"}]
        storage.save_preparations_index(case_id, preps)
        loaded = storage.list_preparations(case_id)
        assert len(loaded) == 1
        assert loaded[0]["id"] == "prep1"

    def test_save_and_load_prep_state(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        state = {"case_summary": "Test summary", "charges": []}
        storage.save_prep_state(case_id, "prep1", state)
        loaded = storage.load_prep_state(case_id, "prep1")
        assert loaded["case_summary"] == "Test summary"

    def test_load_missing_prep_state(self, populated_storage):
        storage, case_id = populated_storage
        assert storage.load_prep_state(case_id, "nonexistent") is None

    def test_delete_preparation(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_prep_state(case_id, "prep1", {"test": True})
        storage.delete_preparation_dir(case_id, "prep1")
        assert storage.load_prep_state(case_id, "prep1") is None


class TestJSONIO:
    def test_load_save_json(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_json(case_id, "custom.json", {"key": "value"})
        loaded = storage.load_json(case_id, "custom.json")
        assert loaded["key"] == "value"

    def test_load_missing_json(self, populated_storage):
        storage, case_id = populated_storage
        assert storage.load_json(case_id, "missing.json", []) == []

    def test_prep_json(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_prep_json(case_id, "prep1", "data.json", [1, 2, 3])
        assert storage.load_prep_json(case_id, "prep1", "data.json") == [1, 2, 3]


class TestTextFiles:
    def test_case_text(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_text(case_id, "notes.txt", "Hello World")
        assert storage.load_text(case_id, "notes.txt") == "Hello World"

    def test_prep_text(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_prep_text(case_id, "prep1", "notes.txt", "Prep notes")
        assert storage.load_prep_text(case_id, "prep1", "notes.txt") == "Prep notes"

    def test_module_notes(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_module_notes(case_id, "prep1", "evidence", "Evidence notes here")
        assert storage.load_module_notes(case_id, "prep1", "evidence") == "Evidence notes here"


class TestSnapshots:
    def test_save_and_list_snapshots(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_snapshot(case_id, "prep1", "snap1",
                              {"case_summary": "Snapshot"}, {"id": "snap1", "label": "Test"})
        snaps = storage.list_snapshots(case_id, "prep1")
        assert len(snaps) == 1
        assert snaps[0]["id"] == "snap1"

    def test_load_snapshot(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        state = {"case_summary": "Saved state"}
        storage.save_snapshot(case_id, "prep1", "snap1", state, {"id": "snap1"})
        loaded = storage.load_snapshot(case_id, "prep1", "snap1")
        assert loaded["case_summary"] == "Saved state"


class TestActivityLog:
    def test_append_and_get(self, populated_storage):
        storage, case_id = populated_storage
        storage.append_activity(case_id, {"action": "test", "detail": "first"})
        storage.append_activity(case_id, {"action": "test", "detail": "second"})
        log = storage.get_activity_log(case_id, limit=10)
        assert len(log) == 2
        # Newest first
        assert log[0]["detail"] == "second"


class TestFileTags:
    def test_save_and_get_tags(self, populated_storage):
        storage, case_id = populated_storage
        tags = {"file1.pdf": ["Police Report", "Important"], "file2.pdf": ["Contract"]}
        storage.save_file_tags(case_id, tags)
        loaded = storage.get_file_tags(case_id)
        assert loaded["file1.pdf"] == ["Police Report", "Important"]


class TestClone:
    def test_clone_case(self, populated_storage, sample_case_metadata):
        storage, case_id = populated_storage
        storage.save_file(case_id, "test.pdf", b"data")
        storage.clone_case(case_id, "clone_case")
        assert storage.case_exists("clone_case")
        assert "test.pdf" in [os.path.basename(f) for f in storage.get_case_files("clone_case")]

    def test_clone_preparation(self, populated_storage):
        storage, case_id = populated_storage
        storage.create_preparation_dir(case_id, "prep1")
        storage.save_prep_state(case_id, "prep1", {"test": True})
        storage.clone_preparation(case_id, "prep1", "prep2")
        state = storage.load_prep_state(case_id, "prep2")
        assert state["test"] is True


class TestFingerprinting:
    def test_docs_fingerprint(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "a.pdf", b"content A")
        storage.save_file(case_id, "b.pdf", b"content B")
        fp = storage.compute_docs_fingerprint(case_id)
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA-256 hex

    def test_fingerprint_changes_on_file_change(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "a.pdf", b"original")
        fp1 = storage.compute_docs_fingerprint(case_id)
        # Use different-length content so the size-based fingerprint changes
        storage.save_file(case_id, "a.pdf", b"modified content that is longer")
        fp2 = storage.compute_docs_fingerprint(case_id)
        assert fp1 != fp2

    def test_per_file_fingerprint(self, populated_storage):
        storage, case_id = populated_storage
        storage.save_file(case_id, "a.pdf", b"content")
        fps = storage.compute_per_file_fingerprint(case_id)
        assert "a.pdf" in fps
        assert len(fps["a.pdf"]) == 64
