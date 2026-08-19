"""HTTP transport layer for Daktela API communication."""

import logging
import time
from http.cookies import SimpleCookie
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlencode

import httpx

from ..auth import AuthMethod
from ..config import DaktelaConfig
from ..exceptions import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaNotFoundException,
    DaktelaProtocolException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)
from ..response import DaktelaResponse
from .rate_limit import RateLimitConfig
from .retry import RetryConfig


class ApiCommunicator:
    """Low-level transport handling protocol, authentication, and retries."""

    def __init__(
        self,
        config: DaktelaConfig,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
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
        """Close the HTTP client when it was created by this communicator."""
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
        query_params: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Send a request and return its parsed response.

        Transient HTTP and network failures use :class:`RetryConfig`. Rate
        limits use their own independently bounded :class:`RateLimitConfig`.
        """
        url = self._build_url(endpoint, query_params)
        headers = self._build_headers()
        method = method.upper()
        retry_attempt = 0
        rate_limit_attempt = 0

        while True:
            try:
                self._log(
                    "debug",
                    "Sending API request",
                    method=method,
                    endpoint=self._normalize_endpoint(endpoint),
                    attempt=retry_attempt + rate_limit_attempt + 1,
                )
                response = self._execute_request(method, url, headers, body)
                result = self._handle_response(response)
                self._log(
                    "debug",
                    "API response received",
                    method=method,
                    endpoint=self._normalize_endpoint(endpoint),
                    status_code=response.status_code,
                )
                return result

            except DaktelaRateLimitException as exc:
                wait_time = self._rate_limit_config.get_wait_time(exc.retry_after)
                if (
                    wait_time is None
                    or rate_limit_attempt >= self._rate_limit_config.max_retries
                ):
                    raise
                rate_limit_attempt += 1
                self._log(
                    "warning",
                    "Rate limited; retrying request",
                    wait_seconds=wait_time,
                    attempt=rate_limit_attempt,
                )
                time.sleep(wait_time)

            except DaktelaException as exc:
                if (
                    exc.status_code is not None
                    and self._retry_config.should_retry(exc.status_code, retry_attempt)
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, exc.status_code)
                    continue
                raise

            except httpx.TimeoutException as exc:
                if (
                    self._retry_config.retry_on_timeout
                    and retry_attempt < self._retry_config.max_retries
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, None)
                    continue
                raise DaktelaTimeoutException(f"Request timed out: {exc}") from exc

            except httpx.RequestError as exc:
                if (
                    self._retry_config.retry_on_connection_error
                    and retry_attempt < self._retry_config.max_retries
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, None)
                    continue
                raise DaktelaConnectionException(f"Request failed: {exc}") from exc

    def _wait_before_retry(self, attempt: int, status_code: Optional[int]) -> None:
        delay = self._retry_config.get_delay(attempt - 1)
        self._log(
            "warning",
            "Retrying API request",
            delay_seconds=delay,
            attempt=attempt,
            status_code=status_code,
        )
        time.sleep(delay)

    def _execute_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Mapping[str, Any]],
    ) -> httpx.Response:
        return self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
        )

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        value = endpoint.strip().strip("/")
        if not value:
            raise ValueError("endpoint must not be empty")
        if "://" in value or "?" in value or "#" in value or "\\" in value:
            raise ValueError("endpoint must be a relative API path without a query string")

        if value.lower().endswith(".json"):
            value = value[:-5]
        if not value:
            raise ValueError("endpoint must not be empty")
        if any(unquote(segment) in {".", ".."} for segment in value.split("/")):
            raise ValueError("endpoint must not contain relative path segments")

        value = value[0].lower() + value[1:]
        return f"{value}.json"

    def _build_url(
        self,
        endpoint: str,
        query_params: Optional[Mapping[str, Any]],
    ) -> str:
        url = f"{self._config.base_url}/{self._normalize_endpoint(endpoint)}"
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
        params: Mapping[str, Any],
        result: List[Tuple[str, str]],
        prefix: str = "",
    ) -> None:
        for key, value in params.items():
            full_key = f"{prefix}[{key}]" if prefix else key
            if value is None:
                continue
            if isinstance(value, Mapping):
                self._flatten_params(value, result, full_key)
            elif isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    item_key = f"{full_key}[{index}]"
                    if isinstance(item, Mapping):
                        self._flatten_params(item, result, item_key)
                    else:
                        result.append((item_key, self._stringify_param(item)))
            else:
                result.append((full_key, self._stringify_param(value)))

    @staticmethod
    def _stringify_param(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._config.user_agent,
        }
        if self._config.auth_method == AuthMethod.HEADER:
            headers["X-AUTH-TOKEN"] = self._config.access_token
        elif self._config.auth_method == AuthMethod.COOKIE:
            cookie = SimpleCookie()
            cookie["c_user"] = self._config.access_token
            headers["Cookie"] = cookie.output(header="").strip()
        return headers

    def _handle_response(self, response: httpx.Response) -> DaktelaResponse:
        status_code = response.status_code
        data: Any = None
        total: Optional[int] = None
        errors: List[Any] = []

        if response.content:
            try:
                json_data = response.json()
            except ValueError as exc:
                if status_code >= 400:
                    self._raise_for_status(status_code, errors, response)
                raise DaktelaProtocolException(
                    "API returned malformed JSON",
                    status_code=status_code,
                ) from exc
            if not isinstance(json_data, Mapping):
                raise DaktelaProtocolException(
                    "API response must be a JSON object",
                    status_code=status_code,
                )
            data, total, errors = self._parse_response_body(json_data)

        self._raise_for_status(status_code, errors, response)
        return DaktelaResponse(
            status_code=status_code,
            data=data,
            total=total,
            errors=errors,
        )

    def _parse_response_body(
        self,
        json_data: Mapping[str, Any],
    ) -> Tuple[Any, Optional[int], List[Any]]:
        data: Any = None
        total: Optional[int] = None

        if "result" in json_data:
            result = json_data["result"]
            if isinstance(result, Mapping):
                data = result["data"] if "data" in result else dict(result)
                if "total" in result:
                    total = self._parse_total(result["total"])
            else:
                data = result
        elif "data" in json_data:
            data = json_data["data"]

        if total is None and "total" in json_data:
            total = self._parse_total(json_data["total"])

        raw_errors = json_data.get("error", json_data.get("errors", []))
        if raw_errors is None:
            errors: List[Any] = []
        elif isinstance(raw_errors, list):
            errors = raw_errors
        else:
            errors = [raw_errors]
        return data, total, errors

    @staticmethod
    def _parse_total(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise DaktelaProtocolException("API response contains an invalid total") from exc

    def _raise_for_status(
        self,
        status_code: int,
        errors: List[Any],
        response: httpx.Response,
    ) -> None:
        if status_code < 400:
            return

        message = str(errors[0]) if len(errors) == 1 else str(errors)
        if not errors:
            message = f"Request failed with status {status_code}"

        if status_code == 401:
            raise DaktelaUnauthorizedException(message, errors)
        if status_code == 404:
            raise DaktelaNotFoundException(message, errors)
        if status_code == 429:
            retry_after = self._rate_limit_config.parse_retry_after(
                response.headers.get("Retry-After")
            )
            raise DaktelaRateLimitException(message, retry_after, errors)
        if status_code in (400, 422):
            raise DaktelaValidationException(message, status_code, errors)
        raise DaktelaException(message, status_code, errors)

    def _log(self, level: str, message: str, **context: Any) -> None:
        if self._logger:
            self._logger.log(getattr(logging, level.upper()), message, extra=context)

    def ping(self) -> bool:
        """Return whether the authenticated ``whoim`` endpoint is healthy."""
        try:
            return self.send_request("GET", "whoim").is_success
        except DaktelaException:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Return health, latency, status, and error details."""
        start_time = time.monotonic()
        try:
            response = self.send_request("GET", "whoim")
            latency = (time.monotonic() - start_time) * 1000
            return {
                "healthy": response.is_success,
                "latency_ms": round(latency, 2),
                "status_code": response.status_code,
            }
        except DaktelaException as exc:
            latency = (time.monotonic() - start_time) * 1000
            result: Dict[str, Any] = {
                "healthy": False,
                "latency_ms": round(latency, 2),
                "error": str(exc),
            }
            if exc.status_code is not None:
                result["status_code"] = exc.status_code
            return result
