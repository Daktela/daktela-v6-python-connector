"""Daktela V6 Python SDK.

A Python SDK for the Daktela V6 REST API.

Example:
    >>> from daktela import DaktelaClient, DaktelaConfig, DaktelaQuery, DaktelaFilter, DaktelaSort
    >>>
    >>> client = DaktelaClient(
    ...     DaktelaConfig(
    ...         url="my.daktela.com",
    ...         access_token="your-token"
    ...     )
    ... )
    >>>
    >>> # Query with filters
    >>> query = (DaktelaQuery()
    ...     .fields("name", "title", "stage")
    ...     .filter(DaktelaFilter.eq("stage", "OPEN"))
    ...     .sort(DaktelaSort.desc("created"))
    ...     .pagination(take=50))
    >>>
    >>> response = client.get("tickets", query)
    >>>
    >>> # Iterate through large datasets
    >>> for ticket in client.iterate("tickets", query):
    ...     print(ticket["name"])
"""

from ._version import __version__
from .auth import AuthMethod
from .client import DaktelaClient
from .config import DaktelaConfig
from .exceptions import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaForbiddenException,
    DaktelaNotFoundException,
    DaktelaProtocolException,
    DaktelaRateLimitException,
    DaktelaRedirectException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)
from .files import DaktelaFile, DaktelaUploadedFile
from .http import RateLimitConfig, RetryConfig
from .iterator import PaginatedIterator
from .query import DaktelaFilter, DaktelaPagination, DaktelaQuery, DaktelaSort
from .response import DaktelaResponse
from .session import InMemoryTokenStore, TokenSet, TokenStore
from .utils import normalize_phone_number

__all__ = [
    # Main client
    "DaktelaClient",
    "DaktelaConfig",
    "DaktelaResponse",
    # Query builders
    "DaktelaQuery",
    "DaktelaFilter",
    "DaktelaSort",
    "DaktelaPagination",
    # Iterator
    "PaginatedIterator",
    # Authentication
    "AuthMethod",
    "TokenSet",
    "TokenStore",
    "InMemoryTokenStore",
    # Files
    "DaktelaFile",
    "DaktelaUploadedFile",
    # Configuration
    "RetryConfig",
    "RateLimitConfig",
    # Exceptions
    "DaktelaException",
    "DaktelaUnauthorizedException",
    "DaktelaForbiddenException",
    "DaktelaNotFoundException",
    "DaktelaRateLimitException",
    "DaktelaProtocolException",
    "DaktelaRedirectException",
    "DaktelaConnectionException",
    "DaktelaTimeoutException",
    "DaktelaValidationException",
    # Utilities
    "normalize_phone_number",
    # Version
    "__version__",
]
