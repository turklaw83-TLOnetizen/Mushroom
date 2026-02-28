# ---- Tests for core/case_manager.py ---------------------------------------

import pytest
from core.case_manager import CaseManager
from core.storage.json_backend import JSONStorageBackend


@pytest.fixture
def cm(tmp_data_dir):
    """Provide a CaseManager with a temp storage backend."""
    storage = JSONStorageBackend(tmp_data_dir)
    return CaseManager(storage)


class TestCaseCRUD:
    def test_create_case(self, cm):
        case_id = cm.create_case("State v. Smith", description="Test case")
        assert case_id
        cases = cm.list_cases()
        assert len(cases) == 1
        assert cases[0]["name"] == "State v. Smith"

    def test_get_case_name(self, cm):
        case_id = cm.create_case("Test Case")
        assert cm.get_case_name(case_id) == "Test Case"

    def test_delete_case(self, cm):
        case_id = cm.create_case("Delete Me")
        cm.delete_case(case_id)
        assert len(cm.list_cases()) == 0

    def test_rename_case(self, cm):
        case_id = cm.create_case("Old Name")
        new_id = cm.rename_case(case_id, "New Name")
        assert cm.get_case_name(new_id) == "New Name"

    def test_archive_unarchive(self, cm):
        case_id = cm.create_case("Archivable")
        cm.archive_case(case_id)
        assert len(cm.list_cases(include_archived=False)) == 0
        assert len(cm.list_cases(include_archived=True)) == 1
        cm.unarchive_case(case_id)
        assert len(cm.list_cases(include_archived=False)) == 1

    def test_clone_case(self, cm):
        case_id = cm.create_case("Original")
        cm.save_file(case_id, b"test", "test.pdf")
        new_id = cm.clone_case(case_id, "Clone")
        assert cm.get_case_name(new_id) == "Clone"


class TestCaseTypeAndClient:
    def test_case_type(self, cm):
        case_id = cm.create_case("Civil Case", case_type="civil-plaintiff")
        assert cm.get_case_type(case_id) == "civil-plaintiff"
        cm.update_case_type(case_id, "civil-defendant")
        assert cm.get_case_type(case_id) == "civil-defendant"

    def test_client_name(self, cm):
        case_id = cm.create_case("Client Test", client_name="John")
        assert cm.get_client_name(case_id) == "John"
        cm.update_client_name(case_id, "Jane")
        assert cm.get_client_name(case_id) == "Jane"


class TestDirectives:
    def test_add_and_load_directives(self, cm):
        case_id = cm.create_case("Directives Test")
        d_id = cm.save_directive(case_id, "Client was not at scene", "fact")
        directives = cm.load_directives(case_id)
        assert len(directives) == 1
        assert directives[0]["text"] == "Client was not at scene"
        assert directives[0]["category"] == "fact"

    def test_update_directive(self, cm):
        case_id = cm.create_case("Test")
        d_id = cm.save_directive(case_id, "Original text")
        cm.update_directive(case_id, d_id, "Updated text")
        directives = cm.load_directives(case_id)
        assert directives[0]["text"] == "Updated text"

    def test_delete_directive(self, cm):
        case_id = cm.create_case("Test")
        d_id = cm.save_directive(case_id, "To delete")
        cm.delete_directive(case_id, d_id)
        assert len(cm.load_directives(case_id)) == 0


class TestPreparations:
    def test_create_preparation(self, cm):
        case_id = cm.create_case("Prep Test")
        prep_id = cm.create_preparation(case_id, "trial", "Trial Prep 1")
        preps = cm.list_preparations(case_id)
        assert len(preps) == 1
        assert preps[0]["type"] == "trial"

    def test_save_and_load_prep_state(self, cm, sample_state):
        case_id = cm.create_case("State Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_prep_state(case_id, prep_id, sample_state)
        loaded = cm.load_prep_state(case_id, prep_id)
        assert loaded["case_summary"] == sample_state["case_summary"]

    def test_delete_preparation(self, cm):
        case_id = cm.create_case("Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.delete_preparation(case_id, prep_id)
        assert len(cm.list_preparations(case_id)) == 0

    def test_merge_append_only(self, cm, sample_state):
        case_id = cm.create_case("Merge Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_prep_state(case_id, prep_id, sample_state)

        new_state = {
            "witnesses": [
                {"name": "Officer Smith", "type": "State", "goal": "Testify about arrest"},
                {"name": "New Witness", "type": "Expert", "goal": "Forensics"},
            ],
            "case_summary": "Updated summary",
        }
        merged = cm.merge_append_only(case_id, prep_id, new_state)
        names = {w["name"] for w in merged["witnesses"]}
        assert "Jane Doe" in names  # Preserved from original
        assert "New Witness" in names  # Added

    def test_has_preparations(self, cm):
        case_id = cm.create_case("Test")
        assert not cm.has_preparations(case_id)
        cm.create_preparation(case_id, "trial")
        assert cm.has_preparations(case_id)


class TestNotes:
    def test_prep_notes(self, cm):
        case_id = cm.create_case("Notes Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_notes(case_id, prep_id, "My prep notes")
        assert cm.load_notes(case_id, prep_id) == "My prep notes"

    def test_case_notes(self, cm):
        case_id = cm.create_case("Notes Test")
        cm.save_case_notes(case_id, "Case-level notes")
        assert cm.load_case_notes(case_id) == "Case-level notes"

    def test_module_notes(self, cm):
        case_id = cm.create_case("Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_module_notes(case_id, prep_id, "evidence", "Evidence notes")
        assert cm.load_module_notes(case_id, prep_id, "evidence") == "Evidence notes"


class TestJournal:
    def test_add_and_load(self, cm):
        case_id = cm.create_case("Journal Test")
        cm.add_journal_entry(case_id, "Entry one", "Strategy")
        cm.add_journal_entry(case_id, "Entry two", "General")
        journal = cm.load_journal(case_id)
        assert len(journal) == 2
        assert journal[0]["text"] == "Entry two"  # Newest first

    def test_delete_entry(self, cm):
        case_id = cm.create_case("Test")
        entry_id = cm.add_journal_entry(case_id, "To delete")
        cm.delete_journal_entry(case_id, entry_id)
        assert len(cm.load_journal(case_id)) == 0


class TestDeadlines:
    def test_save_and_load(self, cm):
        case_id = cm.create_case("Test")
        prep_id = cm.create_preparation(case_id, "trial")
        d_id = cm.save_deadline(case_id, prep_id, {
            "date": "2026-06-15",
            "label": "Motion Filing",
            "category": "Filing Deadline",
        })
        deadlines = cm.load_deadlines(case_id, prep_id)
        assert len(deadlines) == 1
        assert deadlines[0]["label"] == "Motion Filing"

    def test_delete_deadline(self, cm):
        case_id = cm.create_case("Test")
        prep_id = cm.create_preparation(case_id, "trial")
        d_id = cm.save_deadline(case_id, prep_id, {"label": "Delete me"})
        cm.delete_deadline(case_id, prep_id, d_id)
        assert len(cm.load_deadlines(case_id, prep_id)) == 0


class TestSnapshots:
    def test_save_and_restore(self, cm, sample_state):
        case_id = cm.create_case("Snapshot Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_prep_state(case_id, prep_id, sample_state)

        snap_id = cm.save_snapshot(case_id, prep_id, "Before changes")
        assert snap_id

        # Modify state
        sample_state["case_summary"] = "Modified"
        cm.save_prep_state(case_id, prep_id, sample_state)

        # Restore
        restored = cm.restore_snapshot(case_id, prep_id, snap_id)
        assert restored["case_summary"] != "Modified"

    def test_list_snapshots(self, cm, sample_state):
        case_id = cm.create_case("Test")
        prep_id = cm.create_preparation(case_id, "trial")
        cm.save_prep_state(case_id, prep_id, sample_state)
        cm.save_snapshot(case_id, prep_id, "Snap 1")
        cm.save_snapshot(case_id, prep_id, "Snap 2")
        snaps = cm.list_snapshots(case_id, prep_id)
        assert len(snaps) == 2


class TestActivityLog:
    def test_log_and_retrieve(self, cm):
        case_id = cm.create_case("Activity Test")
        # create_case already logs an activity
        log = cm.get_activity_log(case_id)
        assert len(log) >= 1
        assert log[0]["action"] == "case_created"
