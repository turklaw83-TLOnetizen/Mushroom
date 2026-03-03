"""Tests for the core/exceptions.py exception hierarchy.

Verifies:
  - All exceptions inherit from MushroomCloudError
  - Exception messages propagate correctly
  - LLMRateLimitError is an LLMError (and a MushroomCloudError)
"""

import pytest
from core.exceptions import (
    MushroomCloudError,
    LLMError,
    LLMRateLimitError,
    LLMAuthError,
    LLMProviderError,
    StorageError,
    CaseNotFoundError,
    PrepNotFoundError,
    ValidationError,
    AuthorizationError,
)


class TestMushroomCloudErrorBase:
    """The base exception should work as a standard Python exception."""

    def test_can_be_raised(self):
        with pytest.raises(MushroomCloudError):
            raise MushroomCloudError("something went wrong")

    def test_message_propagates(self):
        try:
            raise MushroomCloudError("test message")
        except MushroomCloudError as e:
            assert str(e) == "test message"

    def test_inherits_from_exception(self):
        assert issubclass(MushroomCloudError, Exception)


class TestLLMErrorHierarchy:
    """LLM-related exceptions should all inherit from LLMError and MushroomCloudError."""

    def test_llm_error_is_mushroom_cloud_error(self):
        assert issubclass(LLMError, MushroomCloudError)

    def test_llm_rate_limit_is_llm_error(self):
        assert issubclass(LLMRateLimitError, LLMError)

    def test_llm_rate_limit_is_mushroom_cloud_error(self):
        assert issubclass(LLMRateLimitError, MushroomCloudError)

    def test_llm_auth_error_is_llm_error(self):
        assert issubclass(LLMAuthError, LLMError)

    def test_llm_provider_error_is_llm_error(self):
        assert issubclass(LLMProviderError, LLMError)

    def test_llm_rate_limit_message(self):
        try:
            raise LLMRateLimitError("Rate limit exceeded for Anthropic")
        except LLMError as e:
            assert "Rate limit" in str(e)

    def test_llm_auth_error_message(self):
        try:
            raise LLMAuthError("Invalid API key")
        except MushroomCloudError as e:
            assert "Invalid API key" in str(e)

    def test_catch_llm_rate_limit_as_llm_error(self):
        """LLMRateLimitError should be catchable as LLMError."""
        with pytest.raises(LLMError):
            raise LLMRateLimitError("too many requests")

    def test_catch_llm_rate_limit_as_base(self):
        """LLMRateLimitError should be catchable as MushroomCloudError."""
        with pytest.raises(MushroomCloudError):
            raise LLMRateLimitError("too many requests")


class TestStorageError:
    """StorageError should inherit from MushroomCloudError."""

    def test_inherits_from_base(self):
        assert issubclass(StorageError, MushroomCloudError)

    def test_message_propagates(self):
        try:
            raise StorageError("disk full")
        except MushroomCloudError as e:
            assert str(e) == "disk full"


class TestCaseNotFoundError:
    """CaseNotFoundError should inherit from MushroomCloudError."""

    def test_inherits_from_base(self):
        assert issubclass(CaseNotFoundError, MushroomCloudError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(MushroomCloudError):
            raise CaseNotFoundError("case_abc not found")


class TestPrepNotFoundError:
    """PrepNotFoundError should inherit from MushroomCloudError."""

    def test_inherits_from_base(self):
        assert issubclass(PrepNotFoundError, MushroomCloudError)

    def test_message(self):
        err = PrepNotFoundError("prep_001 does not exist")
        assert "prep_001" in str(err)


class TestValidationError:
    """ValidationError should inherit from MushroomCloudError."""

    def test_inherits_from_base(self):
        assert issubclass(ValidationError, MushroomCloudError)

    def test_message(self):
        try:
            raise ValidationError("case_type must be one of: criminal, civil")
        except MushroomCloudError as e:
            assert "case_type" in str(e)


class TestAuthorizationError:
    """AuthorizationError should inherit from MushroomCloudError."""

    def test_inherits_from_base(self):
        assert issubclass(AuthorizationError, MushroomCloudError)

    def test_message(self):
        err = AuthorizationError("paralegal cannot delete cases")
        assert "paralegal" in str(err)


class TestAllExceptionsShareBase:
    """Every exception in the hierarchy should be an instance of MushroomCloudError."""

    @pytest.mark.parametrize("exc_class", [
        MushroomCloudError,
        LLMError,
        LLMRateLimitError,
        LLMAuthError,
        LLMProviderError,
        StorageError,
        CaseNotFoundError,
        PrepNotFoundError,
        ValidationError,
        AuthorizationError,
    ])
    def test_subclass_of_base(self, exc_class):
        assert issubclass(exc_class, MushroomCloudError)

    @pytest.mark.parametrize("exc_class", [
        MushroomCloudError,
        LLMError,
        LLMRateLimitError,
        LLMAuthError,
        LLMProviderError,
        StorageError,
        CaseNotFoundError,
        PrepNotFoundError,
        ValidationError,
        AuthorizationError,
    ])
    def test_instance_of_base(self, exc_class):
        instance = exc_class("test")
        assert isinstance(instance, MushroomCloudError)
        assert isinstance(instance, Exception)
