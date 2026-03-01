# ---- Shared Test Fixtures -------------------------------------------------
# Provides tmp directories, mock storage backends, and sample data for all tests.

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so `import core.*` works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Set test environment variables BEFORE importing app code (Fix #5)
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("CLERK_SECRET_KEY", "")  # Disable Clerk in tests

from core.storage.json_backend import JSONStorageBackend


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def storage(tmp_data_dir):
    """Provide a JSONStorageBackend backed by a temp directory."""
    return JSONStorageBackend(tmp_data_dir)


@pytest.fixture
def sample_case_metadata():
    """Return a sample case metadata dict."""
    return {
        "id": "test_case__abc123",
        "name": "Test Case",
        "description": "A test case for unit tests",
        "status": "active",
        "case_type": "criminal",
        "case_category": "",
        "case_subcategory": "",
        "client_name": "John Doe",
        "assigned_to": [],
        "created_at": "2026-01-15T10:00:00",
        "last_updated": "2026-01-15T10:00:00",
    }


@pytest.fixture
def populated_storage(storage, sample_case_metadata):
    """Provide a storage backend with one case already created."""
    case_id = sample_case_metadata["id"]
    storage.create_case(case_id, sample_case_metadata)
    return storage, case_id


@pytest.fixture
def sample_state():
    """Return a sample analysis state dict."""
    return {
        "case_summary": "Test summary of the case.",
        "charges": [
            {"name": "Assault", "statute_number": "39-13-101", "level": "Misdemeanor A"},
        ],
        "witnesses": [
            {"name": "Officer Smith", "type": "State", "goal": "Testify about arrest"},
            {"name": "Jane Doe", "type": "Defense", "goal": "Alibi witness"},
        ],
        "timeline": [
            {"year": "2025", "month": "06", "day": "15", "headline": "Incident", "text": "The alleged incident occurred."},
        ],
        "evidence_foundations": [],
        "consistency_check": [],
        "legal_elements": [],
        "investigation_plan": [
            {"action": "Obtain security footage", "reason": "Verify timeline", "priority": "High"},
        ],
        "strategy_notes": "Focus on alibi defense.",
        "devils_advocate_notes": "",
        "cross_examination_plan": [],
        "direct_examination_plan": [],
        "entities": [
            {"id": "e1", "name": "Officer Smith", "type": "PERSON", "context": "Arresting officer"},
        ],
        "voir_dire": {},
        "mock_jury_feedback": [],
        "legal_research_data": [],
        "drafted_documents": [],
        "current_model": "anthropic",
        "case_type": "criminal",
        "raw_documents": [],
    }


# ---- API Test Fixtures (Fix #5: merged from test_api_conftest.py) --------

@pytest.fixture
def auth_token():
    """Generate a valid JWT token for testing."""
    from api.auth import _create_jwt
    return _create_jwt(user_id="test_admin", role="admin", name="Test Admin")


@pytest.fixture
def auth_headers(auth_token):
    """Return authorization headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def attorney_token():
    """Generate a JWT token with attorney role."""
    from api.auth import _create_jwt
    return _create_jwt(user_id="test_attorney", role="attorney", name="Test Attorney")


@pytest.fixture
def attorney_headers(attorney_token):
    return {"Authorization": f"Bearer {attorney_token}"}
