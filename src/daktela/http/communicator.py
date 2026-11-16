"""HTTP transport layer for Daktela API communication."""

import logging
import re
import threading
import time
import warnings
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)
from urllib.parse import quote, unquote, urlencode

import httpx

from ..auth import AuthMethod
from ..config import _TOKEN_CHARACTERS, DaktelaConfig
from ..exceptions import (
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
    _format_errors,
)
from ..response import DaktelaResponse
from ..session import TokenSet, TokenStore, _Secret
from .rate_limit import RateLimitConfig
from .retry import RetryConfig

T = TypeVar("T")

_ACCESS_TOKEN_PATTERN = re.compile(r"(accessToken=)[^&\s\"']+")

# Failures raised before any request bytes reach the server, so resending is
# safe even for non-idempotent methods.
_UNSENT_REQUEST_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Seconds before its expiry at which a login session's access token is refreshed.
_TOKEN_REFRESH_MARGIN = 60

# Hosts a password may be sent to over plain HTTP without a warning.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_REDACTED = "***"

_TOKEN_NOT_ACCEPTED = "The access token was not accepted: the API did not identify a user."
_UNEXPECTED_WHOIM = "The API did not return a whoim result; check the instance URL."
_NO_CREDENTIALS = (
    "No access token: pass access_token to DaktelaConfig or log in with DaktelaClient.login()"
)

FileField = Tuple[str, bytes, str]


class _AccessTokenRedactor(logging.Filter):
    """Mask ``accessToken`` query values in httpx request log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            # Leave malformed records for logging's own error handling.
            return True
        redacted = _ACCESS_TOKEN_PATTERN.sub(r"\1***", message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def _install_access_token_redactor() -> None:
    logger = logging.getLogger("httpx")
    if not any(isinstance(filter_, _AccessTokenRedactor) for filter_ in logger.filters):
        logger.addFilter(_AccessTokenRedactor())


@dataclass(frozen=True)
class _Request:
    """A request as the retry loop sends it; credentials are added per attempt."""

    method: str
    url: str
    # Endpoint or path as logged, without the query string.
    endpoint: str
    query_params: Optional[Mapping[str, Any]] = None
    # Left out of the repr: a login body holds the password, a refresh body the
    # refresh token, and tracebacks print the arguments of their frames.
    body: Optional[Mapping[str, Any]] = field(default=None, repr=False)
    files: Optional[Mapping[str, FileField]] = field(default=None, repr=False)
    # JSON API requests send JSON and accept JSON; file requests accept anything.
    json_api: bool = True


def _is_transient(exc: DaktelaException) -> bool:
    """Return whether a failed request may succeed when it is repeated later."""
    if isinstance(
        exc, (DaktelaConnectionException, DaktelaTimeoutException, DaktelaRateLimitException)
    ):
        return True
    return exc.status_code is not None and exc.status_code >= 500


def _identifies_user(data: Any) -> bool:
    """Return whether a ``whoim`` result identifies the token's user.

    ``whoim`` is public: a request whose token was not accepted still gets
    HTTP 200, with ``user`` set to ``null``.
    """
    return isinstance(data, Mapping) and data.get("user") is not None


class _LoginSession:
    """State of a username/password login session."""

    def __init__(self, username: str, password: str, token_store: Optional[TokenStore]) -> None:
        self.username = username
        self.password = password
        self.token_store = token_store
        self.tokens: Optional[TokenSet] = None
        # Replaced tokens are still redacted, as later responses may repeat them.
        self.retired_tokens: List[str] = []
        # Reason the server rejected the login; no further login is sent after it.
        self.rejection: Optional[str] = None
        self.refresh_before_expiry = True

    def __repr__(self) -> str:
        return (
            f"_LoginSession(username={self.username!r}, password='***', "
            f"tokens={'***' if self.tokens else None})"
        )


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
        self._session: Optional[_LoginSession] = None
        self._session_lock = threading.RLock()
        self._redact_password = False
        if config.auth_method == AuthMethod.QUERY:
            _install_access_token_redactor()

    def close(self) -> None:
        """Close the HTTP client when it was created by this communicator."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ApiCommunicator":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Requests

    def send_request(
        self,
        method: str,
        endpoint: str,
        query_params: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
    ) -> DaktelaResponse:
        """Send an API request and return its parsed response.

        Transient HTTP and network failures use :class:`RetryConfig`. Failures
        after the request may have reached the server are only retried for
        methods in ``RetryConfig.retry_on_methods``. Rate limits use their own
        independently bounded :class:`RateLimitConfig`. Redirects are never
        followed; they raise :class:`DaktelaRedirectException`.
        """
        method = method.upper()
        endpoint = self._normalize_endpoint(endpoint)
        request = _Request(
            method, f"{self._config.base_url}/{endpoint}", endpoint, query_params, body
        )
        return self._send_authenticated(
            request, lambda response: self._handle_response(response, method)
        )

    def send_file_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Mapping[str, Any]] = None,
        files: Optional[Mapping[str, FileField]] = None,
    ) -> httpx.Response:
        """Send a request to a file endpoint outside ``/api/v6``.

        ``path`` is relative to the instance root, such as
        ``file/recording/activity_1``. Error statuses raise the same exceptions
        as API requests; a successful response is returned unparsed.
        """
        method = method.upper()
        path = self._normalize_file_path(path)
        request = _Request(
            method,
            f"{self._config.instance_url}/{path}",
            path,
            query_params,
            files=files,
            json_api=False,
        )
        return self._send_authenticated(request, self._handle_file_response)

    def _send_authenticated(
        self,
        request: "_Request",
        handler: Callable[[httpx.Response], T],
    ) -> T:
        session = self._session
        if session is None and not self._config.access_token:
            raise DaktelaUnauthorizedException(_NO_CREDENTIALS)
        self._prepare_session()
        token_used = self._current_access_token()
        try:
            return self._dispatch(request, handler, authenticate=True)
        except DaktelaUnauthorizedException:
            if session is None:
                raise
            # The server answers 401 before it processes a request, for example
            # after it ended the session, so resending it once is safe.
            with self._session_lock:
                if session.tokens is None or session.tokens.access_token == token_used:
                    self._refresh_tokens()
            return self._dispatch(request, handler, authenticate=True)

    def _dispatch(
        self,
        request: "_Request",
        handler: Callable[[httpx.Response], T],
        *,
        authenticate: bool,
    ) -> T:
        method = request.method
        retry_attempt = 0
        rate_limit_attempt = 0

        while True:
            token = self._current_access_token() if authenticate else ""
            request_url = self._build_url(request.url, request.query_params, token)
            headers = self._build_headers(token, request.json_api)
            try:
                self._log(
                    "debug",
                    "Sending API request",
                    method=method,
                    endpoint=request.endpoint,
                    attempt=retry_attempt + rate_limit_attempt + 1,
                )
                response = self._client.request(
                    method=method,
                    url=request_url,
                    headers=headers,
                    json=request.body,
                    files=request.files,
                    # A redirect would send the credentials to its target.
                    follow_redirects=False,
                )
                result = handler(response)
                self._log(
                    "debug",
                    "API response received",
                    method=method,
                    endpoint=request.endpoint,
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
                    and self._retry_config.allows_method(method)
                    and self._retry_config.should_retry(exc.status_code, retry_attempt)
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, exc.status_code)
                    continue
                raise

            except httpx.TimeoutException as exc:
                if (
                    self._retry_config.retry_on_timeout
                    and self._may_resend(method, exc)
                    and retry_attempt < self._retry_config.max_retries
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, None)
                    continue
                error, cause = self._transport_error(
                    DaktelaTimeoutException, "Request timed out", exc, authenticate
                )
                raise error from cause

            except httpx.RequestError as exc:
                if (
                    self._retry_config.retry_on_connection_error
                    and self._may_resend(method, exc)
                    and retry_attempt < self._retry_config.max_retries
                ):
                    retry_attempt += 1
                    self._wait_before_retry(retry_attempt, None)
                    continue
                error, cause = self._transport_error(
                    DaktelaConnectionException, "Request failed", exc, authenticate
                )
                raise error from cause

    def _transport_error(
        self,
        exception_type: Type[DaktelaException],
        prefix: str,
        exc: httpx.RequestError,
        authenticate: bool,
    ) -> Tuple[DaktelaException, Optional[BaseException]]:
        detail = str(exc)
        redacted = self._redact(detail)
        # A traceback prints the messages of chained exceptions and the arguments
        # of their frames, so the httpx exception is not chained when its message
        # holds a secret, nor for a login or refresh, whose httpx frames hold the
        # password or the refresh token in their arguments.
        chain = authenticate and redacted == detail
        return exception_type(f"{prefix}: {redacted}"), exc if chain else None

    def _may_resend(self, method: str, exc: httpx.RequestError) -> bool:
        return isinstance(exc, _UNSENT_REQUEST_ERRORS) or self._retry_config.allows_method(
            method
        )

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

    # ------------------------------------------------------------------
    # URLs and headers

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

    @staticmethod
    def _normalize_file_path(path: str) -> str:
        value = path.strip().strip("/")
        if not value:
            raise ValueError("path must not be empty")
        if "://" in value or "?" in value or "#" in value or "\\" in value:
            raise ValueError("path must be a relative path without a query string")
        if any(unquote(segment) in {"", ".", ".."} for segment in value.split("/")):
            raise ValueError("path must not contain empty or relative segments")
        return value

    def _build_url(
        self,
        url: str,
        query_params: Optional[Mapping[str, Any]],
        token: str,
    ) -> str:
        params: List[Tuple[str, str]] = []

        if token and self._config.auth_method == AuthMethod.QUERY:
            params.append(("accessToken", token))
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

    def _build_headers(self, token: str, json_api: bool) -> Dict[str, str]:
        headers = {
            "Accept": "application/json" if json_api else "*/*",
            "User-Agent": self._config.user_agent,
        }
        if json_api:
            # Multipart uploads get their Content-Type, with its boundary, from httpx.
            headers["Content-Type"] = "application/json"
        if not token:
            return headers
        if self._config.auth_method == AuthMethod.HEADER:
            headers["X-AUTH-TOKEN"] = token
        elif self._config.auth_method == AuthMethod.BEARER:
            headers["Authorization"] = f"Bearer {token}"
        elif self._config.auth_method == AuthMethod.COOKIE:
            cookie = SimpleCookie()
            cookie["c_user"] = token
            headers["Cookie"] = cookie.output(header="").strip()
        return headers

    # ------------------------------------------------------------------
    # Responses

    def _handle_response(self, response: httpx.Response, method: str) -> DaktelaResponse:
        status_code = response.status_code
        data: Any = None
        total: Optional[int] = None
        errors: List[Any] = []

        if response.content:
            try:
                json_data = response.json()
            except ValueError as exc:
                if status_code >= 300:
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
        if errors and method in _WRITE_METHODS:
            # A write that reports errors did not succeed, whatever the status.
            raise DaktelaValidationException(_format_errors(errors), status_code, errors)
        return DaktelaResponse(
            status_code=status_code,
            data=data,
            total=total,
            errors=errors,
        )

    def _handle_file_response(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 300:
            self._raise_for_status(response.status_code, self._file_errors(response), response)
        return response

    def _file_errors(self, response: httpx.Response) -> List[Any]:
        content_type = response.headers.get("Content-Type", "").lower()
        if not response.content or "json" not in content_type:
            return []
        try:
            payload = response.json()
        except ValueError:
            return []
        if isinstance(payload, Mapping):
            return self._parse_response_body(payload)[2]
        return self._redact_value([payload]) if payload else []

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
        return data, total, self._redact_value(errors)

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
        if status_code < 300:
            return
        if status_code < 400:
            location = response.headers.get("Location")
            location = self._redact(location) if location else None
            target = f" to {location}" if location else ""
            raise DaktelaRedirectException(
                f"The server redirected the request{target}. Redirects are not "
                "followed; configure the instance URL the API answers on, for "
                "example https:// instead of http://.",
                status_code,
                location,
                errors,
            )

        message = (
            _format_errors(errors) if errors else f"Request failed with status {status_code}"
        )

        if status_code == 401:
            raise DaktelaUnauthorizedException(message, errors)
        if status_code == 403:
            raise DaktelaForbiddenException(message, errors)
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

    # ------------------------------------------------------------------
    # Secrets

    def _secrets(self) -> List[str]:
        secrets: List[str] = []
        if self._config.access_token:
            secrets.append(self._config.access_token)
        session = self._session
        if session is not None:
            if session.tokens is not None:
                secrets.extend([session.tokens.access_token, session.tokens.refresh_token])
            secrets.extend(session.retired_tokens)
            # A login error may echo the password. Other responses are left alone,
            # as a short password would mangle their text.
            if self._redact_password:
                secrets.append(session.password)
        variants = {quote(secret, safe="") for secret in secrets} | set(secrets)
        return sorted((secret for secret in variants if secret), key=len, reverse=True)

    def _redact(self, text: str) -> str:
        for secret in self._secrets():
            text = text.replace(secret, _REDACTED)
        return text

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact(value)
        if isinstance(value, Mapping):
            return {
                self._redact(key) if isinstance(key, str) else key: self._redact_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._redact_value(item) for item in value]
        return value

    # ------------------------------------------------------------------
    # Login session

    def login(
        self,
        username: str,
        password: str,
        token_store: Optional[TokenStore] = None,
    ) -> None:
        """Start a login session with a username and password.

        The short-lived access token is refreshed before it expires and after
        the server rejects it, and the client logs in again when the session has
        ended. With ``token_store``, a stored session of the same user and
        instance is resumed instead of logging in.

        Warns when the password would be sent over plain HTTP to another host
        than the local machine, or without certificate verification.
        """
        # Masks the password in the arguments tracebacks print for this frame.
        password = _Secret(password)
        if not username:
            raise ValueError("username must not be empty")
        if not password:
            raise ValueError("password must not be empty")
        if self._config.access_token is not None:
            raise ValueError("login() requires a DaktelaConfig without access_token")
        self._warn_about_insecure_login()
        with self._session_lock:
            self._session = _LoginSession(username, password, token_store)
            stored = self._load_stored_tokens()
            if stored is not None:
                self._use_tokens(stored, received=False)
                return
            self._login_with_credentials()

    def _warn_about_insecure_login(self) -> None:
        url = httpx.URL(self._config.instance_url)
        if url.scheme == "http" and url.host not in _LOOPBACK_HOSTS:
            warnings.warn(
                "login() sends the password over plain HTTP; use an https:// instance URL",
                UserWarning,
                stacklevel=4,
            )
        if not self._config.verify_ssl:
            warnings.warn(
                "login() sends the password without certificate verification; "
                "enable verify_ssl",
                UserWarning,
                stacklevel=4,
            )

    def _current_access_token(self) -> str:
        session = self._session
        if session is None:
            return self._config.access_token or ""
        return session.tokens.access_token if session.tokens is not None else ""

    def _session_owner(self, session: _LoginSession) -> str:
        return f"{session.username}@{self._config.base_url}"

    def _prepare_session(self) -> None:
        session = self._session
        if session is None:
            return
        with self._session_lock:
            if session.tokens is None:
                self._login_with_credentials()
                return
            if not session.refresh_before_expiry or not session.tokens.access_token_expires_within(
                _TOKEN_REFRESH_MARGIN, time.time()
            ):
                return
            try:
                self._refresh_tokens()
            except DaktelaException as exc:
                tokens = session.tokens
                if tokens is None or tokens.access_token_expires_within(0, time.time()):
                    raise
                self._log(
                    "warning",
                    "Refreshing the access token failed; the current one is used until it expires",
                    error=exc.message,
                )

    def _refresh_tokens(self) -> None:
        session = self._require_session()
        with self._session_lock:
            tokens = session.tokens
            if tokens is None or tokens.is_refresh_token_expired(time.time()):
                self._login_with_credentials()
                return
            try:
                new_tokens = self._request_tokens(session, "refreshAccessToken")
            except (DaktelaValidationException, DaktelaUnauthorizedException):
                # The server no longer accepts the refresh token. Another client
                # sharing the token store may have rotated it.
                stored = self._load_stored_tokens()
                if stored is not None and stored.refresh_token != tokens.refresh_token:
                    self._use_tokens(stored, received=False)
                    self._log("info", "Resumed the login session saved by another client")
                    return
                self._login_with_credentials()
                return
            self._use_tokens(new_tokens, received=True)
            self._save_tokens(session)
            self._log("info", "Refreshed the access token of the Daktela API")

    def _login_with_credentials(self) -> None:
        session = self._require_session()
        if session.rejection is not None:
            raise DaktelaUnauthorizedException(
                f"The server rejected the login ({session.rejection}); call "
                "DaktelaClient.login() again with valid credentials."
            )
        try:
            tokens = self._request_tokens(session, "login")
        except DaktelaException as exc:
            if not _is_transient(exc):
                # Repeating a rejected login could lock the account or send
                # another two-factor code.
                session.rejection = exc.message
                self._retire_tokens(session)
                session.tokens = None
            raise
        self._use_tokens(tokens, received=True)
        self._save_tokens(session)
        self._log("info", "Logged in to the Daktela API", username=session.username)

    def _require_session(self) -> _LoginSession:
        session = self._session
        if session is None:
            raise DaktelaUnauthorizedException("There is no login session; call login() first.")
        return session

    def _request_tokens(self, session: _LoginSession, endpoint: str) -> TokenSet:
        current = session.tokens
        normalized = self._normalize_endpoint(endpoint)
        # The body is built inline into the request, whose repr masks it, so no
        # local variable of this frame holds the password or the refresh token.
        request = _Request(
            "POST",
            f"{self._config.base_url}/{normalized}",
            normalized,
            body=(
                {
                    "username": session.username,
                    "password": session.password,
                    # Return the tokens instead of setting them as cookies.
                    "only_token": "true",
                    # The client refreshes the session itself.
                    "client_side_refresh": "true",
                }
                if endpoint == "login"
                else {"refresh_token": current.refresh_token if current is not None else ""}
            ),
        )
        self._redact_password = endpoint == "login"
        try:
            response = self._dispatch(
                request,
                lambda response: self._handle_response(response, "POST"),
                authenticate=False,
            )
        finally:
            self._redact_password = False

        data = response.data if isinstance(response.data, Mapping) else {}
        access_token = data.get("accessToken")
        refresh_token = data.get("refreshToken")
        if endpoint != "login" and current is not None and not refresh_token:
            # The server keeps the refresh token when it does not rotate it.
            refresh_token = current.refresh_token
        if not self._is_valid_token(access_token) or not self._is_valid_token(refresh_token):
            raise DaktelaProtocolException(
                f"The {endpoint} response does not contain a valid access token "
                "and refresh token",
                status_code=response.status_code,
            )
        return TokenSet(str(access_token), str(refresh_token), self._session_owner(session))

    @staticmethod
    def _is_valid_token(value: Any) -> bool:
        return isinstance(value, str) and bool(_TOKEN_CHARACTERS.fullmatch(value))

    @staticmethod
    def _retire_tokens(session: _LoginSession, keep: Sequence[str] = ()) -> None:
        """Keep replaced tokens redacted, as later responses may repeat them."""
        if session.tokens is None:
            return
        replaced = [session.tokens.access_token, session.tokens.refresh_token]
        retired = dict.fromkeys(replaced + session.retired_tokens)
        session.retired_tokens = [token for token in retired if token not in keep][:4]

    def _use_tokens(self, tokens: TokenSet, received: bool) -> None:
        session = self._require_session()
        self._retire_tokens(session, keep=(tokens.access_token, tokens.refresh_token))
        session.tokens = tokens
        # A token that looks expired as soon as it is issued means the local clock
        # is ahead of the server, so it is only refreshed after a 401.
        session.refresh_before_expiry = not received or not tokens.access_token_expires_within(
            _TOKEN_REFRESH_MARGIN, time.time()
        )

    def _load_stored_tokens(self) -> Optional[TokenSet]:
        session = self._require_session()
        if session.token_store is None:
            return None
        try:
            stored = session.token_store.load()
        except Exception as exc:  # A broken store must not prevent logging in.
            # Only the exception type is logged: its message may quote stored
            # tokens the session does not know yet, so they cannot be redacted.
            self._log(
                "warning",
                "Loading the saved login session failed; logging in",
                error=type(exc).__name__,
            )
            return None
        # A store shared by several users or instances must not resume another session.
        if (
            stored is None
            or stored.owner != self._session_owner(session)
            or stored.is_refresh_token_expired(time.time())
        ):
            return None
        return stored

    def _save_tokens(self, session: _LoginSession) -> None:
        if session.token_store is None or session.tokens is None:
            return
        try:
            session.token_store.save(session.tokens)
        except Exception as exc:  # The session still works from memory.
            self._log(
                "warning",
                "Saving the login session failed; it is kept in memory",
                error=self._redact(str(exc)),
            )

    # ------------------------------------------------------------------
    # Health

    def _log(self, level: str, message: str, **context: Any) -> None:
        if self._logger:
            self._logger.log(getattr(logging, level.upper()), message, extra=context)

    def ping(self) -> bool:
        """Return whether the API identifies the user of the access token."""
        return bool(self.health_check()["healthy"])

    def health_check(self) -> Dict[str, Any]:
        """Return health, latency, status, and error details.

        The API is healthy only when the ``whoim`` endpoint identifies the user
        of the access token. ``whoim`` also answers requests whose token was not
        accepted (invalid, expired, or revoked token, or a deactivated user),
        with HTTP 200 and no user.
        """
        start_time = time.monotonic()
        try:
            response = self.send_request("GET", "whoim")
            session = self._session
            if (
                session is not None
                and session.tokens is not None
                and not _identifies_user(response.data)
            ):
                # whoim answers a session the server has ended with no user
                # instead of HTTP 401.
                self._refresh_tokens()
                response = self.send_request("GET", "whoim")
        except DaktelaException as exc:
            result: Dict[str, Any] = {
                "healthy": False,
                "latency_ms": round((time.monotonic() - start_time) * 1000, 2),
                "error": exc.message,
            }
            if exc.status_code is not None:
                result["status_code"] = exc.status_code
            return result

        healthy = response.is_success and _identifies_user(response.data)
        result = {
            "healthy": healthy,
            "latency_ms": round((time.monotonic() - start_time) * 1000, 2),
            "status_code": response.status_code,
        }
        if not healthy:
            result["error"] = self._describe_unhealthy(response)
        return result

    @staticmethod
    def _describe_unhealthy(response: DaktelaResponse) -> str:
        if response.errors:
            return _format_errors(response.errors)
        if isinstance(response.data, Mapping) and "user" in response.data:
            return _TOKEN_NOT_ACCEPTED
        return _UNEXPECTED_WHOIM

