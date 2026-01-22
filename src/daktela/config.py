"""Configuration for Daktela client."""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .auth import AuthMethod


def _normalize_url(url: str) -> str:
    """Normalize instance URL to hostname only.

    Removes protocol prefix, trailing slashes, and API paths.

    Args:
        url: The instance URL to normalize

    Returns:
        Normalized hostname (e.g., "my.daktela.com")
    """
    url = re.sub(r"^https?://", "", url)
    url = url.rstrip("/")
    url = re.sub(r"/api/v\d+/?.*$", "", url)
    return url


@dataclass(frozen=True)
class DaktelaConfig:
    """Immutable configuration for Daktela client.

    Attributes:
        url: Daktela instance hostname (e.g., "my.daktela.com")
        access_token: API access token for authentication
        auth_method: Authentication method to use (default: HEADER)
        timeout: Request timeout in seconds (default: 30.0)
        user_agent: Custom User-Agent header (default: DaktelaPythonSDK/1.0)
        verify_ssl: Whether to verify SSL certificates (default: True)
        logger: Custom logger instance (default: None)
    """

    url: str
    access_token: str
    auth_method: AuthMethod = AuthMethod.HEADER
    timeout: float = 30.0
    user_agent: str = "DaktelaPythonSDK/1.0"
    verify_ssl: bool = True
    logger: Optional[logging.Logger] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Normalize the URL after initialization."""
        object.__setattr__(self, "url", _normalize_url(self.url))

    @property
    def base_url(self) -> str:
        """Get the full base URL for API requests.

        Returns:
            Base URL with protocol and API path (e.g., "https://my.daktela.com/api/v6")
        """
        return f"https://{self.url}/api/v6"
