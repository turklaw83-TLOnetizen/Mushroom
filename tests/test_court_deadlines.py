"""Tests for court deadline calculator (Phase 17)."""
import pytest
from datetime import date


class TestCourtDeadlines:
    def test_import(self):
        from core.court_deadlines import calculate_deadline, FEDERAL_RULES
        assert calculate_deadline is not None
        assert len(FEDERAL_RULES) > 0

    def test_calculate_deadline_basic(self):
        from core.court_deadlines import calculate_deadline
        result = calculate_deadline(
            rule_type="response_to_complaint",
            start_date=date(2026, 3, 1),
            jurisdiction="federal",
        )
        assert result["deadline"] is not None
        assert result["rule_type"] == "response_to_complaint"

    def test_add_business_days(self):
        from core.court_deadlines import add_business_days
        # Monday March 2, 2026 + 5 business days = Monday March 9, 2026
        result = add_business_days(date(2026, 3, 2), 5)
        assert result.weekday() < 5  # Should be a weekday

    def test_skips_weekends(self):
        from core.court_deadlines import add_business_days
        # Friday + 1 business day should be Monday
        friday = date(2026, 3, 6)
        assert friday.weekday() == 4  # Friday
        result = add_business_days(friday, 1)
        assert result.weekday() == 0  # Monday

    def test_available_rules(self):
        from core.court_deadlines import get_available_rules
        rules = get_available_rules("federal")
        assert len(rules) > 0
        assert any(r["type"] == "response_to_complaint" for r in rules)

    def test_federal_rules_have_days(self):
        from core.court_deadlines import FEDERAL_RULES
        for name, rule in FEDERAL_RULES.items():
            assert "days" in rule, f"Rule {name} missing 'days'"
            assert isinstance(rule["days"], int)
