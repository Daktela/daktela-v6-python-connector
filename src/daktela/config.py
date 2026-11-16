"""Configuration for Daktela client."""

import logging
import re
import warnings
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urlsplit

from ._version import __version__
from .auth import AuthMethod

_API_PATH = re.compile(r"^(?P<prefix>.*?)/api/v6(?:/.*)?$", re.IGNORECASE)
# Daktela tokens are hex strings or JWTs. Anything outside visible ASCII, such as
# the line break of a token read from a file, cannot be sent in a header.
_TOKEN_CHARACTERS = re.compile(r"[\x21-\x7e]+")


def _normalize_url(url: str) -> tuple[str, str]:
    """Normalize an instance URL to its scheme and location.

    Hostnames without a scheme default to HTTPS. Existing HTTP/HTTPS schemes
    are preserved. A path prefix, such as ``/daktela`` for an instance behind a
    reverse proxy, is kept, and a trailing ``/api/v6`` path is removed.

    Args:
        url: The instance URL to normalize

    Returns:
        A ``(scheme, location)`` tuple, where the location is the network
        location followed by the path prefix, if any.
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

    prefix = parsed.path.rstrip("/")
    match = _API_PATH.match(prefix)
    if match:
        prefix = match.group("prefix").rstrip("/")
    if prefix:
        segments = prefix.split("/")[1:]
        if any(not segment or unquote(segment) in {".", ".."} for segment in segments):
            raise ValueError("url path must not contain empty or relative segments")
        if "\\" in prefix:
            raise ValueError("url path must not contain backslashes")

    return parsed.scheme.lower(), f"{parsed.netloc}{prefix}"


def _validate_token(token: str) -> None:
    if not token:
        raise ValueError("access_token must not be empty")
    if not _TOKEN_CHARACTERS.fullmatch(token):
        # The token itself is left out of the message.
        raise ValueError(
            "access_token must not contain whitespace, line breaks, or other "
            "control or non-ASCII characters; strip the value read from a file "
            "or environment variable"
        )


@dataclass(frozen=True)
class DaktelaConfig:
    """Immutable configuration for Daktela client.

    Attributes:
        url: Daktela instance URL or hostname (e.g., "my.daktela.com" or
            "https://example.com/daktela"). After normalization it holds the
            network location and the path prefix, if any.
        access_token: Static API access token. Leave it out only when the client
            logs in with :meth:`daktela.DaktelaClient.login`.
        auth_method: Authentication method to use (default: HEADER)
        timeout: Request timeout in seconds (default: 30.0)
        user_agent: Custom User-Agent header (default: DaktelaPythonSDK/<version>)
        verify_ssl: Whether to verify SSL certificates (default: True)
        logger: Custom logger instance (default: None)
    """

    url: str
    access_token: Optional[str] = field(default=None, repr=False)
    auth_method: AuthMethod = AuthMethod.HEADER
    timeout: float = 30.0
    user_agent: str = f"DaktelaPythonSDK/{__version__}"
    verify_ssl: bool = True
    logger: Optional[logging.Logger] = field(default=None, compare=False)
    _scheme: str = field(default="https", init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate and normalize configuration after initialization."""
        scheme, url = _normalize_url(self.url)
        if self.access_token is not None:
            _validate_token(self.access_token)
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if not self.user_agent:
            raise ValueError("user_agent must not be empty")
        if self.auth_method == AuthMethod.COOKIE:
            warnings.warn(
                "AuthMethod.COOKIE is deprecated: Daktela 32 and later accept only "
                "web-session tokens in the c_user cookie. Use AuthMethod.BEARER or "
                "AuthMethod.HEADER.",
                DeprecationWarning,
                stacklevel=3,
            )

        object.__setattr__(self, "_scheme", scheme)
        object.__setattr__(self, "url", url)

    @property
    def instance_url(self) -> str:
        """Get the instance root URL, used for file endpoints.

        Returns:
            Instance URL with protocol and path prefix (e.g., "https://my.daktela.com")
        """
        return f"{self._scheme}://{self.url}"

    @property
    def base_url(self) -> str:
        """Get the full base URL for API requests.

        Returns:
            Base URL with protocol and API path (e.g., "https://my.daktela.com/api/v6")
        """
        return f"{self.instance_url}/api/v6"
