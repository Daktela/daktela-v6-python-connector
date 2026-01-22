"""Retry configuration for HTTP requests."""

from dataclasses import dataclass
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
        retry_on_status: HTTP status codes that trigger a retry (default: 429, 500, 502, 503, 504)
    """

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on_status: Tuple[int, ...] = (429, 500, 502, 503, 504)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.

        Uses exponential backoff: delay = initial_delay * (base ^ attempt)

        Args:
            attempt: The retry attempt number (0-indexed)

        Returns:
            Delay in seconds, capped at max_delay
        """
        delay = self.initial_delay * (self.exponential_base**attempt)
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
