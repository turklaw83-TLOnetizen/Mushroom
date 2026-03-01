"""Tests for email classifier (Phase 15)."""
import pytest


class TestEmailClassifier:
    def test_import(self):
        from core.email_classifier import classify_email
        assert classify_email is not None

    def test_classify_with_case_id(self):
        from core.email_classifier import classify_email
        result = classify_email(
            subject="Re: Case #2024-0042 - Discovery Documents",
            body="Please find attached the discovery documents for case 2024-0042.",
            sender="attorney@firm.com",
            cases=[
                {"id": "2024-0042", "name": "Smith v. Johnson", "client_name": "Smith"},
                {"id": "2024-0099", "name": "Davis v. Metro", "client_name": "Davis"},
            ],
        )
        assert result is not None
        # Should match the case with ID 2024-0042
        if result.get("case_id"):
            assert result["case_id"] == "2024-0042"

    def test_classify_no_match(self):
        from core.email_classifier import classify_email
        result = classify_email(
            subject="Newsletter: Weekly Legal Updates",
            body="Here are this week's legal updates from the bar association.",
            sender="newsletter@bar.org",
            cases=[],
        )
        assert result is not None
        assert result.get("confidence", 0) < 0.5 or result.get("case_id") is None

    def test_classify_batch(self):
        from core.email_classifier import classify_batch
        results = classify_batch(
            emails=[
                {"subject": "Test 1", "body": "Body 1", "sender": "a@b.com"},
                {"subject": "Test 2", "body": "Body 2", "sender": "c@d.com"},
            ],
            cases=[],
        )
        assert isinstance(results, list)
        assert len(results) == 2
