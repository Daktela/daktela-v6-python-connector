"""Exception hierarchy for Daktela SDK."""

from typing import Any, Iterator, List, Mapping, Optional

# Keys that wrap a message rather than name the field it belongs to.
_WRAPPER_KEYS = frozenset({"error", "errors", "message", "messages"})


def _error_messages(error: Any, prefix: str = "") -> Iterator[str]:
    """Yield readable messages from nested API error lists and maps."""
    if error is None:
        return
    if isinstance(error, Mapping):
        for key, value in error.items():
            name = str(key)
            nested = prefix if name.lower() in _WRAPPER_KEYS or name.isdigit() else (
                f"{prefix}{name}: "
            )
            yield from _error_messages(value, nested)
    elif isinstance(error, (list, tuple)):
        for item in error:
            yield from _error_messages(item, prefix)
    else:
        text = str(error).strip()
        if text:
            yield f"{prefix}{text}"


def _format_errors(errors: List[Any]) -> str:
    """Render API error details as an exception message.

    Nested lists and maps are flattened, so ``[{"error": "Bad request"}]``
    becomes ``"Bad request"`` and ``{"title": ["required"]}`` becomes
    ``"title: required"``.
    """
    messages = list(_error_messages(errors))
    return "; ".join(messages) if messages else "Unknown API error"


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


class DaktelaForbiddenException(DaktelaException):
    """Raised when the token lacks permission for a resource (HTTP 403)."""

    def __init__(
        self,
        message: str = "Forbidden",
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=403, errors=errors)


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
    """Raised when request validation fails.

    Raised for HTTP 400/422 responses, and for successful write responses whose
    body still reports errors.
    """

    def __init__(
        self,
        message: str = "Validation error",
        status_code: int = 400,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, errors=errors)


class DaktelaProtocolException(DaktelaException):
    """Raised when an API response does not match the expected JSON protocol."""


class DaktelaRedirectException(DaktelaException):
    """Raised when the server answers with an HTTP redirect (3xx).

    The SDK never follows redirects: a redirect would send the access token or
    login credentials to its target, and could resend a create request. A
    redirect usually means the configured instance URL is not the one the API
    answers on, for example ``http://`` instead of ``https://``.

    Attributes:
        location: Value of the ``Location`` header, if the server sent one
    """

    def __init__(
        self,
        message: str = "Redirected",
        status_code: int = 302,
        location: Optional[str] = None,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, errors=errors)
        self.location = location
