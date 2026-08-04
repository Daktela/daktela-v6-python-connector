"""Tests for Daktela exceptions."""

from daktela import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaNotFoundException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
    DaktelaFileResponseException,
)


class TestDaktelaExceptions:
    """Tests for Daktela exception classes."""

    def test_base_exception(self) -> None:
        """Test base DaktelaException."""
        e = DaktelaException("Test error", 500, ["error1"])
        assert e.message == "Test error"
        assert e.status_code == 500
        assert e.errors == ["error1"]
        assert "[500]" in str(e)

    def test_base_exception_without_status(self) -> None:
        """Test base exception without status code."""
        e = DaktelaException("Test error")
        assert e.status_code is None
        assert str(e) == "Test error"

    def test_unauthorized_exception(self) -> None:
        """Test DaktelaUnauthorizedException."""
        e = DaktelaUnauthorizedException()
        assert e.status_code == 401
        assert "Unauthorized" in e.message

    def test_unauthorized_exception_with_message(self) -> None:
        """Test DaktelaUnauthorizedException with custom message."""
        e = DaktelaUnauthorizedException("Invalid token")
        assert e.message == "Invalid token"
        assert e.status_code == 401

    def test_not_found_exception(self) -> None:
        """Test DaktelaNotFoundException."""
        e = DaktelaNotFoundException()
        assert e.status_code == 404
        assert "Not found" in e.message

    def test_rate_limit_exception(self) -> None:
        """Test DaktelaRateLimitException."""
        e = DaktelaRateLimitException(retry_after=60)
        assert e.status_code == 429
        assert e.retry_after == 60

    def test_rate_limit_exception_without_retry_after(self) -> None:
        """Test DaktelaRateLimitException without retry_after."""
        e = DaktelaRateLimitException()
        assert e.status_code == 429
        assert e.retry_after is None

    def test_connection_exception(self) -> None:
        """Test DaktelaConnectionException."""
        e = DaktelaConnectionException("Network error")
        assert e.message == "Network error"
        assert e.status_code is None

    def test_timeout_exception(self) -> None:
        """Test DaktelaTimeoutException."""
        e = DaktelaTimeoutException()
        assert "timed out" in e.message.lower()
        assert e.status_code is None

    def test_validation_exception(self) -> None:
        """Test DaktelaValidationException."""
        e = DaktelaValidationException("Invalid input", 422, ["field error"])
        assert e.message == "Invalid input"
        assert e.status_code == 422
        assert e.errors == ["field error"]

    def test_file_response_exception(self) -> None:
        """Test DaktelaFileResponseException."""
        e = DaktelaFileResponseException('MY_FUNCTION', ['error 01', 'error 02'])
        assert e.message == 'Function or property is not available in DaktelaFileResponse: "MY_FUNCTION".'
        assert e.status_code is None
        assert e.errors == ['error 01', 'error 02']

    def test_exception_inheritance(self) -> None:
        """Test that all exceptions inherit from DaktelaException."""
        assert issubclass(DaktelaUnauthorizedException, DaktelaException)
        assert issubclass(DaktelaNotFoundException, DaktelaException)
        assert issubclass(DaktelaRateLimitException, DaktelaException)
        assert issubclass(DaktelaConnectionException, DaktelaException)
        assert issubclass(DaktelaTimeoutException, DaktelaException)
        assert issubclass(DaktelaValidationException, DaktelaException)
        assert issubclass(DaktelaFileResponseException, DaktelaException)
