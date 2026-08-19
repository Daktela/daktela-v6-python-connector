"""Retry configuration for HTTP requests."""

from dataclasses import dataclass
from random import uniform
from typing import Tuple


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for automatic request retries.

    Implements exponential backoff with optional jitter.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay in seconds between retries (default: 60.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        retry_on_status: HTTP status codes that trigger a retry
        retry_on_connection_error: Whether to retry connection failures
        retry_on_timeout: Whether to retry request timeouts
        jitter: Maximum random jitter added to each delay in seconds
    """

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on_status: Tuple[int, ...] = (408, 500, 502, 503, 504)
    retry_on_connection_error: bool = True
    retry_on_timeout: bool = True
    jitter: float = 0.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must not be negative")
        if self.max_delay < 0:
            raise ValueError("max_delay must not be negative")
        if self.exponential_base < 1:
            raise ValueError("exponential_base must be at least one")
        if self.jitter < 0:
            raise ValueError("jitter must not be negative")

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.

        Uses exponential backoff: delay = initial_delay * (base ^ attempt)

        Args:
            attempt: The retry attempt number (0-indexed)

        Returns:
            Delay in seconds, capped at max_delay
        """
        if attempt < 0:
            raise ValueError("attempt must not be negative")
        delay = self.initial_delay * (self.exponential_base**attempt)
        if self.jitter:
            delay += uniform(0.0, self.jitter)
        return min(delay, self.max_delay)

    def should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if a request should be retried.

        Args:
            status_code: HTTP status code from the response
            attempt: Current retry attempt number (0-indexed)

        Returns:
            True if the request should be retried
        """
        return status_code in self.retry_on_status and attempt < self.max_retries

    @classmethod
    def disabled(cls) -> "RetryConfig":
        """Create a config that disables retries."""
        return cls(max_retries=0)

    @classmethod
    def aggressive(cls) -> "RetryConfig":
        """Create a config with more aggressive retry settings."""
        return cls(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=2.0,
        )
