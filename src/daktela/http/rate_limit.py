"""Rate limit handling configuration."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for handling rate limits (HTTP 429).

    Attributes:
        enabled: Whether to automatically handle rate limits (default: True)
        max_retries: Maximum number of automatic rate-limit retries (default: 3)
        max_wait: Maximum time to wait for rate limit reset in seconds (default: 120.0)
        default_retry_after: Default wait time if Retry-After header is missing (default: 60.0)
    """

    enabled: bool = True
    max_retries: int = 3
    max_wait: float = 120.0
    default_retry_after: float = 60.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.max_wait < 0:
            raise ValueError("max_wait must not be negative")
        if self.default_retry_after < 0:
            raise ValueError("default_retry_after must not be negative")

    def parse_retry_after(
        self,
        value: Optional[str],
        *,
        now: Optional[datetime] = None,
    ) -> Optional[float]:
        """Parse Retry-After seconds or an HTTP date.

        Invalid or missing values return ``None`` so the configured default can
        be applied by :meth:`get_wait_time`.
        """
        if value is None or not value.strip():
            return None

        try:
            return max(0.0, float(value))
        except ValueError:
            pass

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current_time = now or datetime.now(timezone.utc)
        return max(0.0, (retry_at - current_time).total_seconds())

    def get_wait_time(self, retry_after: Optional[float]) -> Optional[float]:
        """Calculate how long to wait before retrying.

        Args:
            retry_after: Value from Retry-After header (in seconds), or None

        Returns:
            Seconds to wait, or None if wait would exceed max_wait
        """
        if not self.enabled:
            return None

        wait_time = float(retry_after) if retry_after is not None else self.default_retry_after

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
            max_retries=5,
            max_wait=300.0,
            default_retry_after=60.0,
        )
