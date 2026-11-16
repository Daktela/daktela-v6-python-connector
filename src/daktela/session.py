"""Login-session tokens and their storage."""

import base64
import binascii
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

from .config import _TOKEN_CHARACTERS


class _Secret(str):
    """A string whose ``repr`` is masked, so tracebacks that print frame
    arguments (pytest, debuggers, error trackers) do not show it."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "'***'"


def _jwt_expiry(token: str) -> Optional[int]:
    """Return the ``exp`` claim of a JWT, or ``None`` when it has none."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, ValueError):
        return None
    if not isinstance(claims, dict):
        return None
    expiry = claims.get("exp")
    if isinstance(expiry, bool) or not isinstance(expiry, int):
        return None
    return expiry


@dataclass(frozen=True)
class TokenSet:
    """The access and refresh token of a login session.

    The access token returned by the ``login`` endpoint is a short-lived JWT;
    the refresh token renews it. Expiry times are read from the tokens' ``exp``
    claims and are ``None`` when a token carries none.

    Attributes:
        access_token: Short-lived access token
        refresh_token: Long-lived refresh token; store it as securely as a password
        owner: User and instance the tokens belong to (``username@`` followed
            by the API base URL), so a shared store never resumes the session
            of another user or instance
    """

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    owner: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.access_token or not self.refresh_token:
            raise ValueError("access_token and refresh_token must not be empty")
        if not (
            _TOKEN_CHARACTERS.fullmatch(self.access_token)
            and _TOKEN_CHARACTERS.fullmatch(self.refresh_token)
        ):
            # The tokens are left out of the message.
            raise ValueError(
                "access_token and refresh_token must not contain whitespace, line "
                "breaks, or other control or non-ASCII characters"
            )

    @property
    def access_token_expires_at(self) -> Optional[int]:
        """Unix time when the access token expires, if known."""
        return _jwt_expiry(self.access_token)

    @property
    def refresh_token_expires_at(self) -> Optional[int]:
        """Unix time when the refresh token expires, if known."""
        return _jwt_expiry(self.refresh_token)

    def access_token_expires_within(self, seconds: float, now: float) -> bool:
        """Return whether the access token expires within ``seconds`` of ``now``.

        A token without a known expiry is treated as not expiring.
        """
        expires_at = self.access_token_expires_at
        return expires_at is not None and expires_at - seconds <= now

    def is_refresh_token_expired(self, now: float) -> bool:
        """Return whether the refresh token has expired (``False`` when unknown)."""
        expires_at = self.refresh_token_expires_at
        return expires_at is not None and expires_at <= now

    def to_dict(self) -> Dict[str, str]:
        """Return the tokens as a JSON-serializable mapping for a token store."""
        data = {"accessToken": self.access_token, "refreshToken": self.refresh_token}
        if self.owner is not None:
            data["owner"] = self.owner
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TokenSet":
        """Create tokens from a mapping produced by :meth:`to_dict`."""
        access_token = data.get("accessToken")
        refresh_token = data.get("refreshToken")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise ValueError("saved tokens must contain accessToken and refreshToken strings")
        owner = data.get("owner")
        return cls(access_token, refresh_token, owner if isinstance(owner, str) else None)


@runtime_checkable
class TokenStore(Protocol):
    """Keeps a login session across processes, e.g. in a cache or database.

    ``load()`` returns ``None`` when nothing is stored. Implementations must be
    safe to call from several threads if the client is shared between threads.
    """

    def load(self) -> Optional[TokenSet]:
        """Return the stored tokens, or ``None``."""

    def save(self, tokens: TokenSet) -> None:
        """Store ``tokens``, replacing any stored before."""


class InMemoryTokenStore:
    """A thread-safe :class:`TokenStore` that keeps the tokens in memory.

    Share one instance between clients in the same process to reuse a session.
    """

    def __init__(self, tokens: Optional[TokenSet] = None) -> None:
        self._tokens = tokens
        self._lock = threading.Lock()

    def load(self) -> Optional[TokenSet]:
        with self._lock:
            return self._tokens

    def save(self, tokens: TokenSet) -> None:
        with self._lock:
            self._tokens = tokens

    def __repr__(self) -> str:
        return f"InMemoryTokenStore(stored={self._tokens is not None})"
