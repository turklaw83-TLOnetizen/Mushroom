"""Tests for core/war_game.py — session management and round mechanics."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.helpers.fixtures import (
    SAMPLE_ANALYSIS_STATE,
    SAMPLE_CRIMINAL_CASE,
    SAMPLE_PREP,
    SAMPLE_WAR_GAME_SESSION,
)
from tests.helpers.mock_llm import MockAIMessage, patch_llm_in_module


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

from core.war_game import (
    DIFFICULTY_PERSONAS,
    ROUND_TYPES,
    create_session,
    save_war_game_session,
    load_war_game_session,
    load_war_game_sessions,
    delete_war_game_session,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_round_types(self):
        assert ROUND_TYPES == ["theory", "evidence", "witnesses", "elements", "jury"]

    def test_difficulty_levels(self):
        assert set(DIFFICULTY_PERSONAS.keys()) == {"standard", "aggressive", "ruthless"}


# ---------------------------------------------------------------------------
# Session Creation
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_creates_session_with_defaults(self):
        session = create_session()
        assert session["difficulty"] == "standard"
        assert session["status"] == "active"
        assert session["current_round"] == 0
        assert len(session["rounds"]) == 5
        assert session["report"] is None

    def test_creates_session_with_difficulty(self):
        session = create_session(difficulty="ruthless")
        assert session["difficulty"] == "ruthless"

    def test_all_rounds_start_pending(self):
        session = create_session()
        for i, round_data in enumerate(session["rounds"]):
            assert round_data["type"] == ROUND_TYPES[i]
            assert round_data["status"] == "pending"
            assert round_data["attack"] is None
            assert round_data["response"] is None
            assert round_data["evaluation"] is None

    def test_session_has_id(self):
        session = create_session()
        assert "id" in session
        assert len(session["id"]) > 0

    def test_session_has_timestamps(self):
        session = create_session()
        assert "created_at" in session
        assert "updated_at" in session


# ---------------------------------------------------------------------------
# Session Persistence
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    def test_save_and_load(self, tmp_data_dir):
        session = create_session(difficulty="aggressive")
        case_id = "case__test_001"
        prep_id = "prep_trial_001"

        session_id = save_war_game_session(tmp_data_dir, case_id, prep_id, session)
        loaded = load_war_game_session(tmp_data_dir, case_id, prep_id, session_id)

        assert loaded is not None
        assert loaded["id"] == session_id
        assert loaded["difficulty"] == "aggressive"
        assert len(loaded["rounds"]) == 5

    def test_load_nonexistent_returns_none(self, tmp_data_dir):
        result = load_war_game_session(tmp_data_dir, "case__x", "prep_x", "nosuch")
        assert result is None

    def test_list_sessions(self, tmp_data_dir):
        case_id = "case__test_001"
        prep_id = "prep_trial_001"

        s1 = create_session(difficulty="standard")
        s2 = create_session(difficulty="aggressive")
        save_war_game_session(tmp_data_dir, case_id, prep_id, s1)
        save_war_game_session(tmp_data_dir, case_id, prep_id, s2)

        sessions = load_war_game_sessions(tmp_data_dir, case_id, prep_id)
        assert len(sessions) == 2

    def test_list_empty(self, tmp_data_dir):
        sessions = load_war_game_sessions(tmp_data_dir, "case__x", "prep_x")
        assert sessions == []

    def test_delete_session(self, tmp_data_dir):
        case_id = "case__test_001"
        prep_id = "prep_trial_001"
        session = create_session()
        session_id = save_war_game_session(tmp_data_dir, case_id, prep_id, session)

        result = delete_war_game_session(tmp_data_dir, case_id, prep_id, session_id)
        assert result is True

        loaded = load_war_game_session(tmp_data_dir, case_id, prep_id, session_id)
        assert loaded is None

    def test_delete_nonexistent_returns_false(self, tmp_data_dir):
        result = delete_war_game_session(tmp_data_dir, "case__x", "prep_x", "nosuch")
        assert result is False

    def test_save_updates_timestamp(self, tmp_data_dir):
        case_id = "case__test_001"
        prep_id = "prep_trial_001"
        session = create_session()
        save_war_game_session(tmp_data_dir, case_id, prep_id, session)

        ts1 = session["updated_at"]
        save_war_game_session(tmp_data_dir, case_id, prep_id, session)
        loaded = load_war_game_session(tmp_data_dir, case_id, prep_id, session["id"])
        assert loaded["updated_at"] >= ts1
