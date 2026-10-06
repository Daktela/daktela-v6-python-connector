"""Protocol and resilience tests for ApiCommunicator."""

import json
import logging
from typing import Callable, Iterator, List
from urllib.parse import parse_qs

import httpx
import pytest

from daktela import (
    AuthMethod,
    DaktelaConfig,
    DaktelaConnectionException,
    DaktelaException,
    DaktelaForbiddenException,
    DaktelaNotFoundException,
    DaktelaProtocolException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
    RateLimitConfig,
    RetryConfig,
)
from daktela.http import ApiCommunicator
from daktela.http.communicator import _AccessTokenRedactor

Handler = Callable[[httpx.Request], httpx.Response]


def make_communicator(
    handler: Handler,
    *,
    auth_method: AuthMethod = AuthMethod.HEADER,
    retry_config: RetryConfig | None = None,
    rate_limit_config: RateLimitConfig | None = None,
    logger: logging.Logger | None = None,
) -> tuple[ApiCommunicator, httpx.Client]:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = DaktelaConfig(
        "test.daktela.com",
        "secret-token",
        auth_method=auth_method,
        logger=logger,
    )
    return (
        ApiCommunicator(config, retry_config, rate_limit_config, client),
        client,
    )


def ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"result": {"data": [{"id": 1}], "total": 1}})


def test_builds_canonical_header_authenticated_request() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"result": {"data": {"id": 1}}})

    communicator, client = make_communicator(handler)
    response = communicator.send_request(
        "post",
        "/Users/",
        {
            "filter": {
                "logic": "and",
                "filters": [{"field": "active", "operator": "eq", "value": True}],
            },
            "fields": ("name", "email"),
            "ignored": None,
        },
        {"name": "Alice"},
    )

    request = requests[0]
    query = parse_qs(request.url.query.decode())
    assert request.method == "POST"
    assert request.url.path == "/api/v6/users.json"
    assert request.headers["X-AUTH-TOKEN"] == "secret-token"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == "DaktelaPythonSDK/1.2"
    assert query["filter[logic]"] == ["and"]
    assert query["filter[filters][0][value]"] == ["true"]
    assert query["fields[0]"] == ["name"]
    assert "ignored" not in query
    assert json.loads(request.content) == {"name": "Alice"}
    assert response.status_code == 201
    client.close()


def test_query_authentication() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"data": []}})

    communicator, client = make_communicator(handler, auth_method=AuthMethod.QUERY)
    communicator.send_request("GET", "Users.json")

    assert requests[0].url.path == "/api/v6/users.json"
    assert requests[0].url.params["accessToken"] == "secret-token"
    assert "X-AUTH-TOKEN" not in requests[0].headers
    client.close()


def test_cookie_authentication() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"data": []}})

    communicator, client = make_communicator(handler, auth_method=AuthMethod.COOKIE)
    communicator.send_request("GET", "users")

    assert requests[0].headers["cookie"] == "c_user=secret-token"
    assert "X-AUTH-TOKEN" not in requests[0].headers
    client.close()


@pytest.mark.parametrize(
    "endpoint",
    ["", "/", "https://evil.example", "users?take=1", "users#fragment", "users\\x", "../x"],
)
def test_invalid_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError):
        ApiCommunicator._normalize_endpoint(endpoint)


def test_endpoint_with_only_json_suffix_is_invalid() -> None:
    with pytest.raises(ValueError):
        ApiCommunicator._normalize_endpoint(".json")


@pytest.mark.parametrize(
    ("payload", "data", "total", "errors"),
    [
        ({"result": {"data": [{"id": 1}], "total": "1"}}, [{"id": 1}], 1, []),
        ({"result": {"id": 1}}, {"id": 1}, None, []),
        ({"result": "pong"}, "pong", None, []),
        ({"data": {"id": 1}, "total": 1}, {"id": 1}, 1, []),
        ({"result": None, "error": None}, None, None, []),
        ({"result": None, "errors": "warning"}, None, None, ["warning"]),
        ({"result": None, "error": {"message": "warning"}}, None, None, [{"message": "warning"}]),
    ],
)
def test_response_shapes(
    payload: dict[str, object], data: object, total: int | None, errors: list[object]
) -> None:
    communicator, client = make_communicator(lambda request: httpx.Response(200, json=payload))
    response = communicator.send_request("GET", "users")
    assert response.data == data
    assert response.total == total
    assert response.errors == errors
    client.close()


def test_empty_response() -> None:
    communicator, client = make_communicator(lambda request: httpx.Response(204))
    response = communicator.send_request("DELETE", "users/1")
    assert response.status_code == 204
    assert response.data is None
    client.close()


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (httpx.Response(200, text="{invalid"), DaktelaProtocolException),
        (httpx.Response(200, json=[1, 2]), DaktelaProtocolException),
        (
            httpx.Response(200, json={"result": {"data": [], "total": "bad"}}),
            DaktelaProtocolException,
        ),
        (httpx.Response(400, text="not-json"), DaktelaValidationException),
    ],
)
def test_invalid_response(response: httpx.Response, exception: type[Exception]) -> None:
    communicator, client = make_communicator(
        lambda request: response,
        retry_config=RetryConfig.disabled(),
    )
    with pytest.raises(exception):
        communicator.send_request("GET", "users")
    client.close()


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, DaktelaUnauthorizedException),
        (404, DaktelaNotFoundException),
        (400, DaktelaValidationException),
        (422, DaktelaValidationException),
        (500, DaktelaException),
    ],
)
def test_status_exceptions(status: int, exception: type[DaktelaException]) -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(status, json={"error": ["failure"]}),
        retry_config=RetryConfig.disabled(),
    )
    with pytest.raises(exception) as raised:
        communicator.send_request("GET", "users")
    assert raised.value.errors == ["failure"]
    client.close()


def test_status_retry_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(503, json={"error": "temporary"}),
        httpx.Response(200, json={"result": {"data": [{"id": 1}]}}),
    ]
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    communicator, client = make_communicator(lambda request: responses.pop(0))
    assert communicator.send_request("GET", "users").is_success
    assert responses == []
    client.close()


def test_status_retry_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    communicator, client = make_communicator(
        handler,
        retry_config=RetryConfig(max_retries=2, initial_delay=0),
    )
    with pytest.raises(DaktelaException):
        communicator.send_request("GET", "users")
    assert calls == 3
    client.close()


def test_rate_limit_retry_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"result": {"data": []}}),
    ]
    waits: list[float] = []
    monkeypatch.setattr("daktela.http.communicator.time.sleep", waits.append)
    communicator, client = make_communicator(lambda request: responses.pop(0))

    assert communicator.send_request("GET", "users").is_success
    assert waits == [0.0]
    client.close()


def test_rate_limit_retry_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"})

    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    communicator, client = make_communicator(
        handler,
        rate_limit_config=RateLimitConfig(max_retries=1),
    )
    with pytest.raises(DaktelaRateLimitException) as raised:
        communicator.send_request("GET", "users")
    assert raised.value.retry_after == 0.0
    assert calls == 2
    client.close()


@pytest.mark.parametrize(
    "config",
    [RateLimitConfig.disabled(), RateLimitConfig(max_wait=1, default_retry_after=2)],
)
def test_rate_limit_not_retried(config: RateLimitConfig) -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(429),
        rate_limit_config=config,
    )
    with pytest.raises(DaktelaRateLimitException):
        communicator.send_request("GET", "users")
    client.close()


def test_timeout_retry_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"result": {"data": []}})

    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    communicator, client = make_communicator(handler)
    assert communicator.send_request("GET", "users").is_success
    client.close()

    communicator, client = make_communicator(
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=request)),
        retry_config=RetryConfig(retry_on_timeout=False),
    )
    with pytest.raises(DaktelaTimeoutException):
        communicator.send_request("GET", "users")
    client.close()


def test_connection_retry_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json={"result": {"data": []}})

    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    communicator, client = make_communicator(handler)
    assert communicator.send_request("GET", "users").is_success
    client.close()

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ProtocolError("broken", request=request)

    communicator, client = make_communicator(
        fail,
        retry_config=RetryConfig(retry_on_connection_error=False),
    )
    with pytest.raises(DaktelaConnectionException):
        communicator.send_request("GET", "users")
    client.close()


def test_logging_and_health(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("daktela-test")
    caplog.set_level(logging.DEBUG, logger="daktela-test")
    times = iter([1.0, 1.025])
    monkeypatch.setattr("daktela.http.communicator.time.monotonic", lambda: next(times))
    communicator, client = make_communicator(ok_response, logger=logger)

    assert communicator.ping()
    health = communicator.health_check()
    assert health == {"healthy": True, "latency_ms": 25.0, "status_code": 200}
    assert "Sending API request" in caplog.text
    assert "API response received" in caplog.text
    client.close()


def test_health_failure_with_and_without_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    times = iter([1.0, 1.001])
    monkeypatch.setattr("daktela.http.communicator.time.monotonic", lambda: next(times))
    communicator, client = make_communicator(
        lambda request: httpx.Response(401),
        retry_config=RetryConfig.disabled(),
    )
    assert not communicator.ping()
    result = communicator.health_check()
    assert result["healthy"] is False
    assert result["status_code"] == 401
    client.close()

    times = iter([2.0, 2.001])
    monkeypatch.setattr("daktela.http.communicator.time.monotonic", lambda: next(times))

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    communicator, client = make_communicator(
        offline,
        retry_config=RetryConfig.disabled(),
    )
    result = communicator.health_check()
    assert result["healthy"] is False
    assert "status_code" not in result
    client.close()


def test_client_ownership_and_context_manager() -> None:
    communicator, custom_client = make_communicator(ok_response)
    communicator.close()
    assert not custom_client.is_closed
    custom_client.close()

    owned = ApiCommunicator(DaktelaConfig("test.daktela.com", "token"))
    assert owned.__enter__() is owned
    owned.__exit__()
    assert owned._client.is_closed


def count_calls(
    outcome: Callable[[httpx.Request], httpx.Response],
) -> tuple[list[str], Handler]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return outcome(request)

    return calls, handler


def raise_read_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


def raise_read_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadError("reset", request=request)


@pytest.mark.parametrize(
    ("outcome", "exception"),
    [
        (lambda request: httpx.Response(500), DaktelaException),
        (raise_read_timeout, DaktelaTimeoutException),
        (raise_read_error, DaktelaConnectionException),
    ],
)
def test_post_is_not_retried_after_it_may_have_been_processed(
    monkeypatch: pytest.MonkeyPatch,
    outcome: Callable[[httpx.Request], httpx.Response],
    exception: type[DaktelaException],
) -> None:
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    calls, handler = count_calls(outcome)
    communicator, client = make_communicator(handler)
    with pytest.raises(exception):
        communicator.send_request("POST", "tickets", body={"title": "t"})
    assert calls == ["POST"]
    client.close()


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_idempotent_methods_are_retried(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    calls, handler = count_calls(lambda request: httpx.Response(500))
    communicator, client = make_communicator(
        handler, retry_config=RetryConfig(max_retries=2, initial_delay=0)
    )
    with pytest.raises(DaktelaException):
        communicator.send_request(method, "tickets/1")
    assert len(calls) == 3
    client.close()


def test_post_is_retried_when_request_was_never_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)
    outcomes: list[Callable[[httpx.Request], httpx.Response]] = [
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("down", request=request)),
        lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow", request=request)),
        lambda request: httpx.Response(429, headers={"Retry-After": "0"}),
        lambda request: httpx.Response(201, json={"result": {"data": {"name": "t"}}}),
    ]
    calls, handler = count_calls(lambda request: outcomes.pop(0)(request))
    communicator, client = make_communicator(handler)
    assert communicator.send_request("POST", "tickets", body={"title": "t"}).is_success
    assert calls == ["POST"] * 4
    client.close()


def test_post_retry_can_be_opted_into() -> None:
    calls, handler = count_calls(lambda request: httpx.Response(503))
    communicator, client = make_communicator(
        handler,
        retry_config=RetryConfig(max_retries=1, initial_delay=0, retry_on_methods=("POST",)),
    )
    with pytest.raises(DaktelaException):
        communicator.send_request("POST", "tickets", body={})
    assert len(calls) == 2
    client.close()


def test_forbidden_status_has_dedicated_exception() -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(403, json={"error": ["forbidden"]}),
    )
    with pytest.raises(DaktelaForbiddenException) as raised:
        communicator.send_request("GET", "users")
    assert raised.value.status_code == 403
    assert raised.value.errors == ["forbidden"]
    client.close()


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_successful_write_with_body_errors_raises(method: str) -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(200, json={"error": {"title": ["required"]}}),
    )
    with pytest.raises(DaktelaValidationException) as raised:
        communicator.send_request(method, "tickets", body={})
    assert raised.value.status_code == 200
    assert raised.value.errors == [{"title": ["required"]}]
    client.close()


def test_successful_read_with_body_errors_is_returned() -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(200, json={"error": ["partial"], "result": {"data": []}}),
    )
    response = communicator.send_request("GET", "tickets")
    assert response.errors == ["partial"]
    client.close()


def test_query_token_is_redacted_from_httpx_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    communicator, client = make_communicator(ok_response, auth_method=AuthMethod.QUERY)
    communicator.send_request("GET", "users", {"take": 1})
    make_communicator(ok_response, auth_method=AuthMethod.QUERY)

    assert "secret-token" not in caplog.text
    assert "accessToken=***" in caplog.text
    assert "take=1" in caplog.text
    assert sum(isinstance(f, _AccessTokenRedactor) for f in logging.getLogger("httpx").filters) == 1
    client.close()


def test_redactor_leaves_unrelated_records_untouched() -> None:
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, "plain %s", ("text",), None)
    assert _AccessTokenRedactor().filter(record)
    assert record.getMessage() == "plain text"


@pytest.mark.parametrize(
    ("error", "attempts"),
    [
        (httpx.PoolTimeout, 2),
        (httpx.WriteTimeout, 1),
        (httpx.RemoteProtocolError, 1),
    ],
)
def test_post_resend_depends_on_whether_request_was_sent(
    monkeypatch: pytest.MonkeyPatch,
    error: type[httpx.RequestError],
    attempts: int,
) -> None:
    monkeypatch.setattr("daktela.http.communicator.time.sleep", lambda delay: None)

    def fail(request: httpx.Request) -> httpx.Response:
        raise error("failure", request=request)

    calls, handler = count_calls(fail)
    communicator, client = make_communicator(
        handler, retry_config=RetryConfig(max_retries=1, initial_delay=0)
    )
    with pytest.raises(DaktelaException):
        communicator.send_request("POST", "tickets", body={})
    assert len(calls) == attempts
    client.close()


def test_redactor_tolerates_malformed_records() -> None:
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, "%s %s", ("one",), None)
    assert _AccessTokenRedactor().filter(record)


@pytest.fixture
def clean_httpx_filters() -> Iterator[logging.Logger]:
    logger = logging.getLogger("httpx")
    saved = list(logger.filters)
    for filter_ in saved:
        logger.removeFilter(filter_)
    yield logger
    for filter_ in list(logger.filters):
        logger.removeFilter(filter_)
    for filter_ in saved:
        logger.addFilter(filter_)


@pytest.mark.parametrize("auth_method", [AuthMethod.HEADER, AuthMethod.COOKIE])
def test_redactor_is_only_installed_for_query_auth(
    clean_httpx_filters: logging.Logger, auth_method: AuthMethod
) -> None:
    _, client = make_communicator(ok_response, auth_method=auth_method)
    assert not any(isinstance(f, _AccessTokenRedactor) for f in clean_httpx_filters.filters)
    client.close()


def test_redactor_masks_token_in_any_query_position() -> None:
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        "HTTP Request: %s %s",
        ("GET", "https://x/api/v6/users.json?take=1&accessToken=a%26b%3Dc&skip=2"),
        None,
    )
    assert _AccessTokenRedactor().filter(record)
    assert record.getMessage() == (
        "HTTP Request: GET https://x/api/v6/users.json?take=1&accessToken=***&skip=2"
    )


@pytest.mark.parametrize("method", ["PATCH", "post"])
def test_other_write_spellings_raise_on_body_errors(method: str) -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(200, json={"error": ["failure"]}),
    )
    with pytest.raises(DaktelaValidationException):
        communicator.send_request(method, "tickets", body={})
    client.close()


def test_successful_write_without_body_errors_returns() -> None:
    communicator, client = make_communicator(
        lambda request: httpx.Response(201, json={"error": [], "result": {"data": {"id": 1}}}),
    )
    assert communicator.send_request("POST", "tickets", body={}).get("id") == 1
    client.close()


@pytest.mark.parametrize(
    ("error", "retry_config", "exception"),
    [
        (
            httpx.ConnectError,
            RetryConfig(retry_on_connection_error=False),
            DaktelaConnectionException,
        ),
        (httpx.ConnectTimeout, RetryConfig(retry_on_timeout=False), DaktelaTimeoutException),
    ],
)
def test_retry_flags_take_precedence_for_unsent_post(
    error: type[httpx.RequestError],
    retry_config: RetryConfig,
    exception: type[DaktelaException],
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise error("failure", request=request)

    calls, handler = count_calls(fail)
    communicator, client = make_communicator(handler, retry_config=retry_config)
    with pytest.raises(exception):
        communicator.send_request("POST", "tickets", body={})
    assert calls == ["POST"]
    client.close()
