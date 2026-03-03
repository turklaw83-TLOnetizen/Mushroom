"""
Tests for core.user_profiles — UserManager RBAC, authentication, and case assignment.
"""

import json
import hashlib
import os

import pytest

import core.user_profiles as up
from core.user_profiles import UserManager, _hash_pin, ROLES


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_user_dir(tmp_path, monkeypatch):
    """Redirect _USERS_DIR and _PROFILES_FILE to a temp directory for every test."""
    users_dir = str(tmp_path / "users")
    profiles_file = os.path.join(users_dir, "profiles.json")
    monkeypatch.setattr(up, "_USERS_DIR", users_dir)
    monkeypatch.setattr(up, "_PROFILES_FILE", profiles_file)
    return users_dir, profiles_file


@pytest.fixture
def mgr():
    """Return a fresh UserManager (auto-seeds defaults because no file exists)."""
    return UserManager()


# ---------------------------------------------------------------------------
#  _hash_pin
# ---------------------------------------------------------------------------

class TestHashPin:

    def test_consistent_sha256(self):
        expected = hashlib.sha256(b"1234").hexdigest()
        assert _hash_pin("1234") == expected
        # Same input always yields same hash
        assert _hash_pin("1234") == _hash_pin("1234")

    def test_empty_input_returns_empty_string(self):
        assert _hash_pin("") == ""

    def test_none_like_empty(self):
        # The function guards with `if not pin`, so "" is the only real "empty"
        # but verifying empty string path is sufficient.
        assert _hash_pin("") == ""


# ---------------------------------------------------------------------------
#  _load / seed defaults
# ---------------------------------------------------------------------------

class TestLoadAndSeed:

    def test_seeds_defaults_when_no_file(self, mgr):
        """First instantiation should create 2 default admin users."""
        users = mgr.list_users()
        assert len(users) == 2
        ids = {u["id"] for u in users}
        assert "djt-49a" in ids
        assert "crj-82b" in ids

    def test_seeded_profiles_are_admin(self, mgr):
        for uid in ("djt-49a", "crj-82b"):
            u = mgr.get_user(uid)
            assert u is not None
            assert u["role"] == "admin"
            assert u["active"] is True

    def test_profiles_persisted_to_disk(self, isolate_user_dir, mgr):
        _, profiles_file = isolate_user_dir
        assert os.path.exists(profiles_file)
        with open(profiles_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 2


# ---------------------------------------------------------------------------
#  list_users
# ---------------------------------------------------------------------------

class TestListUsers:

    def test_returns_active_only_by_default(self, mgr):
        mgr.deactivate_user("crj-82b")
        active = mgr.list_users()
        assert all(u["active"] for u in active)
        assert len(active) == 1

    def test_include_inactive_returns_all(self, mgr):
        mgr.deactivate_user("crj-82b")
        all_users = mgr.list_users(include_inactive=True)
        assert len(all_users) == 2


# ---------------------------------------------------------------------------
#  get_user
# ---------------------------------------------------------------------------

class TestGetUser:

    def test_finds_existing_user(self, mgr):
        user = mgr.get_user("djt-49a")
        assert user is not None
        assert user["name"] == "Daniel Joseph Turklay"

    def test_returns_none_for_nonexistent(self, mgr):
        assert mgr.get_user("no-such-id") is None


# ---------------------------------------------------------------------------
#  create_user
# ---------------------------------------------------------------------------

class TestCreateUser:

    def test_valid_role(self, mgr):
        user = mgr.create_user("Alice Wonderland", role="attorney")
        assert user["role"] == "attorney"
        assert user["active"] is True
        assert user["name"] == "Alice Wonderland"
        # Persisted: should now appear in list
        assert mgr.get_user(user["id"]) is not None

    def test_invalid_role_raises(self, mgr):
        with pytest.raises(ValueError, match="Invalid role"):
            mgr.create_user("Bob Builder", role="janitor")

    def test_auto_generates_initials(self, mgr):
        user = mgr.create_user("John Michael Smith")
        assert user["initials"] == "JMS"

    def test_explicit_initials_preserved(self, mgr):
        user = mgr.create_user("John Michael Smith", initials="JS")
        assert user["initials"] == "JS"

    def test_pin_is_hashed(self, mgr):
        user = mgr.create_user("Secure User", pin="9999")
        expected_hash = hashlib.sha256(b"9999").hexdigest()
        assert user["pin_hash"] == expected_hash

    def test_no_pin_yields_empty_hash(self, mgr):
        user = mgr.create_user("Open User")
        assert user["pin_hash"] == ""

    def test_google_email_stored(self, mgr):
        user = mgr.create_user("Gmail User", google_email="guser@gmail.com")
        assert user["google_email"] == "guser@gmail.com"


# ---------------------------------------------------------------------------
#  update_user
# ---------------------------------------------------------------------------

class TestUpdateUser:

    def test_updates_fields_and_persists(self, mgr, isolate_user_dir):
        mgr.update_user("djt-49a", {"email": "djt@example.com"})
        user = mgr.get_user("djt-49a")
        assert user["email"] == "djt@example.com"
        # Re-load from disk to confirm persistence
        _, profiles_file = isolate_user_dir
        with open(profiles_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        djt = next(u for u in data if u["id"] == "djt-49a")
        assert djt["email"] == "djt@example.com"

    def test_hashes_pin_field(self, mgr):
        mgr.update_user("djt-49a", {"pin": "5555"})
        user = mgr.get_user("djt-49a")
        expected = hashlib.sha256(b"5555").hexdigest()
        assert user["pin_hash"] == expected
        assert "pin" not in user  # raw pin should not be stored

    def test_prevents_changing_id(self, mgr):
        original_id = "djt-49a"
        mgr.update_user(original_id, {"id": "hacker-id"})
        # id must remain unchanged
        assert mgr.get_user(original_id) is not None
        assert mgr.get_user("hacker-id") is None

    def test_prevents_changing_created_at(self, mgr):
        original = mgr.get_user("djt-49a")["created_at"]
        mgr.update_user("djt-49a", {"created_at": "2000-01-01T00:00:00"})
        assert mgr.get_user("djt-49a")["created_at"] == original

    def test_returns_false_for_nonexistent(self, mgr):
        assert mgr.update_user("ghost", {"email": "x"}) is False


# ---------------------------------------------------------------------------
#  deactivate / reactivate
# ---------------------------------------------------------------------------

class TestDeactivateReactivate:

    def test_deactivate_marks_inactive(self, mgr):
        assert mgr.deactivate_user("crj-82b") is True
        user = mgr.get_user("crj-82b")
        assert user["active"] is False

    def test_reactivate_marks_active(self, mgr):
        mgr.deactivate_user("crj-82b")
        assert mgr.reactivate_user("crj-82b") is True
        user = mgr.get_user("crj-82b")
        assert user["active"] is True


# ---------------------------------------------------------------------------
#  authenticate
# ---------------------------------------------------------------------------

class TestAuthenticate:

    def test_correct_pin(self, mgr):
        mgr.update_user("djt-49a", {"pin": "1234"})
        assert mgr.authenticate("djt-49a", "1234") is True

    def test_wrong_pin(self, mgr):
        mgr.update_user("djt-49a", {"pin": "1234"})
        assert mgr.authenticate("djt-49a", "0000") is False

    def test_no_pin_set_allows_access(self, mgr):
        # Default seeds have no PIN
        assert mgr.authenticate("djt-49a") is True

    def test_fails_for_inactive_user(self, mgr):
        mgr.deactivate_user("crj-82b")
        assert mgr.authenticate("crj-82b") is False

    def test_fails_for_nonexistent_user(self, mgr):
        assert mgr.authenticate("nobody") is False


# ---------------------------------------------------------------------------
#  record_login
# ---------------------------------------------------------------------------

class TestRecordLogin:

    def test_updates_last_login(self, mgr):
        assert mgr.get_user("djt-49a")["last_login"] is None
        mgr.record_login("djt-49a")
        last_login = mgr.get_user("djt-49a")["last_login"]
        assert last_login is not None
        # Should be a valid ISO timestamp
        assert "T" in last_login


# ---------------------------------------------------------------------------
#  Google account linking
# ---------------------------------------------------------------------------

class TestGoogleAccount:

    def test_find_by_google_email_case_insensitive(self, mgr):
        mgr.link_google_account("djt-49a", "DJT@Gmail.COM")
        found = mgr.find_by_google_email("djt@gmail.com")
        assert found is not None
        assert found["id"] == "djt-49a"

    def test_find_by_google_email_returns_none_for_no_match(self, mgr):
        assert mgr.find_by_google_email("nobody@nowhere.com") is None

    def test_find_by_google_email_returns_none_for_empty(self, mgr):
        assert mgr.find_by_google_email("") is None

    def test_find_by_google_email_skips_inactive(self, mgr):
        mgr.link_google_account("crj-82b", "crj@gmail.com")
        mgr.deactivate_user("crj-82b")
        assert mgr.find_by_google_email("crj@gmail.com") is None

    def test_link_google_account_stores_email_and_sub(self, mgr):
        result = mgr.link_google_account("djt-49a", "djt@gmail.com", sub="google-sub-123")
        assert result is True
        user = mgr.get_user("djt-49a")
        assert user["google_email"] == "djt@gmail.com"
        assert user["google_sub"] == "google-sub-123"

    def test_link_google_account_nonexistent_user(self, mgr):
        assert mgr.link_google_account("ghost", "x@y.com") is False


# ---------------------------------------------------------------------------
#  Case assignment
# ---------------------------------------------------------------------------

class TestCaseAssignment:

    def test_assign_case(self, mgr):
        result = mgr.assign_case("djt-49a", "case-001")
        assert result is True
        user = mgr.get_user("djt-49a")
        assert "case-001" in user["assigned_cases"]

    def test_assign_case_idempotent(self, mgr):
        mgr.assign_case("djt-49a", "case-001")
        mgr.assign_case("djt-49a", "case-001")
        user = mgr.get_user("djt-49a")
        assert user["assigned_cases"].count("case-001") == 1

    def test_unassign_case(self, mgr):
        mgr.assign_case("djt-49a", "case-001")
        result = mgr.unassign_case("djt-49a", "case-001")
        assert result is True
        assert "case-001" not in mgr.get_user("djt-49a")["assigned_cases"]

    def test_unassign_case_not_assigned(self, mgr):
        # Unassign a case that was never assigned
        assert mgr.unassign_case("djt-49a", "case-999") is False

    def test_assign_case_nonexistent_user(self, mgr):
        assert mgr.assign_case("ghost", "case-001") is False

    def test_unassign_case_nonexistent_user(self, mgr):
        assert mgr.unassign_case("ghost", "case-001") is False


# ---------------------------------------------------------------------------
#  get_cases_for_user / get_users_for_case
# ---------------------------------------------------------------------------

class TestCaseAccess:

    def test_admin_gets_none_meaning_all_access(self, mgr):
        result = mgr.get_cases_for_user("djt-49a")
        assert result is None  # None = unrestricted

    def test_attorney_gets_assigned_list(self, mgr):
        attorney = mgr.create_user("Test Attorney", role="attorney")
        mgr.assign_case(attorney["id"], "case-A")
        mgr.assign_case(attorney["id"], "case-B")
        cases = mgr.get_cases_for_user(attorney["id"])
        assert set(cases) == {"case-A", "case-B"}

    def test_nonexistent_user_gets_empty_list(self, mgr):
        assert mgr.get_cases_for_user("ghost") == []

    def test_get_users_for_case_includes_admins(self, mgr):
        attorney = mgr.create_user("Assigned Attorney", role="attorney")
        mgr.assign_case(attorney["id"], "case-X")
        users = mgr.get_users_for_case("case-X")
        ids = {u["id"] for u in users}
        # Both seeded admins should be included automatically
        assert "djt-49a" in ids
        assert "crj-82b" in ids
        # The assigned attorney should also be included
        assert attorney["id"] in ids

    def test_get_users_for_case_excludes_inactive_admin(self, mgr):
        mgr.deactivate_user("crj-82b")
        users = mgr.get_users_for_case("case-Y")
        ids = {u["id"] for u in users}
        assert "crj-82b" not in ids

    def test_get_users_for_case_excludes_unassigned_attorney(self, mgr):
        attorney = mgr.create_user("Unassigned Attorney", role="attorney")
        users = mgr.get_users_for_case("case-Z")
        ids = {u["id"] for u in users}
        assert attorney["id"] not in ids


# ---------------------------------------------------------------------------
#  is_admin
# ---------------------------------------------------------------------------

class TestIsAdmin:

    def test_returns_true_for_admin(self, mgr):
        assert mgr.is_admin("djt-49a") is True

    def test_returns_false_for_attorney(self, mgr):
        attorney = mgr.create_user("Lawyer", role="attorney")
        assert mgr.is_admin(attorney["id"]) is False

    def test_returns_false_for_nonexistent(self, mgr):
        assert mgr.is_admin("ghost") is False


# ---------------------------------------------------------------------------
#  get_team_stats
# ---------------------------------------------------------------------------

class TestGetTeamStats:

    def test_default_stats(self, mgr):
        stats = mgr.get_team_stats()
        assert stats["total"] == 2
        assert stats["active"] == 2
        assert stats["admins"] == 2
        assert stats["attorneys"] == 0
        assert stats["paralegals"] == 0

    def test_stats_after_adding_users(self, mgr):
        mgr.create_user("Atty One", role="attorney")
        mgr.create_user("Para One", role="paralegal")
        mgr.create_user("Inactive Atty", role="attorney")
        mgr.deactivate_user(mgr.list_users(include_inactive=True)[-1]["id"])
        stats = mgr.get_team_stats()
        assert stats["total"] == 5
        assert stats["active"] == 4
        assert stats["admins"] == 2
        assert stats["attorneys"] == 1
        assert stats["paralegals"] == 1
