"""Configuration for Daktela client."""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from .auth import AuthMethod


def _normalize_url(url: str) -> tuple[str, str]:
    """Normalize an instance URL to its scheme and network location.

    Hostnames without a scheme default to HTTPS. Existing HTTP/HTTPS schemes
    are preserved, and an optional ``/api/v6`` path is removed.

    Args:
        url: The instance URL to normalize

    Returns:
        A ``(scheme, network_location)`` tuple.
    """
    value = url.strip()
    if not value:
        raise ValueError("url must not be empty")

    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, re.IGNORECASE):
        value = f"https://{value}"

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("url scheme must be http or https")
    if not parsed.netloc or parsed.hostname is None:
        raise ValueError("url must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("url must not include a query string or fragment")

    path = parsed.path.rstrip("/")
    if path and not re.match(r"^/api/v6(?:/|$)", path, re.IGNORECASE):
        raise ValueError("url path must be /api/v6 or omitted")

    return parsed.scheme.lower(), parsed.netloc


@dataclass(frozen=True)
class DaktelaConfig:
    """Immutable configuration for Daktela client.

    Attributes:
        url: Daktela instance hostname (e.g., "my.daktela.com")
        access_token: API access token for authentication
        auth_method: Authentication method to use (default: HEADER)
        timeout: Request timeout in seconds (default: 30.0)
        user_agent: Custom User-Agent header (default: DaktelaPythonSDK/1.1)
        verify_ssl: Whether to verify SSL certificates (default: True)
        logger: Custom logger instance (default: None)
    """

    url: str
    access_token: str
    auth_method: AuthMethod = AuthMethod.HEADER
    timeout: float = 30.0
    user_agent: str = "DaktelaPythonSDK/1.1"
    verify_ssl: bool = True
    logger: Optional[logging.Logger] = field(default=None, compare=False)
    _scheme: str = field(default="https", init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate and normalize configuration after initialization."""
        scheme, url = _normalize_url(self.url)
        if not self.access_token:
            raise ValueError("access_token must not be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if not self.user_agent:
            raise ValueError("user_agent must not be empty")

        object.__setattr__(self, "_scheme", scheme)
        object.__setattr__(self, "url", url)

    @property
    def base_url(self) -> str:
        """Get the full base URL for API requests.

        Returns:
            Base URL with protocol and API path (e.g., "https://my.daktela.com/api/v6")
        """
        return f"{self._scheme}://{self.url}/api/v6"
