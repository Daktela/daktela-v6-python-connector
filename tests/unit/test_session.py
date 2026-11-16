"""Tests for login sessions, token refresh, and token storage."""

import base64
import io
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Union

import httpx
import pytest

from daktela import (
    AuthMethod,
    DaktelaClient,
    DaktelaConfig,
    DaktelaConnectionException,
    DaktelaException,
    DaktelaProtocolException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
    InMemoryTokenStore,
    RetryConfig,
    TokenSet,
    TokenStore,
)
from daktela.http import ApiCommunicator
from daktela.http.communicator import _LoginSession, _Request
from daktela.session import _jwt_expiry, _Secret

API = "/api/v6"
OWNER = "alice@https://test.daktela.com/api/v6"
WHOIM_USER = {"result": {"version": {}, "user": {"name": "alice"}}}


def b64(data: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def jwt(subject: str, expires_in: Optional[int]) -> str:
    claims: Dict[str, object] = {"sub": subject}
    if expires_in is not None:
        claims["exp"] = int(time.time()) + expires_in
    return f"{b64({'alg': 'HS256'})}.{b64(claims)}.signature"


HOUR = 3600
ACCESS_1 = jwt("access-1", HOUR)
ACCESS_2 = jwt("access-2", HOUR)
REFRESH_1 = jwt("refresh-1", 30 * 24 * HOUR)
REFRESH_2 = jwt("refresh-2", 30 * 24 * HOUR)
EXPIRING = jwt("expiring", 30)
EXPIRED = jwt("expired", -10)

Responder = Union[httpx.Response, Callable[[httpx.Request], httpx.Response]]


class Server:
    """Routes requests by path; the last response for a path repeats."""

    def __init__(self) -> None:
        self.requests: List[httpx.Request] = []
        self.routes: Dict[str, List[Responder]] = {}

    def on(self, path: str, *responses: Responder) -> "Server":
        key = path if path.startswith("/file/") else API + path
        self.routes.setdefault(key, []).extend(responses)
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self.routes[request.url.path]
        responder = queue.pop(0) if len(queue) > 1 else queue[0]
        return responder(request) if callable(responder) else responder

    @property
    def paths(self) -> List[str]:
        return [request.url.path.removeprefix(API) for request in self.requests]

    def tokens_used(self, path: str) -> List[str]:
        return [
            request.headers.get("X-AUTH-TOKEN", "")
            for request in self.requests
            if request.url.path == API + path
        ]


def tokens(access: str, refresh: Optional[str] = None) -> httpx.Response:
    result = {"accessToken": access, "accessTokenExpirationDate": "2026-11-16 12:00:00"}
    if refresh is not None:
        result["refreshToken"] = refresh
    return httpx.Response(200, json={"result": result, "error": []})


def stored(access: str) -> InMemoryTokenStore:
    return InMemoryTokenStore(TokenSet(access, REFRESH_1, OWNER))


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"result": {"data": [], "total": 0}})


def communicator_for(
    server: Server,
    *,
    auth_method: AuthMethod = AuthMethod.HEADER,
    logger: Optional[logging.Logger] = None,
    retry_config: Optional[RetryConfig] = None,
) -> ApiCommunicator:
    client = httpx.Client(transport=httpx.MockTransport(server))
    config = DaktelaConfig("test.daktela.com", auth_method=auth_method, logger=logger)
    return ApiCommunicator(config, retry_config, None, client)


def logged_in(server: Server, **kwargs: object) -> ApiCommunicator:
    server.on("/login.json", tokens(ACCESS_1, REFRESH_1))
    communicator = communicator_for(server, **kwargs)  # type: ignore[arg-type]
    communicator.login("alice", "pa55word")
    return communicator


def test_login_sends_credentials_and_uses_the_access_token() -> None:
    server = Server().on("/users.json", ok)
    communicator = logged_in(server)

    communicator.send_request("GET", "users")

    login = server.requests[0]
    assert login.method == "POST"
    assert json.loads(login.content) == {
        "username": "alice",
        "password": "pa55word",
        "only_token": "true",
        "client_side_refresh": "true",
    }
    assert "X-AUTH-TOKEN" not in login.headers
    assert "Authorization" not in login.headers
    assert server.tokens_used("/users.json") == [ACCESS_1]


@pytest.mark.parametrize(
    ("auth_method", "check"),
    [
        (AuthMethod.BEARER, lambda r: r.headers["Authorization"] == f"Bearer {ACCESS_1}"),
        (AuthMethod.QUERY, lambda r: r.url.params["accessToken"] == ACCESS_1),
    ],
)
def test_login_session_with_other_auth_methods(
    auth_method: AuthMethod, check: Callable[[httpx.Request], bool]
) -> None:
    server = Server().on("/users.json", ok)
    communicator = logged_in(server, auth_method=auth_method)
    communicator.send_request("GET", "users")
    assert "accessToken" not in server.requests[0].url.params
    assert check(server.requests[1])


def test_rejected_login_is_redacted_and_never_repeated() -> None:
    server = Server().on(
        "/login.json",
        httpx.Response(400, json={"result": None, "error": ["Wrong password pa55word"]}),
    )
    communicator = communicator_for(server)

    with pytest.raises(DaktelaValidationException) as raised:
        communicator.login("alice", "pa55word")
    assert "pa55word" not in str(raised.value)
    assert raised.value.errors == ["Wrong password ***"]

    with pytest.raises(DaktelaUnauthorizedException, match="rejected the login"):
        communicator.send_request("GET", "users")
    health = communicator.health_check()
    assert health["healthy"] is False
    assert "rejected the login" in health["error"]
    assert server.paths == ["/login.json"]


def test_login_without_credentials_is_rejected() -> None:
    server = Server().on("/login.json", httpx.Response(401))
    communicator = communicator_for(server)
    with pytest.raises(DaktelaUnauthorizedException):
        communicator.login("alice", "pa55word")
    assert communicator._session is not None
    assert communicator._session.rejection == "Request failed with status 401"


@pytest.mark.parametrize(
    ("response", "exception", "reason"),
    [
        (
            httpx.Response(403, json={"error": ["User is blocked"]}),
            DaktelaException,
            "User is blocked",
        ),
        (tokens(ACCESS_1), DaktelaProtocolException, "does not contain a valid access token"),
        (
            httpx.Response(302, headers={"Location": "https://sso.example/"}),
            DaktelaException,
            "redirected",
        ),
    ],
)
def test_any_non_transient_login_failure_is_not_repeated(
    response: httpx.Response, exception: type[DaktelaException], reason: str
) -> None:
    server = Server().on("/login.json", response)
    communicator = communicator_for(server)

    with pytest.raises(exception):
        communicator.login("alice", "pa55word")
    with pytest.raises(DaktelaUnauthorizedException, match=reason):
        communicator.send_request("GET", "users")
    assert server.paths == ["/login.json"]


def test_transient_login_failure_is_retried_by_the_next_request() -> None:
    server = Server().on("/login.json", httpx.Response(503), tokens(ACCESS_1, REFRESH_1))
    server.on("/users.json", ok)
    communicator = communicator_for(server, retry_config=RetryConfig.disabled())

    with pytest.raises(DaktelaException) as raised:
        communicator.login("alice", "pa55word")
    assert raised.value.status_code == 503
    communicator.send_request("GET", "users")

    assert server.paths == ["/login.json", "/login.json", "/users.json"]


def test_rejected_login_keeps_replaced_tokens_redacted() -> None:
    server = Server()
    communicator = logged_in(server)
    assert communicator._session is not None
    communicator._session.tokens = TokenSet(EXPIRING, EXPIRED, OWNER)
    communicator._session.refresh_before_expiry = True
    server.routes[API + "/login.json"] = [httpx.Response(400, json={"error": ["locked"]})]

    with pytest.raises(DaktelaValidationException):
        communicator.send_request("GET", "users")

    assert communicator._session.tokens is None
    assert communicator._session.retired_tokens[:2] == [EXPIRING, EXPIRED]
    assert communicator._redact(f"{EXPIRING} {EXPIRED}") == "*** ***"


@pytest.mark.parametrize(
    "response",
    [
        tokens(ACCESS_1),
        tokens("bad token\n", REFRESH_1),
        httpx.Response(200, json={"result": "ok"}),
    ],
)
def test_login_response_without_valid_tokens(response: httpx.Response) -> None:
    communicator = communicator_for(Server().on("/login.json", response))
    with pytest.raises(DaktelaProtocolException, match="login response"):
        communicator.login("alice", "pa55word")


@pytest.mark.parametrize(
    ("username", "password", "token", "message"),
    [
        ("", "pw", None, "username"),
        ("alice", "", None, "password"),
        ("alice", "pw", "static", "without access_token"),
    ],
)
def test_login_argument_validation(
    username: str, password: str, token: Optional[str], message: str
) -> None:
    communicator = ApiCommunicator(DaktelaConfig("test.daktela.com", token))
    with pytest.raises(ValueError, match=message):
        communicator.login(username, password)
    communicator.close()


def test_expiring_token_is_refreshed_before_the_request() -> None:
    store = InMemoryTokenStore(TokenSet(EXPIRING, REFRESH_1, OWNER))
    server = Server().on("/refreshAccessToken.json", tokens(ACCESS_2)).on("/users.json", ok)
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word", store)

    communicator.send_request("GET", "users")

    assert server.paths == ["/refreshAccessToken.json", "/users.json"]
    assert json.loads(server.requests[0].content) == {"refresh_token": REFRESH_1}
    assert server.tokens_used("/users.json") == [ACCESS_2]
    saved = store.load()
    assert saved == TokenSet(ACCESS_2, REFRESH_1, OWNER)


def test_token_that_expires_on_arrival_is_refreshed_only_after_a_401() -> None:
    # The local clock is ahead of the server; refreshing before every request
    # would not help.
    server = Server().on("/login.json", tokens(EXPIRING, REFRESH_1))
    server.on("/users.json", ok, httpx.Response(401), ok)
    server.on("/refreshAccessToken.json", tokens(ACCESS_2, REFRESH_2))
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word")

    communicator.send_request("GET", "users")
    assert server.paths == ["/login.json", "/users.json"]

    communicator.send_request("GET", "users")
    assert server.paths[2:] == ["/users.json", "/refreshAccessToken.json", "/users.json"]
    assert server.tokens_used("/users.json") == [EXPIRING, EXPIRING, ACCESS_2]


def test_rejected_refresh_falls_back_to_login() -> None:
    server = (
        Server()
        .on("/refreshAccessToken.json", httpx.Response(400, json={"error": ["Invalid refresh"]}))
        .on("/login.json", tokens(ACCESS_2, REFRESH_2))
        .on("/users.json", ok)
    )
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word", stored(EXPIRING))

    communicator.send_request("GET", "users")

    assert server.paths == ["/refreshAccessToken.json", "/login.json", "/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_2]


def test_expired_refresh_token_logs_in_again() -> None:
    server = Server().on("/users.json", ok)
    communicator = logged_in(server)
    assert communicator._session is not None
    communicator._session.tokens = TokenSet(EXPIRING, EXPIRED, OWNER)
    communicator._session.refresh_before_expiry = True
    server.routes[API + "/login.json"] = [tokens(ACCESS_2, REFRESH_2)]

    communicator.send_request("GET", "users")

    assert server.paths == ["/login.json", "/login.json", "/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_2]


def test_failed_refresh_keeps_a_still_valid_token(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("daktela-session-test")
    caplog.set_level(logging.WARNING, logger="daktela-session-test")
    server = Server().on("/refreshAccessToken.json", httpx.Response(500)).on("/users.json", ok)
    communicator = communicator_for(server, logger=logger, retry_config=RetryConfig.disabled())
    communicator.login("alice", "pa55word", stored(EXPIRING))

    communicator.send_request("GET", "users")

    assert server.tokens_used("/users.json") == [EXPIRING]
    assert "Refreshing the access token failed" in caplog.text


def test_failed_refresh_of_an_expired_token_raises() -> None:
    server = Server().on("/refreshAccessToken.json", httpx.Response(500))
    communicator = communicator_for(server, retry_config=RetryConfig.disabled())
    communicator.login("alice", "pa55word", stored(EXPIRED))

    with pytest.raises(DaktelaException) as raised:
        communicator.send_request("GET", "users")
    assert raised.value.status_code == 500


def test_rejected_refresh_and_login_raise() -> None:
    server = (
        Server()
        .on("/refreshAccessToken.json", httpx.Response(400, json={"error": ["expired"]}))
        .on("/login.json", httpx.Response(400, json={"error": ["account locked"]}))
    )
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word", stored(EXPIRING))

    with pytest.raises(DaktelaValidationException, match="account locked"):
        communicator.send_request("GET", "users")


def test_unauthorized_request_is_refreshed_and_resent_once() -> None:
    server = Server().on(
        "/users.json",
        httpx.Response(401),
        httpx.Response(201, json={"result": {"name": "u"}}),
    )
    server.on("/refreshAccessToken.json", tokens(ACCESS_2, REFRESH_2))
    communicator = logged_in(server)

    response = communicator.send_request("POST", "users", body={"title": "t"})

    assert response.status_code == 201
    assert server.paths == ["/login.json", "/users.json", "/refreshAccessToken.json", "/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_1, ACCESS_2]


def test_second_unauthorized_response_is_raised() -> None:
    server = Server().on("/users.json", httpx.Response(401))
    server.on("/refreshAccessToken.json", tokens(ACCESS_2, REFRESH_2))
    communicator = logged_in(server)

    with pytest.raises(DaktelaUnauthorizedException):
        communicator.send_request("GET", "users")
    assert server.paths == ["/login.json", "/users.json", "/refreshAccessToken.json", "/users.json"]


def test_unauthorized_request_after_a_concurrent_refresh_is_only_resent() -> None:
    server = Server()
    communicator = logged_in(server)

    def refreshed_elsewhere(request: httpx.Request) -> httpx.Response:
        assert communicator._session is not None
        communicator._session.tokens = TokenSet(ACCESS_2, REFRESH_2, OWNER)
        return httpx.Response(401)

    server.on("/users.json", refreshed_elsewhere, ok)
    communicator.send_request("GET", "users")

    assert server.paths == ["/login.json", "/users.json", "/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_1, ACCESS_2]


def test_unauthorized_request_after_the_session_was_dropped_logs_in() -> None:
    server = Server()
    communicator = logged_in(server)

    def dropped(request: httpx.Request) -> httpx.Response:
        assert communicator._session is not None
        communicator._session.tokens = None
        return httpx.Response(401)

    server.on("/users.json", dropped, ok)
    communicator.send_request("GET", "users")

    assert server.paths == ["/login.json", "/users.json", "/login.json", "/users.json"]


def test_missing_tokens_trigger_a_new_login() -> None:
    server = Server().on("/users.json", ok)
    communicator = logged_in(server)
    assert communicator._session is not None
    communicator._session.tokens = None

    communicator.send_request("GET", "users")

    assert server.paths == ["/login.json", "/login.json", "/users.json"]


def test_stored_session_of_the_same_user_is_resumed() -> None:
    server = Server().on("/users.json", ok)
    store = InMemoryTokenStore(TokenSet(ACCESS_1, REFRESH_1, OWNER))
    communicator = communicator_for(server)

    communicator.login("alice", "pa55word", store)
    communicator.send_request("GET", "users")

    assert server.paths == ["/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_1]


@pytest.mark.parametrize(
    "stored",
    [
        TokenSet(ACCESS_2, REFRESH_2, "bob@https://test.daktela.com/api/v6"),
        TokenSet(ACCESS_2, REFRESH_2, "alice@https://other.daktela.com/api/v6"),
        TokenSet(ACCESS_2, EXPIRED, OWNER),
        None,
    ],
)
def test_stored_session_of_another_owner_or_expired_is_not_resumed(
    stored: Optional[TokenSet],
) -> None:
    server = Server().on("/login.json", tokens(ACCESS_1, REFRESH_1))
    store = InMemoryTokenStore(stored)
    communicator = communicator_for(server)

    communicator.login("alice", "pa55word", store)

    assert server.paths == ["/login.json"]
    assert store.load() == TokenSet(ACCESS_1, REFRESH_1, OWNER)


class BrokenStore:
    def load(self) -> Optional[TokenSet]:
        raise OSError(f"cannot read {REFRESH_1}")

    def save(self, tokens: TokenSet) -> None:
        raise OSError(f"cannot write {tokens.refresh_token}")


def test_broken_token_store_is_logged_and_ignored(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("daktela-store-test")
    caplog.set_level(logging.WARNING, logger="daktela-store-test")
    server = Server().on("/login.json", tokens(ACCESS_1, REFRESH_1)).on("/users.json", ok)
    communicator = communicator_for(server, logger=logger)

    communicator.login("alice", "pa55word", BrokenStore())
    communicator.send_request("GET", "users")

    assert "Loading the saved login session failed" in caplog.text
    assert "Saving the login session failed" in caplog.text
    # A load error may quote tokens the session does not know yet, so only its
    # type is logged.
    assert [record.__dict__["error"] for record in caplog.records] == [
        "OSError",
        "cannot write ***",
    ]
    assert REFRESH_1 not in caplog.text


def test_health_check_refreshes_a_session_the_server_ended() -> None:
    server = Server().on(
        "/whoim.json",
        httpx.Response(200, json={"result": {"version": {}, "user": None}}),
        httpx.Response(200, json=WHOIM_USER),
    )
    server.on("/refreshAccessToken.json", tokens(ACCESS_2, REFRESH_2))
    communicator = logged_in(server)

    assert communicator.health_check()["healthy"] is True
    assert server.paths == [
        "/login.json",
        "/whoim.json",
        "/refreshAccessToken.json",
        "/whoim.json",
    ]


def test_replaced_tokens_stay_redacted() -> None:
    server = Server().on(
        "/users.json",
        httpx.Response(400, json={"error": {ACCESS_2: [f"old {EXPIRING}, current {REFRESH_1}"]}}),
    )
    server.on("/refreshAccessToken.json", tokens(ACCESS_2))
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word", stored(EXPIRING))

    with pytest.raises(DaktelaValidationException) as raised:
        communicator.send_request("GET", "users")
    assert raised.value.errors == [{"***": ["old ***, current ***"]}]
    assert communicator._session is not None
    assert communicator._session.retired_tokens == [EXPIRING]


def test_refresh_without_a_login_session_is_rejected() -> None:
    communicator = ApiCommunicator(DaktelaConfig("test.daktela.com", "static"))
    with pytest.raises(DaktelaUnauthorizedException, match="no login session"):
        communicator._refresh_tokens()
    communicator.close()


def test_login_session_repr_hides_secrets() -> None:
    session = _LoginSession("alice", "pa55word", None)
    assert "pa55word" not in repr(session)
    assert "tokens=None" in repr(session)
    session.tokens = TokenSet(ACCESS_1, REFRESH_1)
    assert ACCESS_1 not in repr(session)
    assert "tokens=***" in repr(session)


def test_client_login_returns_a_working_client() -> None:
    server = Server().on("/login.json", tokens(ACCESS_1, REFRESH_1)).on("/users.json", ok)
    http_client = httpx.Client(transport=httpx.MockTransport(server))

    client = DaktelaClient.login(
        DaktelaConfig("test.daktela.com"), "alice", "pa55word", http_client=http_client
    )

    assert client.get("users").is_success
    assert server.tokens_used("/users.json") == [ACCESS_1]
    client.close()
    http_client.close()


def test_client_login_failure_closes_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: List[bool] = []
    monkeypatch.setattr(DaktelaClient, "close", lambda self: closed.append(True))
    server = Server().on("/login.json", httpx.Response(401))
    http_client = httpx.Client(transport=httpx.MockTransport(server))

    with pytest.raises(DaktelaUnauthorizedException):
        DaktelaClient.login(
            DaktelaConfig("test.daktela.com"), "alice", "pa55word", http_client=http_client
        )
    assert closed == [True]
    http_client.close()


def test_client_requires_a_token_or_a_login() -> None:
    with pytest.raises(ValueError, match="DaktelaClient.login"):
        DaktelaClient(DaktelaConfig("test.daktela.com"))


# ---------------------------------------------------------------------------
# TokenSet and stores


def test_token_set_expiry_and_serialization() -> None:
    token_set = TokenSet(EXPIRING, REFRESH_1, OWNER)
    now = time.time()

    assert token_set.access_token_expires_within(60, now)
    assert not token_set.access_token_expires_within(0, now)
    assert not token_set.is_refresh_token_expired(now)
    assert TokenSet(ACCESS_1, EXPIRED).is_refresh_token_expired(now)
    assert TokenSet.from_dict(token_set.to_dict()) == token_set
    assert TokenSet.from_dict({"accessToken": "a", "refreshToken": "r", "owner": 1}).owner is None
    assert TokenSet("a", "r").to_dict() == {"accessToken": "a", "refreshToken": "r"}
    assert EXPIRING not in repr(token_set) and REFRESH_1 not in repr(token_set)


def test_token_set_without_known_expiry_never_expires() -> None:
    token_set = TokenSet("static-access", "static-refresh")
    assert token_set.access_token_expires_at is None
    assert token_set.refresh_token_expires_at is None
    assert not token_set.access_token_expires_within(10**9, time.time())
    assert not token_set.is_refresh_token_expired(time.time())


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        "a.!!!.c",
        f"a.{b64([1, 2])}.c",
        f"a.{b64({'exp': True})}.c",
        f"a.{b64({'exp': '123'})}.c",
        f"a.{base64.urlsafe_b64encode(b'not json').decode()}.c",
    ],
)
def test_jwt_expiry_of_malformed_tokens(token: str) -> None:
    assert _jwt_expiry(token) is None


@pytest.mark.parametrize(
    "data",
    [{}, {"accessToken": "a"}, {"accessToken": 1, "refreshToken": "r"}],
)
def test_token_set_from_invalid_dict(data: Dict[str, object]) -> None:
    with pytest.raises(ValueError, match="accessToken and refreshToken"):
        TokenSet.from_dict(data)


@pytest.mark.parametrize(("access", "refresh"), [("", "r"), ("a", "")])
def test_token_set_rejects_empty_tokens(access: str, refresh: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        TokenSet(access, refresh)


def test_in_memory_token_store() -> None:
    store = InMemoryTokenStore()
    assert isinstance(store, TokenStore)
    assert store.load() is None
    assert repr(store) == "InMemoryTokenStore(stored=False)"
    store.save(TokenSet(ACCESS_1, REFRESH_1))
    assert store.load() == TokenSet(ACCESS_1, REFRESH_1)
    assert repr(store) == "InMemoryTokenStore(stored=True)"


# ---------------------------------------------------------------------------
# Review follow-ups: rotation, concurrency, uploads, and secret hygiene


def test_refresh_token_rotated_by_another_client_is_resumed_from_the_store() -> None:
    store = stored(EXPIRING)
    server = Server().on(
        "/refreshAccessToken.json", httpx.Response(400, json={"error": ["Invalid refresh token"]})
    )
    server.on("/users.json", ok)
    communicator = communicator_for(server)
    communicator.login("alice", "pa55word", store)
    # Another process sharing the store refreshed and rotated the tokens.
    store.save(TokenSet(ACCESS_2, REFRESH_2, OWNER))

    communicator.send_request("GET", "users")

    assert server.paths == ["/refreshAccessToken.json", "/users.json"]
    assert server.tokens_used("/users.json") == [ACCESS_2]


def test_unauthorized_request_is_not_resent_when_the_session_cannot_be_renewed() -> None:
    server = Server().on("/users.json", httpx.Response(401))
    server.on("/refreshAccessToken.json", httpx.Response(400, json={"error": ["expired"]}))
    communicator = logged_in(server)
    server.routes[API + "/login.json"] = [httpx.Response(400, json={"error": ["locked"]})]

    with pytest.raises(DaktelaValidationException, match="locked"):
        communicator.send_request("POST", "users", body={"title": "t"})
    assert server.paths == ["/login.json", "/users.json", "/refreshAccessToken.json", "/login.json"]


def test_upload_is_resent_with_its_full_body_after_a_401() -> None:
    uploaded = "e1f056dc18c82ce98c15bb87b923002af8ea9f53.pdf"
    server = Server().on(
        "/file/upload.php", httpx.Response(401), httpx.Response(200, json=uploaded)
    )
    server.on("/login.json", tokens(ACCESS_1, REFRESH_1))
    server.on("/refreshAccessToken.json", tokens(ACCESS_2, REFRESH_2))
    http_client = httpx.Client(transport=httpx.MockTransport(server))
    client = DaktelaClient.login(
        DaktelaConfig("test.daktela.com"), "alice", "pa55word", http_client=http_client
    )

    result = client.upload_file(io.BytesIO(b"%PDF-1.7 content"), "report.pdf")

    uploads = [request for request in server.requests if request.url.path == "/file/upload.php"]
    assert [request.headers["X-AUTH-TOKEN"] for request in uploads] == [ACCESS_1, ACCESS_2]
    assert all(b"%PDF-1.7 content" in request.content for request in uploads)
    assert result.name == uploaded
    http_client.close()


def test_concurrent_unauthorized_requests_refresh_the_session_once() -> None:
    barrier = threading.Barrier(2, timeout=5)
    refreshes: List[int] = []

    def users(request: httpx.Request) -> httpx.Response:
        if request.headers["X-AUTH-TOKEN"] == ACCESS_1:
            barrier.wait()  # both threads hold a 401 before either refreshes
            return httpx.Response(401)
        return ok(request)

    def refresh(request: httpx.Request) -> httpx.Response:
        refreshes.append(1)
        time.sleep(0.05)  # widen the window in which a second refresh could start
        return tokens(ACCESS_2, REFRESH_2)

    server = Server().on("/users.json", users).on("/refreshAccessToken.json", refresh)
    communicator = logged_in(server)
    errors: List[BaseException] = []

    def send() -> None:
        try:
            communicator.send_request("GET", "users")
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert refreshes == [1]
    assert server.tokens_used("/users.json").count(ACCESS_2) == 2


def test_login_request_repr_and_transport_errors_hide_credentials() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    server = Server().on("/login.json", offline)
    communicator = communicator_for(server, retry_config=RetryConfig.disabled())

    with pytest.raises(DaktelaConnectionException) as raised:
        communicator.login("alice", "pa55word")

    # The httpx frames hold the request body in their arguments.
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    request = _Request("POST", "u", "login.json", body={"password": "pa55word"}, files={})
    assert "pa55word" not in repr(request)


def test_secret_string_masks_its_repr_only() -> None:
    secret = _Secret("pa55word")
    assert repr(secret) == "'***'"
    assert secret == "pa55word"
    assert json.dumps({"password": secret}) == '{"password": "pa55word"}'


@pytest.mark.parametrize(
    ("url", "verify_ssl", "message"),
    [
        ("http://daktela.example", True, "plain HTTP"),
        ("https://daktela.example", False, "certificate verification"),
    ],
)
def test_insecure_login_warns(url: str, verify_ssl: bool, message: str) -> None:
    server = Server().on("/login.json", tokens(ACCESS_1, REFRESH_1))
    client = httpx.Client(transport=httpx.MockTransport(server))
    communicator = ApiCommunicator(DaktelaConfig(url, verify_ssl=verify_ssl), None, None, client)
    with pytest.warns(UserWarning, match=message):
        communicator.login("alice", "pa55word")


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1", "http://[::1]"])
def test_login_over_http_to_the_local_machine_does_not_warn(url: str) -> None:
    server = Server().on("/login.json", tokens(ACCESS_1, REFRESH_1))
    client = httpx.Client(transport=httpx.MockTransport(server))
    ApiCommunicator(DaktelaConfig(url), None, None, client).login("alice", "pa55word")


class InvalidTokenStore:
    def load(self) -> Optional[TokenSet]:
        return TokenSet.from_dict({"accessToken": f"{ACCESS_1}\n", "refreshToken": REFRESH_1})

    def save(self, tokens: TokenSet) -> None:
        pass


def test_stored_tokens_with_control_characters_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("daktela-invalid-store-test")
    caplog.set_level(logging.WARNING, logger="daktela-invalid-store-test")
    server = Server().on("/login.json", tokens(ACCESS_2, REFRESH_2))
    communicator = communicator_for(server, logger=logger)

    communicator.login("alice", "pa55word", InvalidTokenStore())

    assert server.paths == ["/login.json"]
    assert [record.__dict__["error"] for record in caplog.records] == ["ValueError"]
    assert ACCESS_1 not in caplog.text


def test_token_set_rejects_control_characters_without_echoing_them() -> None:
    with pytest.raises(ValueError, match="control") as raised:
        TokenSet(ACCESS_1, f"{REFRESH_1}\t")
    assert REFRESH_1 not in str(raised.value)
