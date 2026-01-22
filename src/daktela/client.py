"""Main client for Daktela V6 REST API."""

from typing import Any, Dict, Optional

import httpx

from .config import DaktelaConfig
from .http import ApiCommunicator, RateLimitConfig, RetryConfig
from .iterator import PaginatedIterator
from .query import DaktelaQuery
from .response import DaktelaResponse


class DaktelaClient:
    """Main client for Daktela V6 REST API.

    Provides a high-level interface for all API operations.

    Example:
        >>> from daktela import DaktelaClient, DaktelaConfig, DaktelaQuery, DaktelaFilter
        >>>
        >>> client = DaktelaClient(
        ...     DaktelaConfig(
        ...         url="my.daktela.com",
        ...         access_token="your-token"
        ...     )
        ... )
        >>>
        >>> # Simple GET request
        >>> response = client.get("tickets")
        >>>
        >>> # GET with query
        >>> query = DaktelaQuery().filter(DaktelaFilter.eq("stage", "OPEN")).take(50)
        >>> response = client.get("tickets", query)
        >>>
        >>> # Iterate through large datasets
        >>> for ticket in client.iterate("tickets", query):
        ...     print(ticket["name"])
    """

    def __init__(
        self,
        config: DaktelaConfig,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize the Daktela client.

        Args:
            config: Client configuration
            retry_config: Retry settings (default: RetryConfig())
            rate_limit_config: Rate limit settings (default: RateLimitConfig())
            http_client: Custom httpx client (default: creates new client)
        """
        self._config = config
        self._communicator = ApiCommunicator(
            config=config,
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
            http_client=http_client,
        )

    @property
    def config(self) -> DaktelaConfig:
        """Get the client configuration."""
        return self._config

    def close(self) -> None:
        """Close the client and release resources."""
        self._communicator.close()

    def __enter__(self) -> "DaktelaClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get(
        self,
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
    ) -> DaktelaResponse:
        """Perform a GET request.

        Args:
            endpoint: API endpoint (e.g., "tickets" or "tickets/123")
            query: Optional query parameters

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        params = query.to_params() if query else None
        return self._communicator.send_request("GET", endpoint, params)

    def post(
        self,
        endpoint: str,
        data: Dict[str, Any],
    ) -> DaktelaResponse:
        """Perform a POST request (create).

        Args:
            endpoint: API endpoint (e.g., "tickets")
            data: Request body

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        return self._communicator.send_request("POST", endpoint, body=data)

    def put(
        self,
        endpoint: str,
        data: Dict[str, Any],
    ) -> DaktelaResponse:
        """Perform a PUT request (update).

        Args:
            endpoint: API endpoint (e.g., "tickets/123")
            data: Request body

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        return self._communicator.send_request("PUT", endpoint, body=data)

    def delete(
        self,
        endpoint: str,
    ) -> DaktelaResponse:
        """Perform a DELETE request.

        Args:
            endpoint: API endpoint (e.g., "tickets/123")

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        return self._communicator.send_request("DELETE", endpoint)

    def iterate(
        self,
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
        page_size: int = 100,
        max_items: Optional[int] = None,
        stop_on_error: bool = True,
    ) -> PaginatedIterator:
        """Create a memory-efficient iterator for paginating through large datasets.

        Args:
            endpoint: API endpoint to iterate
            query: Base query (will be cloned and modified for pagination)
            page_size: Number of items per page (default: 100)
            max_items: Maximum items to return (None for unlimited)
            stop_on_error: Whether to stop iteration on first error

        Returns:
            PaginatedIterator that yields individual items

        Example:
            >>> for ticket in client.iterate("tickets", query):
            ...     print(ticket["name"])
        """
        return PaginatedIterator(
            client=self,
            endpoint=endpoint,
            query=query,
            page_size=page_size,
            max_items=max_items,
            stop_on_error=stop_on_error,
        )

    def ping(self) -> bool:
        """Check API connectivity.

        Returns:
            True if API is reachable and responding
        """
        return self._communicator.ping()

    def health_check(self) -> Dict[str, Any]:
        """Perform a detailed health check.

        Returns:
            Dict with health status, latency in ms, and any errors
        """
        return self._communicator.health_check()
