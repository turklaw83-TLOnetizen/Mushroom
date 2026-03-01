# ---- API Integration Tests -----------------------------------------------
# Tests for critical API endpoints: health, auth, CRUD, middleware.
# Run: pytest tests/ -v

import pytest
from unittest.mock import patch, MagicMock


# ---- Health Check ----

class TestHealthCheck:
    def test_health_endpoint_exists(self):
        """Health endpoint should be registered."""
        from api.main import app
        routes = [r.path for r in app.routes]
        assert "/api/v1/health" in routes or any("/health" in r for r in routes)


# ---- Input Sanitization ----

class TestInputSanitization:
    def test_xss_detection(self):
        from api.input_sanitize import _scan_value
        assert _scan_value("<script>alert('xss')</script>") == "XSS"
        assert _scan_value("normal text") is None
        assert _scan_value("javascript:void(0)") == "XSS"
        assert _scan_value("<iframe src='evil.com'>") == "XSS"

    def test_sql_injection_detection(self):
        from api.input_sanitize import _scan_value
        assert _scan_value("' OR '1'='1'") == "SQL_INJECTION"
        assert _scan_value("SELECT * FROM users") == "SQL_INJECTION"
        assert _scan_value("normal query text") is None

    def test_nested_dict_scanning(self):
        from api.input_sanitize import _scan_dict
        assert _scan_dict({"name": "safe", "email": "test@test.com"}) is None
        assert _scan_dict({"name": "<script>evil</script>"}) is not None
        assert _scan_dict({"nested": {"deep": "DROP TABLE users"}}) is not None


# ---- Pagination ----

class TestPagination:
    def test_paginate_basic(self):
        from api.pagination import paginate
        result = paginate(items=[1, 2, 3], total=10, page=1, page_size=3)
        assert result.total == 10
        assert result.page == 1
        assert result.has_next is True
        assert result.has_prev is False
        assert result.total_pages == 4

    def test_paginate_last_page(self):
        from api.pagination import paginate
        result = paginate(items=[10], total=10, page=4, page_size=3)
        assert result.has_next is False
        assert result.has_prev is True

    def test_max_page_size_enforced(self):
        from api.pagination import paginate, MAX_PAGE_SIZE
        result = paginate(items=[], total=1000, page=1, page_size=9999)
        assert result.page_size == MAX_PAGE_SIZE


# ---- Upload Limit ----

class TestUploadLimit:
    def test_default_limit(self):
        from api.upload_limit import DEFAULT_MAX_SIZE
        assert DEFAULT_MAX_SIZE == 20 * 1024 * 1024 * 1024  # 20GB


# ---- Encryption Check ----

class TestEncryptionCheck:
    @patch.dict("os.environ", {"ENCRYPTION_KEY": ""}, clear=False)
    def test_no_key_returns_false(self):
        from api.encryption_check import verify_encryption
        result = verify_encryption()
        assert result["key_configured"] is False

    @patch.dict("os.environ", {"ENCRYPTION_KEY": "test-key-256-bit"}, clear=False)
    def test_key_present(self):
        from api.encryption_check import verify_encryption
        result = verify_encryption()
        assert result["key_configured"] is True


# ---- Environment Validation ----

class TestEnvValidation:
    def test_optional_defaults(self):
        from api.env import OPTIONAL_VARS
        assert "CORS_ORIGINS" in OPTIONAL_VARS
        assert "RATE_LIMIT_REQUESTS" in OPTIONAL_VARS
        assert "MAX_UPLOAD_SIZE_BYTES" in OPTIONAL_VARS


# ---- SOL Periods ----

class TestSOLPeriods:
    def test_all_case_types_have_defaults(self):
        from api.routers.sol import SOL_PERIODS
        for case_type, periods in SOL_PERIODS.items():
            assert "default" in periods, f"{case_type} missing default SOL period"

    def test_personal_injury_california(self):
        from api.routers.sol import SOL_PERIODS
        assert SOL_PERIODS["personal_injury"]["CA"] == 2

    def test_breach_of_contract_new_york(self):
        from api.routers.sol import SOL_PERIODS
        assert SOL_PERIODS["breach_of_contract"]["NY"] == 6
