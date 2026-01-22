"""Rate limit handling configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for handling rate limits (HTTP 429).

    Attributes:
        enabled: Whether to automatically handle rate limits (default: True)
        max_wait: Maximum time to wait for rate limit reset in seconds (default: 120.0)
        default_retry_after: Default wait time if Retry-After header is missing (default: 60.0)
    """

    enabled: bool = True
    max_wait: float = 120.0
    default_retry_after: float = 60.0

    def get_wait_time(self, retry_after: Optional[int]) -> Optional[float]:
        """Calculate how long to wait before retrying.

        Args:
            retry_after: Value from Retry-After header (in seconds), or None

        Returns:
            Seconds to wait, or None if wait would exceed max_wait
        """
        if not self.enabled:
            return None

        wait_time = float(retry_after) if retry_after else self.default_retry_after

        if wait_time > self.max_wait:
            return None

        return wait_time

    @classmethod
    def disabled(cls) -> "RateLimitConfig":
        """Create a config that disables rate limit handling."""
        return cls(enabled=False)

    @classmethod
    def patient(cls) -> "RateLimitConfig":
        """Create a config willing to wait longer for rate limits."""
        return cls(
            enabled=True,
            max_wait=300.0,
            default_retry_after=60.0,
        )
