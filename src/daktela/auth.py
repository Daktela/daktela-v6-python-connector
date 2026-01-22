"""Authentication methods for Daktela API."""

from enum import Enum


class AuthMethod(Enum):
    """Authentication method for API requests.

    Attributes:
        HEADER: Send access token in X-AUTH-TOKEN header (recommended)
        QUERY: Send access token as query parameter
        COOKIE: Send access token as cookie
    """

    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"
