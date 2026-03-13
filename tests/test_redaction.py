"""Tests for core/redaction.py — regex PII scanning and redaction."""

import pytest

from core.redaction import (
    REDACTION_CATEGORIES,
    _regex_scan,
    apply_redactions,
    generate_redaction_log,
)
from tests.helpers.fixtures import SAMPLE_PII_TEXT, SAMPLE_REDACTION_FINDINGS


# ---------------------------------------------------------------------------
# Category Definitions
# ---------------------------------------------------------------------------

class TestCategories:
    def test_all_categories_present(self):
        expected = {"ssn", "phone", "email", "credit_card", "dob", "address",
                    "medical", "financial", "privilege", "work_product"}
        assert set(REDACTION_CATEGORIES.keys()) == expected

    def test_each_has_label(self):
        for cat, info in REDACTION_CATEGORIES.items():
            assert "label" in info, f"Category {cat} missing label"

    def test_regex_categories_have_patterns(self):
        regex_cats = {"ssn", "phone", "email", "credit_card", "financial"}
        for cat in regex_cats:
            assert REDACTION_CATEGORIES[cat]["pattern"] is not None

    def test_llm_categories_have_no_patterns(self):
        llm_cats = {"dob", "address", "medical", "privilege", "work_product"}
        for cat in llm_cats:
            assert REDACTION_CATEGORIES[cat]["pattern"] is None


# ---------------------------------------------------------------------------
# Regex Scanning
# ---------------------------------------------------------------------------

class TestRegexScan:
    def test_detects_ssn(self):
        text = "SSN: 123-45-6789"
        results = _regex_scan(text, ["ssn"])
        assert len(results) == 1
        assert results[0]["category"] == "ssn"
        assert results[0]["text"] == "123-45-6789"

    def test_detects_email(self):
        text = "Contact: user@example.com for details"
        results = _regex_scan(text, ["email"])
        assert len(results) == 1
        assert results[0]["category"] == "email"
        assert results[0]["text"] == "user@example.com"

    def test_detects_phone(self):
        text = "Call (615) 555-0123 anytime"
        results = _regex_scan(text, ["phone"])
        assert len(results) >= 1
        assert any(r["category"] == "phone" for r in results)

    def test_multiple_categories(self):
        text = "SSN: 123-45-6789, Email: test@law.com"
        results = _regex_scan(text, ["ssn", "email"])
        categories = {r["category"] for r in results}
        assert "ssn" in categories
        assert "email" in categories

    def test_no_findings_clean_text(self):
        text = "This is a clean document with no PII."
        results = _regex_scan(text, ["ssn", "phone", "email"])
        assert len(results) == 0

    def test_ignores_llm_categories(self):
        text = "Born on January 15, 1990"  # DOB requires LLM, not regex
        results = _regex_scan(text, ["dob"])
        assert len(results) == 0

    def test_findings_have_required_fields(self):
        text = "SSN: 123-45-6789"
        results = _regex_scan(text, ["ssn"])
        assert len(results) == 1
        f = results[0]
        assert "category" in f
        assert "text" in f
        assert "start" in f
        assert "end" in f
        assert "confidence" in f
        assert "source" in f
        assert f["source"] == "regex"

    def test_context_window(self):
        text = "word " * 20 + "SSN: 123-45-6789 " + "more " * 20
        results = _regex_scan(text, ["ssn"])
        assert len(results) == 1
        ctx = results[0]["context"]
        # Context should be bounded (~50 chars each side + match)
        assert len(ctx) <= 150

    def test_sample_pii_text(self):
        results = _regex_scan(SAMPLE_PII_TEXT, ["ssn", "phone", "email"])
        cats = {r["category"] for r in results}
        assert "ssn" in cats
        assert "email" in cats


# ---------------------------------------------------------------------------
# Apply Redactions
# ---------------------------------------------------------------------------

class TestApplyRedactions:
    def test_blackout_style(self):
        text = "SSN: 123-45-6789"
        findings = [{"category": "ssn", "text": "123-45-6789", "start": 5, "end": 16}]
        result = apply_redactions(text, findings, "blackout")
        assert "[REDACTED]" in result
        assert "123-45-6789" not in result

    def test_category_style(self):
        text = "SSN: 123-45-6789"
        findings = [{"category": "ssn", "text": "123-45-6789", "start": 5, "end": 16}]
        result = apply_redactions(text, findings, "category")
        assert "[REDACTED - Social Security Numbers]" in result

    def test_no_findings_returns_original(self):
        text = "Clean text"
        assert apply_redactions(text, [], "blackout") == text

    def test_multiple_redactions(self):
        text = "SSN: 123-45-6789 and 987-65-4321"
        findings = [
            {"category": "ssn", "text": "123-45-6789", "start": 5, "end": 16},
            {"category": "ssn", "text": "987-65-4321", "start": 21, "end": 32},
        ]
        result = apply_redactions(text, findings, "blackout")
        assert result.count("[REDACTED]") == 2
        assert "123-45-6789" not in result
        assert "987-65-4321" not in result


# ---------------------------------------------------------------------------
# Redaction Log
# ---------------------------------------------------------------------------

class TestRedactionLog:
    def test_generates_log(self):
        log = generate_redaction_log(SAMPLE_REDACTION_FINDINGS, "test_document.pdf")
        assert log is not None
        assert "entries" in log or "log" in log or isinstance(log, (dict, str))
