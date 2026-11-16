"""Authentication methods for Daktela API."""

from enum import Enum


class AuthMethod(Enum):
    """Authentication method for API requests.

    Attributes:
        HEADER: Send the access token in the ``X-AUTH-TOKEN`` header (default;
            works on every Daktela version)
        BEARER: Send the access token in the standard ``Authorization: Bearer``
            header, which the Daktela API documentation recommends. Requires
            Daktela 31.37.0, 32.36.0, 33.14.0, or later.
        QUERY: Send the access token as the ``accessToken`` query parameter.
            Tokens in URLs can end up in proxy and server access logs.
        COOKIE: Send the access token in the ``c_user`` cookie. Deprecated:
            Daktela 32 and later accept only web-session tokens in this cookie,
            so a static API token is ignored there.
    """

    HEADER = "header"
    BEARER = "bearer"
    QUERY = "query"
    COOKIE = "cookie"
