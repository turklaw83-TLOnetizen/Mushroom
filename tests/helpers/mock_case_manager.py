"""Mock CaseManager for testing without file system side effects.

Provides an in-memory CaseManager that stores cases, preparations,
files, and state in dicts instead of on disk.

Usage:
    from tests.helpers.mock_case_manager import create_mock_case_manager

    def test_something(sample_state):
        cm = create_mock_case_manager()
        cm.create_case("case-1", {"name": "Test"})
        assert cm.get_case("case-1")["name"] == "Test"
"""

from typing import Any
from unittest.mock import MagicMock


def create_mock_case_manager(
    cases: dict[str, dict] | None = None,
    preps: dict[str, list[dict]] | None = None,
    states: dict[str, dict] | None = None,
) -> MagicMock:
    """Create an in-memory mock CaseManager.

    Args:
        cases: Initial {case_id: metadata} dict
        preps: Initial {case_id: [prep_dicts]} dict
        states: Initial {"case_id/prep_id": state_dict} dict
    """
    _cases = dict(cases or {})
    _preps = dict(preps or {})
    _states = dict(states or {})
    _files: dict[str, list[dict]] = {}

    cm = MagicMock()

    # ── Case CRUD ──
    def create_case(case_id: str, metadata: dict) -> dict:
        _cases[case_id] = {**metadata, "id": case_id}
        return _cases[case_id]

    def get_case(case_id: str) -> dict | None:
        return _cases.get(case_id)

    def list_cases() -> list[dict]:
        return list(_cases.values())

    def update_case(case_id: str, updates: dict) -> dict:
        if case_id in _cases:
            _cases[case_id].update(updates)
        return _cases.get(case_id, {})

    def delete_case(case_id: str) -> bool:
        return _cases.pop(case_id, None) is not None

    def case_exists(case_id: str) -> bool:
        return case_id in _cases

    cm.create_case.side_effect = create_case
    cm.get_case.side_effect = get_case
    cm.list_cases.side_effect = list_cases
    cm.update_case.side_effect = update_case
    cm.delete_case.side_effect = delete_case
    cm.case_exists.side_effect = case_exists

    # ── Preparation CRUD ──
    def create_preparation(case_id: str, prep: dict) -> dict:
        _preps.setdefault(case_id, []).append(prep)
        return prep

    def list_preparations(case_id: str) -> list[dict]:
        return _preps.get(case_id, [])

    def get_preparation(case_id: str, prep_id: str) -> dict | None:
        for p in _preps.get(case_id, []):
            if p.get("id") == prep_id:
                return p
        return None

    cm.create_preparation.side_effect = create_preparation
    cm.list_preparations.side_effect = list_preparations
    cm.get_preparation.side_effect = get_preparation

    # ── State ──
    def save_state(case_id: str, prep_id: str, state: dict) -> None:
        _states[f"{case_id}/{prep_id}"] = state

    def load_state(case_id: str, prep_id: str) -> dict | None:
        return _states.get(f"{case_id}/{prep_id}")

    cm.save_state.side_effect = save_state
    cm.load_state.side_effect = load_state

    # ── Files ──
    def list_files(case_id: str) -> list[dict]:
        return _files.get(case_id, [])

    def save_file(case_id: str, filename: str, content: bytes) -> dict:
        file_info = {"filename": filename, "size": len(content)}
        _files.setdefault(case_id, []).append(file_info)
        return file_info

    cm.list_files.side_effect = list_files
    cm.save_file.side_effect = save_file

    # ── Expose internal stores for assertions ──
    cm._cases = _cases
    cm._preps = _preps
    cm._states = _states
    cm._files = _files

    return cm
