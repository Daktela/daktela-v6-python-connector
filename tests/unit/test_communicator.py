"""Protocol and resilience tests for ApiCommunicator."""

import json
import logging
from typing import Callable, List
from urllib.parse import parse_qs

import httpx
import pytest

from daktela import (
    AuthMethod,
    DaktelaConfig,
    DaktelaConnectionException,
    DaktelaException,
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
    assert request.headers["User-Agent"] == "DaktelaPythonSDK/1.1"
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
