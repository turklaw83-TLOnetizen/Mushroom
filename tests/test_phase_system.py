# ---- Tests for Case Phase Lifecycle Management -------------------------------
# Tests the phase system: Active (with sub-phases) → Closed → Archived → Purge
# Also tests: migration, auto-archive, phase config CRUD, backward compat.

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.case_manager import (
    CLOSED_AUTO_ARCHIVE_DAYS,
    DEFAULT_PHASE_CONFIG,
    PHASES,
    CaseManager,
    _PHASE_TO_STATUS,
)
from core.storage.json_backend import JSONStorageBackend


# ---- Fixtures ----------------------------------------------------------------

@pytest.fixture
def cm(tmp_path):
    """CaseManager backed by temp storage."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    storage = JSONStorageBackend(data_dir)
    return CaseManager(storage)


@pytest.fixture
def case_id(cm):
    """Create a fresh case and return its ID."""
    cid = cm.create_case("Phase Test Case")
    return cid


# ---- Phase Constants ---------------------------------------------------------

def test_phases_tuple():
    assert PHASES == ("active", "closed", "archived")


def test_phase_to_status_mapping():
    assert _PHASE_TO_STATUS["active"] == "active"
    assert _PHASE_TO_STATUS["closed"] == "active"
    assert _PHASE_TO_STATUS["archived"] == "archived"


def test_default_phase_config_has_all_types():
    for ct in ("criminal", "criminal-juvenile", "civil-plaintiff",
               "civil-defendant", "civil-juvenile"):
        assert ct in DEFAULT_PHASE_CONFIG
        assert isinstance(DEFAULT_PHASE_CONFIG[ct], list)
        assert len(DEFAULT_PHASE_CONFIG[ct]) >= 5


# ---- Migration ---------------------------------------------------------------

def test_migrate_phase_from_status(cm, case_id):
    """Legacy cases (no phase field) should get phase from status on read."""
    # Manually remove phase from metadata to simulate a legacy case
    meta = cm.storage.get_case_metadata(case_id)
    meta.pop("phase", None)
    meta.pop("sub_phase", None)
    meta["status"] = "active"
    cm.storage.update_case_metadata(case_id, meta)

    phase, sub = cm.get_phase(case_id)
    assert phase == "active"
    assert sub == ""


def test_migrate_phase_archived_legacy(cm, case_id):
    """Legacy archived cases migrate correctly."""
    meta = cm.storage.get_case_metadata(case_id)
    meta.pop("phase", None)
    meta["status"] = "archived"
    cm.storage.update_case_metadata(case_id, meta)

    phase, sub = cm.get_phase(case_id)
    assert phase == "archived"
    assert sub == ""


# ---- get_phase / set_phase ---------------------------------------------------

def test_new_case_starts_active(cm, case_id):
    phase, sub = cm.get_phase(case_id)
    assert phase == "active"


def test_set_phase_to_closed(cm, case_id):
    cm.set_phase(case_id, "closed")
    phase, sub = cm.get_phase(case_id)
    assert phase == "closed"
    assert sub == ""  # No sub-phases for closed

    # Verify backward compat: status should still be "active" for closed
    meta = cm.storage.get_case_metadata(case_id)
    assert meta["status"] == "active"


def test_set_phase_to_archived(cm, case_id):
    cm.set_phase(case_id, "archived")
    phase, sub = cm.get_phase(case_id)
    assert phase == "archived"

    meta = cm.storage.get_case_metadata(case_id)
    assert meta["status"] == "archived"


def test_set_phase_invalid_raises(cm, case_id):
    with pytest.raises(ValueError, match="Invalid phase"):
        cm.set_phase(case_id, "bogus")


def test_set_phase_with_sub_phase(cm, case_id):
    cm.set_phase(case_id, "active", sub_phase="Discovery")
    phase, sub = cm.get_phase(case_id)
    assert phase == "active"
    assert sub == "Discovery"


def test_set_phase_to_closed_clears_sub_phase(cm, case_id):
    cm.set_phase(case_id, "active", sub_phase="Trial Prep")
    cm.set_phase(case_id, "closed")
    phase, sub = cm.get_phase(case_id)
    assert sub == ""


def test_set_phase_to_closed_sets_closed_at(cm, case_id):
    cm.set_phase(case_id, "closed")
    meta = cm.storage.get_case_metadata(case_id)
    assert "closed_at" in meta
    assert meta["closed_at"]  # Non-empty string


# ---- set_sub_phase -----------------------------------------------------------

def test_set_sub_phase_active_case(cm, case_id):
    cm.set_sub_phase(case_id, "Discovery")
    _, sub = cm.get_phase(case_id)
    assert sub == "Discovery"


def test_set_sub_phase_ignores_non_active(cm, case_id):
    cm.set_phase(case_id, "closed")
    cm.set_sub_phase(case_id, "Discovery")  # Should silently do nothing
    _, sub = cm.get_phase(case_id)
    assert sub == ""


def test_set_sub_phase_change_logged(cm, case_id):
    cm.set_sub_phase(case_id, "Intake")
    cm.set_sub_phase(case_id, "Discovery")
    log = cm.get_activity_log(case_id, limit=10)
    sub_phase_entries = [e for e in log if e.get("action") == "sub_phase_changed"]
    assert len(sub_phase_entries) >= 1
    assert "Discovery" in sub_phase_entries[0].get("detail", "")


def test_set_sub_phase_same_value_not_logged(cm, case_id):
    cm.set_sub_phase(case_id, "Intake")
    log_before = cm.get_activity_log(case_id, limit=50)
    before_count = len([e for e in log_before if e.get("action") == "sub_phase_changed"])

    cm.set_sub_phase(case_id, "Intake")  # Same value
    log_after = cm.get_activity_log(case_id, limit=50)
    after_count = len([e for e in log_after if e.get("action") == "sub_phase_changed"])
    assert after_count == before_count  # No new log entry


# ---- Purge Source Docs -------------------------------------------------------

def test_purge_requires_archived(cm, case_id):
    with pytest.raises(ValueError, match="archived"):
        cm.purge_source_docs(case_id)


def test_purge_active_case_raises(cm, case_id):
    cm.set_phase(case_id, "active")
    with pytest.raises(ValueError):
        cm.purge_source_docs(case_id)


def test_purge_closed_case_raises(cm, case_id):
    cm.set_phase(case_id, "closed")
    with pytest.raises(ValueError):
        cm.purge_source_docs(case_id)


def test_purge_archived_case_succeeds(cm, case_id):
    # Upload some files first
    cm.storage.save_file(case_id, "doc1.pdf", b"PDF content here")
    cm.storage.save_file(case_id, "doc2.docx", b"DOCX content here")
    files_before = cm.get_case_files(case_id)
    assert len(files_before) == 2

    cm.set_phase(case_id, "archived")
    count = cm.purge_source_docs(case_id)
    assert count == 2

    files_after = cm.get_case_files(case_id)
    assert len(files_after) == 0


def test_purge_sets_metadata(cm, case_id):
    cm.storage.save_file(case_id, "doc1.pdf", b"content")
    cm.set_phase(case_id, "archived")
    cm.purge_source_docs(case_id)

    meta = cm.storage.get_case_metadata(case_id)
    assert meta["purged"] is True
    assert "purged_at" in meta
    assert meta["purged_file_count"] == 1


def test_purge_empty_source_docs(cm, case_id):
    cm.set_phase(case_id, "archived")
    count = cm.purge_source_docs(case_id)
    assert count == 0


def test_purge_logged_in_activity(cm, case_id):
    cm.storage.save_file(case_id, "doc.pdf", b"x")
    cm.set_phase(case_id, "archived")
    cm.purge_source_docs(case_id)

    log = cm.get_activity_log(case_id, limit=10)
    purge_entries = [e for e in log if e.get("action") == "files_purged"]
    assert len(purge_entries) >= 1


# ---- Auto-Archive Closed Cases -----------------------------------------------

def test_auto_archive_fresh_closed_not_archived(cm, case_id):
    """Cases closed just now should NOT be auto-archived."""
    cm.set_phase(case_id, "closed")
    archived_ids = cm.check_auto_archive_closed_cases()
    assert case_id not in archived_ids

    phase, _ = cm.get_phase(case_id)
    assert phase == "closed"


def test_auto_archive_old_closed_case(cm, case_id):
    """Cases closed > CLOSED_AUTO_ARCHIVE_DAYS ago should be auto-archived."""
    cm.set_phase(case_id, "closed")

    # Backdate closed_at
    meta = cm.storage.get_case_metadata(case_id)
    old_date = (datetime.now() - timedelta(days=CLOSED_AUTO_ARCHIVE_DAYS + 1)).isoformat()
    meta["closed_at"] = old_date
    cm.storage.update_case_metadata(case_id, meta)

    archived_ids = cm.check_auto_archive_closed_cases()
    assert case_id in archived_ids

    phase, _ = cm.get_phase(case_id)
    assert phase == "archived"


def test_auto_archive_skips_active_cases(cm, case_id):
    """Active cases should not be affected by auto-archive."""
    cm.set_phase(case_id, "active")
    archived_ids = cm.check_auto_archive_closed_cases()
    assert case_id not in archived_ids


def test_auto_archive_respects_clock_reset(cm, case_id):
    """If a case goes closed → active → closed, the clock resets."""
    cm.set_phase(case_id, "closed")

    # Backdate
    meta = cm.storage.get_case_metadata(case_id)
    old_date = (datetime.now() - timedelta(days=30)).isoformat()
    meta["closed_at"] = old_date
    cm.storage.update_case_metadata(case_id, meta)

    # Reopen (resets clock)
    cm.set_phase(case_id, "active")
    cm.set_phase(case_id, "closed")  # New closed_at timestamp

    archived_ids = cm.check_auto_archive_closed_cases()
    assert case_id not in archived_ids  # Fresh closed_at, not expired


def test_auto_archive_no_closed_at_skipped(cm, case_id):
    """Cases with phase=closed but no closed_at are skipped (not errored)."""
    cm.set_phase(case_id, "closed")

    # Remove closed_at
    meta = cm.storage.get_case_metadata(case_id)
    meta.pop("closed_at", None)
    cm.storage.update_case_metadata(case_id, meta)

    archived_ids = cm.check_auto_archive_closed_cases()
    assert case_id not in archived_ids  # Skipped, not errored


# ---- Phase Configuration CRUD -----------------------------------------------

def test_get_phase_config_returns_defaults(cm):
    config = cm.get_phase_config()
    assert "criminal" in config
    assert "civil-plaintiff" in config
    assert isinstance(config["criminal"], list)
    assert len(config["criminal"]) >= 5


def test_save_and_load_phase_config(cm):
    custom_config = {"criminal": ["Step A", "Step B", "Step C"]}
    cm.save_phase_config(custom_config)
    loaded = cm.get_phase_config()
    assert loaded["criminal"] == ["Step A", "Step B", "Step C"]
    # Default types still merged in
    assert "civil-plaintiff" in loaded


def test_get_sub_phases_for_case(cm, case_id):
    sub_phases = cm.get_sub_phases_for_case(case_id)
    # Default case is criminal type
    assert "Intake" in sub_phases
    assert "Discovery" in sub_phases


def test_get_sub_phases_unknown_type_falls_back(cm, case_id):
    """Unknown case types fall back to 'criminal' sub-phases."""
    meta = cm.storage.get_case_metadata(case_id)
    meta["case_type"] = "alien_law"
    cm.storage.update_case_metadata(case_id, meta)

    sub_phases = cm.get_sub_phases_for_case(case_id)
    # Should fall back to criminal defaults
    assert len(sub_phases) >= 5


# ---- Backward Compatibility --------------------------------------------------

def test_archive_case_legacy_method(cm, case_id):
    cm.archive_case(case_id)
    phase, _ = cm.get_phase(case_id)
    assert phase == "archived"


def test_unarchive_case_legacy_method(cm, case_id):
    cm.archive_case(case_id)
    cm.unarchive_case(case_id)
    phase, _ = cm.get_phase(case_id)
    assert phase == "active"


def test_update_status_syncs_phase(cm, case_id):
    cm.update_status(case_id, "archived")
    meta = cm.storage.get_case_metadata(case_id)
    assert meta["phase"] == "archived"
    assert meta["status"] == "archived"


def test_get_status_derives_from_phase(cm, case_id):
    cm.set_phase(case_id, "closed")
    # Closed phase maps to "active" status for backward compat
    assert cm.get_status(case_id) == "active"

    cm.set_phase(case_id, "archived")
    assert cm.get_status(case_id) == "archived"


# ---- Phase Transition Flow (full lifecycle) ----------------------------------

def test_full_lifecycle_active_to_purged(cm, case_id):
    """Test the complete case lifecycle: Active → Closed → Archived → Purge."""
    # Start active with sub-phase
    cm.set_phase(case_id, "active", sub_phase="Discovery")
    phase, sub = cm.get_phase(case_id)
    assert phase == "active"
    assert sub == "Discovery"

    # Upload a file
    cm.storage.save_file(case_id, "evidence.pdf", b"important evidence")

    # Close the case
    cm.set_phase(case_id, "closed")
    phase, sub = cm.get_phase(case_id)
    assert phase == "closed"
    assert sub == ""

    # Archive the case
    cm.set_phase(case_id, "archived")
    phase, sub = cm.get_phase(case_id)
    assert phase == "archived"

    # Purge source files
    count = cm.purge_source_docs(case_id)
    assert count == 1
    assert cm.get_case_files(case_id) == []

    # Verify metadata
    meta = cm.storage.get_case_metadata(case_id)
    assert meta["purged"] is True
    assert meta["phase"] == "archived"

    # Unarchive should work even after purge
    cm.set_phase(case_id, "active")
    phase, _ = cm.get_phase(case_id)
    assert phase == "active"

    # Purged flag persists
    meta = cm.storage.get_case_metadata(case_id)
    assert meta.get("purged") is True


# ---- list_cases Phase-Aware Filtering ----------------------------------------

def test_list_cases_hides_archived(cm):
    cid1 = cm.create_case("Active Case")
    cid2 = cm.create_case("Archived Case")
    cm.set_phase(cid2, "archived")

    visible = cm.list_cases(include_archived=False)
    visible_ids = [c.get("id", "") for c in visible]
    assert cid1 in visible_ids
    assert cid2 not in visible_ids


def test_list_cases_includes_archived(cm):
    cid1 = cm.create_case("Active Case")
    cid2 = cm.create_case("Archived Case")
    cm.set_phase(cid2, "archived")

    all_cases = cm.list_cases(include_archived=True)
    all_ids = [c.get("id", "") for c in all_cases]
    assert cid1 in all_ids
    assert cid2 in all_ids


def test_list_cases_shows_closed(cm):
    """Closed cases should appear in the default list (not archived)."""
    cid = cm.create_case("Closed Case")
    cm.set_phase(cid, "closed")

    visible = cm.list_cases(include_archived=False)
    visible_ids = [c.get("id", "") for c in visible]
    assert cid in visible_ids


# ---- Storage: purge_source_docs ----------------------------------------------

def test_storage_purge_source_docs(populated_storage):
    storage, case_id = populated_storage
    # Add files
    storage.save_file(case_id, "a.pdf", b"aaa")
    storage.save_file(case_id, "b.pdf", b"bbb")
    assert len(storage.get_case_files(case_id)) == 2

    count = storage.purge_source_docs(case_id)
    assert count == 2
    assert len(storage.get_case_files(case_id)) == 0


def test_storage_purge_empty_dir(populated_storage):
    storage, case_id = populated_storage
    count = storage.purge_source_docs(case_id)
    assert count == 0


# ---- Storage: global JSON ----------------------------------------------------

def test_global_json_round_trip(storage):
    data = {"key": "value", "count": 42}
    storage.save_global_json("test_global.json", data)
    loaded = storage.load_global_json("test_global.json")
    assert loaded == data


def test_global_json_default(storage):
    result = storage.load_global_json("nonexistent.json", default={"x": 1})
    assert result == {"x": 1}


def test_global_json_overwrite(storage):
    storage.save_global_json("cfg.json", {"v": 1})
    storage.save_global_json("cfg.json", {"v": 2})
    assert storage.load_global_json("cfg.json")["v"] == 2


# ---- Activity Logging --------------------------------------------------------

def test_phase_change_logged(cm, case_id):
    cm.set_phase(case_id, "closed")
    log = cm.get_activity_log(case_id, limit=10)
    phase_entries = [e for e in log if e.get("action") == "phase_changed"]
    assert len(phase_entries) >= 1
    assert "closed" in phase_entries[0].get("detail", "").lower()


def test_auto_archive_logged(cm, case_id):
    cm.set_phase(case_id, "closed")
    meta = cm.storage.get_case_metadata(case_id)
    meta["closed_at"] = (datetime.now() - timedelta(days=30)).isoformat()
    cm.storage.update_case_metadata(case_id, meta)

    cm.check_auto_archive_closed_cases()
    log = cm.get_activity_log(case_id, limit=10)
    auto_entries = [e for e in log if e.get("action") == "auto_archived"]
    assert len(auto_entries) >= 1
