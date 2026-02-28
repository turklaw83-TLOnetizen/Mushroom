# ---- Tests for core/append_only.py ----------------------------------------

import pytest
from core.append_only import (
    APPEND_ONLY_KEYS,
    merge_append_only,
    safe_update_and_save,
)


class TestMergeAppendOnly:
    def test_new_items_appended(self):
        existing = {
            "witnesses": [{"name": "Alice", "type": "State"}],
            "case_summary": "Old summary",
        }
        new = {
            "witnesses": [
                {"name": "Alice", "type": "State"},
                {"name": "Bob", "type": "Defense"},
            ],
            "case_summary": "New summary",
        }
        merged = merge_append_only(existing, new)
        names = {w["name"] for w in merged["witnesses"]}
        assert "Alice" in names
        assert "Bob" in names
        # Text field overwritten
        assert merged["case_summary"] == "New summary"

    def test_existing_items_never_removed(self):
        existing = {
            "witnesses": [
                {"name": "Alice", "type": "State"},
                {"name": "Charlie", "type": "Expert"},
            ],
        }
        new = {
            "witnesses": [{"name": "Alice", "type": "State"}],
        }
        merged = merge_append_only(existing, new)
        names = {w["name"] for w in merged["witnesses"]}
        assert "Charlie" in names  # Still present
        # Charlie should be flagged
        charlie = [w for w in merged["witnesses"] if w["name"] == "Charlie"][0]
        assert charlie.get("_ai_suggests_remove") is True

    def test_user_added_items_never_flagged(self):
        existing = {
            "investigation_plan": [
                {"action": "Check alibis", "_user_added": True},
            ],
        }
        new = {
            "investigation_plan": [{"action": "Something else"}],
        }
        merged = merge_append_only(existing, new)
        user_item = [i for i in merged["investigation_plan"]
                     if i.get("action") == "Check alibis"][0]
        assert "_ai_suggests_remove" not in user_item

    def test_empty_new_state_preserves_existing(self):
        existing = {
            "charges": [{"name": "Assault"}],
        }
        new = {
            "charges": [],
        }
        merged = merge_append_only(existing, new)
        # Empty new list = don't touch existing
        assert len(merged["charges"]) == 1

    def test_non_append_keys_overwritten(self):
        existing = {
            "case_summary": "Old",
            "strategy_notes": "Old strategy",
        }
        new = {
            "case_summary": "New",
            "strategy_notes": "New strategy",
        }
        merged = merge_append_only(existing, new)
        assert merged["case_summary"] == "New"
        assert merged["strategy_notes"] == "New strategy"

    def test_all_append_only_keys_present(self):
        """Verify the key list matches expected length."""
        assert len(APPEND_ONLY_KEYS) == 13

    def test_flag_cleared_on_reproduced(self):
        existing = {
            "witnesses": [
                {"name": "Alice", "type": "State", "_ai_suggests_remove": True},
            ],
        }
        new = {
            "witnesses": [{"name": "Alice", "type": "State"}],
        }
        merged = merge_append_only(existing, new)
        alice = merged["witnesses"][0]
        assert "_ai_suggests_remove" not in alice


class TestSafeUpdateAndSave:
    def test_calls_save_fn(self):
        saved = []
        def mock_save(state):
            saved.append(state)

        result = safe_update_and_save(
            {"witnesses": [{"name": "A"}]},
            {"witnesses": [{"name": "A"}, {"name": "B"}]},
            mock_save,
        )
        assert len(saved) == 1
        assert len(result["witnesses"]) == 2
