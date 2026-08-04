"""HTTP transport layer for Daktela API communication."""

import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from ..auth import AuthMethod
from ..config import DaktelaConfig
from ..exceptions import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaNotFoundException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)
from ..response import DaktelaResponse, DaktelaFileResponse
from .rate_limit import RateLimitConfig
from .retry import RetryConfig


class ApiCommunicator:
    """Low-level HTTP transport for Daktela API requests.

    Handles authentication, request building, retries, and rate limiting.
    """

    def __init__(
        self,
        config: DaktelaConfig,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize the API communicator.

        Args:
            config: Client configuration
            retry_config: Retry settings (default: RetryConfig())
            rate_limit_config: Rate limit settings (default: RateLimitConfig())
            http_client: Custom httpx client (default: creates new client)
        """
        self._config = config
        self._retry_config = retry_config or RetryConfig()
        self._rate_limit_config = rate_limit_config or RateLimitConfig()
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=config.timeout,
            verify=config.verify_ssl,
        )
        self._logger = config.logger

    def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ApiCommunicator":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def send_request(
        self,
        method: str,
        endpoint: str,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> DaktelaResponse:
        """Send an HTTP request to the Daktela API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            query_params: Query parameters
            body: Request body for POST/PUT requests

        Returns:
            DaktelaResponse wrapper

        Raises:
            DaktelaException: On API or network errors
        """
        url = self._build_url(endpoint, query_params)
        headers = self._build_headers()
        cookies = self._build_cookies()

        attempt = 0

        while True:
            try:
                response = self._execute_request(method, url, headers, cookies, body)
                return self._handle_response(response)

            except DaktelaRateLimitException as e:
                wait_time = self._rate_limit_config.get_wait_time(e.retry_after)
                if wait_time is not None:
                    self._log(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                raise

            except DaktelaException as e:
                if e.status_code and self._retry_config.should_retry(e.status_code, attempt):
                    delay = self._retry_config.get_delay(attempt)
                    self._log(f"Request failed with {e.status_code}. Retrying in {delay}s...")
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt < self._retry_config.max_retries:
                    delay = self._retry_config.get_delay(attempt)
                    self._log(f"Connection error. Retrying in {delay}s...")
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise DaktelaConnectionException(f"Connection failed: {e}")

            except httpx.TimeoutException as e:
                raise DaktelaTimeoutException(f"Request timed out: {e}")

    def _execute_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        body: Optional[Dict[str, Any]],
    ) -> httpx.Response:
        """Execute the actual HTTP request."""
        return self._client.request(
            method=method,
            url=url,
            headers=headers,
            cookies=cookies if cookies else None,
            json=body,
        )

    def _build_url(
        self, endpoint: str, query_params: Optional[Dict[str, Any]]
    ) -> str:
        """Build the full URL with query parameters."""
        endpoint = endpoint.lstrip("/")
        url = f"{self._config.base_url}/{endpoint}"

        params: List[Tuple[str, str]] = []

        if self._config.auth_method == AuthMethod.QUERY:
            params.append(("accessToken", self._config.access_token))

        if query_params:
            self._flatten_params(query_params, params)

        if params:
            url = f"{url}?{urlencode(params)}"

        return url

    def _flatten_params(
        self,
        params: Dict[str, Any],
        result: List[Tuple[str, str]],
        prefix: str = "",
    ) -> None:
        """Flatten nested parameters for URL encoding.

        Converts nested dicts/lists to Daktela's expected format:
        - filter[0][field]=name
        - filter[0][operator]=eq
        - fields[0]=name
        """
        for key, value in params.items():
            full_key = f"{prefix}[{key}]" if prefix else key

            if value is None:
                continue
            elif isinstance(value, dict):
                self._flatten_params(value, result, full_key)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._flatten_params(item, result, f"{full_key}[{i}]")
                    else:
                        result.append((f"{full_key}[{i}]", str(item)))
            else:
                result.append((full_key, str(value)))

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers including authentication."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._config.user_agent,
        }

        if self._config.auth_method == AuthMethod.HEADER:
            headers["X-AUTH-TOKEN"] = self._config.access_token

        return headers

    def _build_cookies(self) -> Dict[str, str]:
        """Build cookies for authentication if using cookie auth."""
        if self._config.auth_method == AuthMethod.COOKIE:
            return {"accessToken": self._config.access_token}
        return {}

    def _handle_response(self, response: httpx.Response) -> DaktelaResponse:
        """Process the HTTP response and handle errors."""
        status_code = response.status_code
        data = None
        total = None
        errors: List[Any] = []

        if response.headers.get('content-type') == 'application/json' and response.content:
            try:
                json_data = response.json()
                data, total, errors = self._parse_response_body(json_data)
            except ValueError:
                pass

            daktela_response = DaktelaResponse(
                status_code=status_code,
                data=data,
                total=total,
                errors=errors,
            )
        elif response.headers.get('content-type') == 'audio/opus' and response.content:
            data = response.content

            daktela_response = DaktelaFileResponse(
                status_code=status_code,
                data=data,
                filename=response.headers.get('filename'),
                errors=errors,
            )
        else:
            daktela_response = DaktelaResponse(
                status_code=status_code,
                data=data,
                total=total,
                errors=errors,
            )

        self._raise_for_status(status_code, errors, response)

        return daktela_response

    def _parse_response_body(
        self, json_data: Dict[str, Any]
    ) -> Tuple[Any, Optional[int], List[Any]]:
        """Parse the JSON response body."""
        data = None
        total = None
        errors: List[Any] = []

        if "result" in json_data:
            result = json_data["result"]
            if isinstance(result, dict):
                data = result.get("data")
                if "total" in result:
                    total = int(result["total"])
            else:
                data = result
        elif "data" in json_data:
            data = json_data["data"]

        if total is None and "total" in json_data:
            total = int(json_data["total"])

        if "error" in json_data:
            error = json_data["error"]
            errors = error if isinstance(error, list) else [error]
        elif "errors" in json_data:
            errors = json_data["errors"]

        return data, total, errors

    def _raise_for_status(
        self,
        status_code: int,
        errors: List[Any],
        response: httpx.Response,
    ) -> None:
        """Raise appropriate exception for error status codes."""
        if status_code < 400:
            return

        message = str(errors) if errors else f"Request failed with status {status_code}"

        if status_code == 401:
            raise DaktelaUnauthorizedException(message, errors)

        if status_code == 404:
            raise DaktelaNotFoundException(message, errors)

        if status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = int(response.headers["Retry-After"])
                except ValueError:
                    pass
            raise DaktelaRateLimitException(message, retry_after, errors)

        if status_code in (400, 422):
            raise DaktelaValidationException(message, status_code, errors)

        raise DaktelaException(message, status_code, errors)

    def _log(self, message: str) -> None:
        """Log a message if logger is configured."""
        if self._logger:
            self._logger.debug(message)

    def ping(self) -> bool:
        """Check API connectivity.

        Returns:
            True if API is reachable
        """
        try:
            response = self.send_request("GET", "ping")
            return response.is_success
        except DaktelaException:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Perform a detailed health check.

        Returns:
            Dict with health status, latency, and any errors
        """
        start_time = time.time()
        try:
            response = self.send_request("GET", "ping")
            latency = (time.time() - start_time) * 1000
            return {
                "healthy": response.is_success,
                "latency_ms": round(latency, 2),
                "status_code": response.status_code,
            }
        except DaktelaException as e:
            latency = (time.time() - start_time) * 1000
            return {
                "healthy": False,
                "latency_ms": round(latency, 2),
                "status_code": e.status_code,
                "error": str(e),
            }
