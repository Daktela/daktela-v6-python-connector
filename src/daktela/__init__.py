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

from .auth import AuthMethod
from .client import DaktelaClient
from .config import DaktelaConfig
from .exceptions import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaFileResponseException,
    DaktelaNotFoundException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)
from .http import RateLimitConfig, RetryConfig
from .iterator import PaginatedIterator
from .query import DaktelaFilter, DaktelaPagination, DaktelaQuery, DaktelaSort
from .response import DaktelaFileResponse, DaktelaResponse

__version__ = "1.0.0"

__all__ = [
    # Main client
    "DaktelaClient",
    "DaktelaConfig",
    "DaktelaResponse",
    "DaktelaFileResponse",
    # Query builders
    "DaktelaQuery",
    "DaktelaFilter",
    "DaktelaSort",
    "DaktelaPagination",
    # Iterator
    "PaginatedIterator",
    # Authentication
    "AuthMethod",
    # Configuration
    "RetryConfig",
    "RateLimitConfig",
    # Exceptions
    "DaktelaException",
    "DaktelaUnauthorizedException",
    "DaktelaNotFoundException",
    "DaktelaRateLimitException",
    "DaktelaConnectionException",
    "DaktelaTimeoutException",
    "DaktelaValidationException",
    "DaktelaFileResponseException",
    # Version
    "__version__",
]
