"""Exception hierarchy for Daktela SDK."""

from typing import Any, List, Optional


class DaktelaException(Exception):
    """Base exception for all Daktela SDK errors.

    Attributes:
        message: Human-readable error description
        status_code: HTTP status code if applicable
        errors: List of error details from the API response
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class DaktelaUnauthorizedException(DaktelaException):
    """Raised when authentication fails (HTTP 401)."""

    def __init__(
        self,
        message: str = "Unauthorized",
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=401, errors=errors)


class DaktelaNotFoundException(DaktelaException):
    """Raised when a resource is not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Not found",
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=404, errors=errors)


class DaktelaRateLimitException(DaktelaException):
    """Raised when rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by server
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=429, errors=errors)
        self.retry_after = retry_after


class DaktelaConnectionException(DaktelaException):
    """Raised when a network connection error occurs."""

    def __init__(
        self,
        message: str = "Connection error",
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=None, errors=errors)


class DaktelaTimeoutException(DaktelaException):
    """Raised when a request times out."""

    def __init__(
        self,
        message: str = "Request timed out",
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=None, errors=errors)


class DaktelaValidationException(DaktelaException):
    """Raised when request validation fails (HTTP 400/422)."""

    def __init__(
        self,
        message: str = "Validation error",
        status_code: int = 400,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, errors=errors)


class DaktelaProtocolException(DaktelaException):
    """Raised when an API response does not match the expected JSON protocol."""
