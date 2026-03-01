"""Project Mushroom Cloud exception hierarchy."""


class MushroomCloudError(Exception):
    """Base exception for all project errors."""


class LLMError(MushroomCloudError):
    """Base for LLM-related errors."""


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""


class LLMAuthError(LLMError):
    """LLM API key invalid or expired."""


class LLMProviderError(LLMError):
    """LLM provider unavailable or returned an error."""


class StorageError(MushroomCloudError):
    """File system or database storage error."""


class CaseNotFoundError(MushroomCloudError):
    """Referenced case does not exist."""


class PrepNotFoundError(MushroomCloudError):
    """Referenced preparation does not exist."""


class ValidationError(MushroomCloudError):
    """Input validation failure."""


class AuthorizationError(MushroomCloudError):
    """User lacks permission for this operation."""
