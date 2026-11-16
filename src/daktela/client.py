"""Main client for Daktela V6 REST API."""

import json
import mimetypes
import re
from typing import IO, Any, Dict, List, Mapping, Optional, Union
from urllib.parse import quote

import httpx

from .config import DaktelaConfig
from .exceptions import DaktelaProtocolException, DaktelaValidationException
from .files import DaktelaFile, DaktelaUploadedFile, _filename_from_disposition
from .http import ApiCommunicator, RateLimitConfig, RetryConfig
from .iterator import PaginatedIterator
from .query import DaktelaQuery
from .response import DaktelaResponse
from .session import TokenStore, _Secret

# The upload endpoint names a stored file with a SHA-1 hash and the original extension.
_UPLOADED_FILE_NAME = re.compile(r"^[0-9a-f]{40}\.[^/\\]*$")


def _path_segment(value: str, what: str) -> str:
    """Encode ``value`` as a single URL path segment.

    Values that could address a different endpoint are rejected: empty values,
    dot segments, and values containing ``/``, ``\\``, or NUL.
    """
    if not value:
        raise ValueError(f"{what} must not be empty")
    if value in {".", ".."} or any(char in value for char in "/\\\x00"):
        raise ValueError(f"{what} must not contain '/', '\\', NUL, or be a dot segment")
    return quote(value, safe="")


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
            config: Client configuration with a static access token
            retry_config: Retry settings (default: RetryConfig())
            rate_limit_config: Rate limit settings (default: RateLimitConfig())
            http_client: Custom httpx client (default: creates new client)

        Raises:
            ValueError: When ``config`` has no access token; use :meth:`login`
                to authenticate with a username and password instead
        """
        if config.access_token is None:
            raise ValueError(
                "access_token is required; use DaktelaClient.login() to log in "
                "with a username and password"
            )
        self._setup(config, retry_config, rate_limit_config, http_client)

    def _setup(
        self,
        config: DaktelaConfig,
        retry_config: Optional[RetryConfig],
        rate_limit_config: Optional[RateLimitConfig],
        http_client: Optional[httpx.Client],
    ) -> None:
        self._config = config
        self._communicator = ApiCommunicator(
            config=config,
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
            http_client=http_client,
        )

    @classmethod
    def login(
        cls,
        config: DaktelaConfig,
        username: str,
        password: str,
        *,
        token_store: Optional[TokenStore] = None,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> "DaktelaClient":
        """Create a client that logs in with a username and password.

        The client refreshes the short-lived access token before it expires
        and after the server rejects it, and logs in again when the session has
        ended. After the server rejects the credentials, no further login is
        sent (repeated attempts could lock the account). Accounts with
        two-factor authentication cannot log in this way; use a static token.

        Args:
            config: Client configuration without ``access_token``
            username: Daktela user name
            password: Password; kept in memory to log in again, never stored
            token_store: Keeps the session across processes; a stored session
                of the same user and instance is resumed instead of logging in
            retry_config: Retry settings (default: RetryConfig())
            rate_limit_config: Rate limit settings (default: RateLimitConfig())
            http_client: Custom httpx client (default: creates new client)

        Raises:
            ValueError: When ``username`` or ``password`` is empty, or
                ``config`` has an ``access_token``
            DaktelaException: When the login fails

        Warns:
            UserWarning: When the password would be sent over plain HTTP to
                another host than the local machine, or without certificate
                verification
        """
        # Masks the password in the arguments tracebacks print for this frame.
        password = _Secret(password)
        client = cls.__new__(cls)
        client._setup(config, retry_config, rate_limit_config, http_client)
        try:
            client._communicator.login(username, password, token_store)
        except BaseException:
            client.close()
            raise
        return client

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
        query_params: Optional[Mapping[str, Any]] = None,
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
        params = self._merge_query_params(query, query_params)
        return self._communicator.send_request("GET", endpoint, params)

    def post(
        self,
        endpoint: str,
        data: Dict[str, Any],
        query_params: Optional[Mapping[str, Any]] = None,
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
        return self._communicator.send_request("POST", endpoint, query_params, data)

    def put(
        self,
        endpoint: str,
        data: Dict[str, Any],
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Perform a PUT request (update) on a raw endpoint path.

        Prefer :meth:`put_one`, which encodes the object name safely.

        Args:
            endpoint: API endpoint (e.g., "tickets/123")
            data: Request body

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        return self._communicator.send_request("PUT", endpoint, query_params, data)

    def delete(
        self,
        endpoint: str,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Perform a DELETE request on a raw endpoint path.

        Prefer :meth:`delete_one`, which encodes the object name safely.

        Args:
            endpoint: API endpoint (e.g., "tickets/123")

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        return self._communicator.send_request("DELETE", endpoint, query_params)

    @staticmethod
    def _object_path(endpoint: str, object_name: str) -> str:
        # The explicit suffix keeps names that end in ".json" intact, because
        # endpoint normalization strips exactly one trailing ".json".
        return f"{endpoint.strip('/')}/{_path_segment(object_name, 'object_name')}.json"

    def get_one(
        self,
        endpoint: str,
        object_name: str,
        query: Optional[DaktelaQuery] = None,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Read one object, safely encoding its name."""
        return self.get(self._object_path(endpoint, object_name), query, query_params)

    def put_one(
        self,
        endpoint: str,
        object_name: str,
        data: Dict[str, Any],
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Update one object, safely encoding its name."""
        return self.put(self._object_path(endpoint, object_name), data, query_params)

    def delete_one(
        self,
        endpoint: str,
        object_name: str,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Delete one object, safely encoding its name."""
        return self.delete(self._object_path(endpoint, object_name), query_params)

    def get_relation(
        self,
        endpoint: str,
        object_name: str,
        relation: str,
        query: Optional[DaktelaQuery] = None,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Read a named relation for one object."""
        relation = relation.strip()
        if relation:
            relation = relation[0].lower() + relation[1:]
        path = (
            f"{endpoint.strip('/')}/{_path_segment(object_name, 'object_name')}/"
            f"{_path_segment(relation, 'relation')}"
        )
        return self.get(path, query, query_params)

    def iterate(
        self,
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
        page_size: int = 100,
        max_items: Optional[int] = None,
        stop_on_error: bool = True,
        max_error_pages: int = 3,
    ) -> PaginatedIterator:
        """Create a memory-efficient iterator for paginating through large datasets.

        Args:
            endpoint: API endpoint to iterate
            query: Base query (will be cloned and modified for pagination)
            page_size: Number of items per page (default: 100). Most resources
                return at most 1000 items per request.
            max_items: Maximum items to return (None for unlimited)
            stop_on_error: Whether to raise on the first failed page instead of
                skipping it
            max_error_pages: Consecutive failed pages tolerated when skipping

        Returns:
            PaginatedIterator that yields individual items

        Note:
            Pagination is offset-based. Add a sort on a stable field (for
            example ``DaktelaSort.asc("name")``) so records created or edited
            during iteration are not skipped or returned twice. If the server
            caps the page size and reports no total, iteration ends after the
            first short page, so keep ``page_size`` within the server limit.

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
            max_error_pages=max_error_pages,
        )

    def get_all(
        self,
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
        page_size: int = 100,
        max_items: Optional[int] = None,
        stop_on_error: bool = True,
        max_error_pages: int = 3,
    ) -> List[Dict[str, Any]]:
        """Read and collect all matching objects.

        Prefer :meth:`iterate` for large datasets to avoid loading all records
        into memory.
        """
        return self.iterate(
            endpoint,
            query,
            page_size,
            max_items,
            stop_on_error,
            max_error_pages,
        ).collect()

    @staticmethod
    def _merge_query_params(
        query: Optional[DaktelaQuery],
        query_params: Optional[Mapping[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        params = dict(query_params or {})
        if query is not None:
            params.update(query.to_params())
        return params or None

    # ------------------------------------------------------------------
    # Files

    def download_recording(
        self,
        activity_name: str,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaFile:
        """Download the call recording of an activity.

        Args:
            activity_name: Name of the call activity (e.g. "activity_123456789")
            query_params: Additional parameters of the recording endpoint

        Returns:
            The recording, with its file name and media type
        """
        params: Dict[str, Any] = {"download": "true", **(query_params or {})}
        path = f"file/recording/{_path_segment(activity_name, 'activity_name')}"
        return self._download(path, params)

    def download_file(
        self,
        mapper: str,
        name: str,
        *,
        icon_hash: Optional[str] = None,
        fullsize: bool = True,
        query_params: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaFile:
        """Download an attachment or another stored file.

        Args:
            mapper: Model the file belongs to (e.g. "activitiesEmail")
            name: Name (id) of the file, or of the object it belongs to for
                some models
            icon_hash: File title, used by the server only to prevent caching
                an obsolete file
            fullsize: Return images in their original size instead of resized
                to at most 1024 x 768 px (default: True)
            query_params: Additional parameters, such as ``thumbnail`` or
                ``directsize``

        Returns:
            The file, with its file name and media type

        Raises:
            DaktelaNotFoundException: When the file does not exist. The server
                also answers HTTP 404 when it does not accept the access token.
        """
        if not mapper:
            raise ValueError("mapper must not be empty")
        if not name:
            raise ValueError("name must not be empty")
        params: Dict[str, Any] = {"mapper": mapper, "name": name, "download": 1}
        if icon_hash:
            params["iconHash"] = icon_hash
        if fullsize:
            params["fullsize"] = 1
        params.update(query_params or {})
        return self._download("file/download.php", params)

    def _download(self, path: str, params: Mapping[str, Any]) -> DaktelaFile:
        response = self._communicator.send_file_request("GET", path, params)
        return DaktelaFile(
            content=response.content,
            filename=_filename_from_disposition(response.headers.get("Content-Disposition")),
            content_type=response.headers.get("Content-Type"),
            status_code=response.status_code,
        )

    def upload_file(
        self,
        content: Union[bytes, IO[bytes]],
        filename: str,
        *,
        content_type: Optional[str] = None,
    ) -> DaktelaUploadedFile:
        """Upload a file to the instance's temporary storage.

        Reference the result once in the entity that uses it, for example as an
        item of an email activity's ``add_files``: ``uploaded.as_dict()``. Like
        other create requests, uploads are resent only when the connection could
        not be established, on HTTP 429, and, with a login session, once after
        an HTTP 401, which the server returns before it stores anything.

        Args:
            content: File content, or a binary file object to read it from
            filename: Original file name, with its extension
            content_type: Media type (default: guessed from ``filename``)

        Returns:
            The server's name for the file and its original name

        Raises:
            DaktelaValidationException: When the server rejects the file, for
                example because its type is blocked or it is too large
        """
        if not filename:
            raise ValueError("filename must not be empty")
        data = content if isinstance(content, bytes) else content.read()
        media_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        response = self._communicator.send_file_request(
            "POST",
            "file/upload.php",
            {"type": "save"},
            {"files": (filename, data, media_type)},
        )
        try:
            result = response.json()
        except ValueError as exc:
            raise DaktelaProtocolException(
                "The upload response is not valid JSON", status_code=response.status_code
            ) from exc
        if isinstance(result, str) and _UPLOADED_FILE_NAME.match(result):
            return DaktelaUploadedFile(name=result, title=filename)
        # The endpoint may report an error with HTTP 200.
        error = self._communicator._redact_value(result)
        message = error if isinstance(error, str) and error else json.dumps(error)
        raise DaktelaValidationException(message, response.status_code, [error])

    # ------------------------------------------------------------------
    # Health

    def ping(self) -> bool:
        """Check that the API accepts the access token.

        Returns:
            True if the API identifies the user of the access token
        """
        return self._communicator.ping()

    def health_check(self) -> Dict[str, Any]:
        """Perform a detailed health check.

        Returns:
            Dict with ``healthy``, ``latency_ms``, ``status_code`` (when a
            response was received), and ``error`` (when unhealthy)
        """
        return self._communicator.health_check()
