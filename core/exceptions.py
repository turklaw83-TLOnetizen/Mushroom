"""Project Mushroom Cloud — domain exceptions.

All custom exceptions inherit from AppError so callers can catch broadly
when appropriate, while still being able to catch specific errors.
"""


class AppError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str = "", *, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CaseNotFoundError(AppError):
    def __init__(self, case_id: str):
        super().__init__(f"Case not found: {case_id}", status_code=404)
        self.case_id = case_id


class PrepNotFoundError(AppError):
    def __init__(self, case_id: str, prep_id: str):
        super().__init__(f"Preparation not found: {prep_id} in case {case_id}", status_code=404)
        self.case_id = case_id
        self.prep_id = prep_id


class AnalysisInProgressError(AppError):
    def __init__(self, case_id: str):
        super().__init__(f"Analysis already running for case: {case_id}", status_code=409)
        self.case_id = case_id


class StorageError(AppError):
    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message, status_code=500)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


class ExternalServiceError(AppError):
    """Raised when an external API (LLM, Clerk, Stripe, etc.) fails."""
    def __init__(self, service: str, message: str = ""):
        super().__init__(f"{service} error: {message}" if message else f"{service} error", status_code=502)
        self.service = service
