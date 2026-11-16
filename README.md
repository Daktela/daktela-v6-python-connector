# Daktela V6 Python SDK

A typed Python client for the Daktela V6 REST API. It supports CRUD operations,
nested queries, static tokens and username/password login sessions, file
downloads and uploads, bounded retries, rate-limit handling, health checks, and
memory-efficient pagination.

## Requirements

- Python 3.11 or newer
- A Daktela V6 instance URL
- An API access token, or the username and password of an account without
  two-factor authentication, with permissions for the resources you use

## Installation

```bash
pip install daktela
```

## Quick start

```python
from daktela import DaktelaClient, DaktelaConfig, DaktelaFilter, DaktelaQuery

config = DaktelaConfig(
    url="my.daktela.com",
    access_token="your-access-token",
)

with DaktelaClient(config) as client:
    query = (
        DaktelaQuery()
        .fields("name", "title", "stage")
        .filter(DaktelaFilter.eq("stage", "OPEN"))
        .take(50)
    )
    response = client.get("tickets", query)

    for ticket in response:
        print(ticket["name"], ticket["title"])
```

Endpoint names can be supplied with or without `.json`; the SDK normalizes them
to the API's canonical JSON path.

## CRUD and relations

```python
# List resources
response = client.get("tickets", DaktelaQuery().take(25))

# Read, update, and delete one object; its name is safely URL-encoded
ticket = client.get_one("tickets", "ticket-123").as_dict()
client.put_one("tickets", "ticket-123", {"stage": "CLOSE"})
client.delete_one("tickets", "ticket-123")

# Read a relation
activities = client.get_relation(
    "tickets",
    "ticket-123",
    "activities",
    DaktelaQuery().take(100),
)

# Create
created = client.post("tickets", {"title": "New request"})
```

`get_one()`, `put_one()`, `delete_one()`, and `get_relation()` reject object and
relation names that could address another endpoint: empty names, `.` and `..`,
and names containing `/`, `\`, or NUL. `put()` and `delete()` take a raw endpoint
path such as `"tickets/ticket-123"` and do not encode it, so prefer the `_one`
methods for names you did not write yourself.

Every operation accepts additional API-specific query parameters:

```python
client.post("tickets", {"title": "New request"}, {"custom": "value"})
client.delete_one("tickets", "ticket-123", {"audit": True})

query = DaktelaQuery().param("custom", "value").params({"another": 1})
client.get("tickets", query)
```

Structured query values take precedence over additional parameters with the
same key.

## Query builder

### Fields, sorting, and pagination

```python
from daktela import DaktelaPagination, DaktelaQuery, DaktelaSort

query = (
    DaktelaQuery()
    .fields("name", "title", "created")
    .sort(DaktelaSort.desc("created"))
    .pagination(pagination=DaktelaPagination.page(2, 25))
)
```

### Filters

```python
from daktela import DaktelaFilter

DaktelaFilter.eq("stage", "OPEN")
DaktelaFilter.neq("stage", "CLOSE")
DaktelaFilter.gt("created", "2026-01-01 00:00:00")
DaktelaFilter.gte("created", "2026-01-01 00:00:00")
DaktelaFilter.lt("edited", "2026-02-01 00:00:00")
DaktelaFilter.lte("edited", "2026-02-01 00:00:00")
DaktelaFilter.contains("title", "urgent")
DaktelaFilter.not_contains("title", "spam")
DaktelaFilter.starts_with("name", "ticket-")
DaktelaFilter.ends_with("email", "@example.com")
DaktelaFilter.like("title", "%urgent%")       # SQL LIKE pattern
DaktelaFilter.not_like("name", "test-%")
DaktelaFilter.in_("stage", ["OPEN", "WAIT"])
DaktelaFilter.not_in("stage", ["CLOSE", "ARCHIVE"])
DaktelaFilter.is_null("user")
DaktelaFilter.is_not_null("user")
```

These are the operators the Daktela API supports. `like()` and `not_like()` use
the value as an SQL `LIKE` pattern, where `%` matches any text and `_` any single
character; use `contains()` for a plain substring.

`in_()` and `not_in()` raise `ValueError` for an empty list. An empty list
cannot be sent as a filter value, and a filter without a value could match
every record.

`begins()`, `ends()`, `not_begins()`, and `not_ends()` are deprecated. Before
version 1.3 they sent operators the API rejects. `begins()` and `ends()` now
send `startswith` and `endswith`; `not_begins()` and `not_ends()` send
`notlike` with a `value%` or `%value` pattern.

Filters added directly to a query are combined with AND. Logical groups can be
nested:

```python
query = (
    DaktelaQuery()
    .filter(DaktelaFilter.eq("priority", "HIGH"))
    .filter(
        DaktelaFilter.or_(
            DaktelaFilter.eq("stage", "OPEN"),
            DaktelaFilter.eq("stage", "WAIT"),
        )
    )
)
```

Use `custom()` for operators without a named helper, and its `field_type` to
limit a custom-field filter to custom fields of one type:

```python
# Contacts with any email custom field ending in @example.com
DaktelaFilter.custom("customFields", "endswith", "@example.com", field_type="email")

# A specific custom field
DaktelaFilter.custom("customFields.homeemail", "endswith", "@example.com")
```

## Pagination

`iterate()` requests pages only as they are needed:

```python
iterator = client.iterate(
    "tickets",
    DaktelaQuery()
    .filter(DaktelaFilter.eq("stage", "OPEN"))
    .sort(DaktelaSort.asc("name")),
    page_size=100,
    max_items=1_000,
)

for ticket in iterator:
    process(ticket)

print(iterator.total)
print(iterator.items_yielded)
```

Page responses expose totals and errors:

```python
for page in client.iterate("tickets", page_size=100).pages():
    print(page.total, page.status_code)
```

Available helpers consume the remaining iterator:

```python
first = client.iterate("tickets").first()
all_items = client.iterate("tickets", max_items=50).collect()
count = client.iterate("tickets").count()
empty = client.iterate("tickets").is_empty()

iterator = client.iterate("tickets")
iterator.each(lambda item, index: print(index, item["name"]))

active = client.iterate("users").filter(lambda user: user["active"])
names = client.iterate("users").map(lambda user: user["name"])
```

For small datasets, `get_all()` collects all pages directly:

```python
tickets = client.get_all("tickets", page_size=100, max_items=500)
```

By default, request exceptions and pages whose response reports errors raise
a `DaktelaException`. `pages()` yields an error page before raising it. Set
`stop_on_error=False` to skip failed pages (the latest one is available as
`iterator.last_error`). `max_error_pages` bounds consecutive skipped pages;
reaching it raises the last error instead of silently ending iteration.

Most resources return at most 1000 records per request. Pagination advances by
the number of records actually returned, so a server that caps the page size
below `page_size` does not truncate iteration when it reports a `total`.
Without a total, a short page ends iteration, so keep `page_size` within the
server's limit.
Pagination is offset-based: sort on a stable field, for example
`DaktelaSort.asc("name")`, so that records created or edited during iteration
are not skipped or returned twice. A single iterator supports either item
iteration or `pages()`, not both.

## Authentication and client configuration

```python
from daktela import AuthMethod, DaktelaConfig

config = DaktelaConfig(
    url="https://my.daktela.com/",
    access_token="your-access-token",
    auth_method=AuthMethod.BEARER,
    timeout=30.0,
    user_agent="MyIntegration/1.0",
    verify_ssl=True,
)
```

Authentication methods:

- `AuthMethod.HEADER` sends the `X-AUTH-TOKEN` header. It is the default and
  works on every Daktela version.
- `AuthMethod.BEARER` sends the standard `Authorization: Bearer` header, which
  the Daktela API documentation recommends. It requires Daktela 31.37.0,
  32.36.0, 33.14.0, or later.
- `AuthMethod.QUERY` sends the `accessToken` query parameter. Tokens in URLs
  can end up in proxy and server access logs, so prefer a header. The SDK masks
  the token in the `httpx` logger's request lines.
- `AuthMethod.COOKIE` sends the `c_user` cookie. It is deprecated: Daktela 32
  and later accept only web-session tokens in this cookie, so a static API token
  is ignored there.

Static API tokens expire (up to 720 days since Daktela 2025.2, optionally
extended on each use). Monitor them with `health_check()`. The configuration
rejects tokens containing whitespace or control characters, such as the line
break of a token read from a file, without echoing the token.

Hostnames without a scheme default to HTTPS. Explicit HTTP URLs are preserved
for local development. An instance served under a path prefix, for example
behind a reverse proxy, keeps the prefix: `https://example.com/daktela/` sends
API requests to `https://example.com/daktela/api/v6/`. Never disable
certificate verification in production.

The SDK never follows HTTP redirects, because a redirect would send the access
token or login credentials to its target and could resend a create request. A
redirect raises `DaktelaRedirectException` with the target in `location`;
usually the configured URL needs `https://` or another host name.

An existing `httpx.Client` can be supplied for proxies, custom transports, or
application-managed connection pools:

```python
import httpx

http_client = httpx.Client(proxy="http://proxy.example:8080")
client = DaktelaClient(config, http_client=http_client)
```

The SDK does not close an injected client; its owner remains responsible for it.

## Logging in with a username and password

Instead of a static token, the client can log in. It refreshes the short-lived
access token before it expires and after the server rejects it, and logs in
again when the session has ended:

```python
from daktela import DaktelaClient, DaktelaConfig

client = DaktelaClient.login(
    DaktelaConfig(url="my.daktela.com"),  # no access_token
    "api-user",
    "password",
)
```

Each login starts a new session on the Daktela server. To reuse one session
across processes, pass a `TokenStore` that keeps the tokens in your cache or
database:

```python
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from daktela import DaktelaClient, DaktelaConfig, TokenSet


class FileTokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Optional[TokenSet]:
        if not self.path.exists():
            return None
        return TokenSet.from_dict(json.loads(self.path.read_text()))

    def save(self, tokens: TokenSet) -> None:
        # mkstemp() creates a file only its owner can read; replace() is atomic
        fd, temp = tempfile.mkstemp(dir=self.path.parent)
        with os.fdopen(fd, "w") as file:
            json.dump(tokens.to_dict(), file)
        os.replace(temp, self.path)


client = DaktelaClient.login(
    DaktelaConfig(url="my.daktela.com"),
    "api-user",
    "password",
    token_store=FileTokenStore(Path("/var/lib/myapp/daktela-tokens.json")),
)
```

`InMemoryTokenStore` shares a session between clients in one process.

- The password is kept in memory to log in again; the SDK never stores it. It
  is redacted from errors the server returns for a login and masked in the
  arguments that tracebacks print.
- `login()` warns when the password would be sent over plain HTTP to another
  host than the local machine, or with certificate verification disabled.
- Saved tokens record the user and instance they belong to, so one store can be
  shared safely. When the store fails to load or save, the client continues
  and logs a warning to `DaktelaConfig.logger`, if one is set. Tokens with
  whitespace or control characters are rejected when a `TokenSet` is created.
- When the server rejects the refresh token, the client first reloads the
  store, in case another process sharing it has rotated the tokens, and logs in
  again only when the store holds nothing newer.
- Refresh tokens are long-lived credentials. Store them as securely as
  passwords, and use an `https://` instance URL with certificate verification.
- After the server rejects a login (any error other than a connection failure,
  a timeout, HTTP 429, or a 5xx status), the client sends no further login,
  which could lock the account, until `DaktelaClient.login()` is called again.
  Requests then raise `DaktelaUnauthorizedException` with the server's reason.
- When the server rejects the access token with HTTP 401, the client refreshes
  it and sends the request once more. The server answers 401 before it
  processes a request, so the request is not executed twice.
- Accounts with two-factor authentication cannot log in this way. Use a static
  token for them.
- The client can be shared between threads. Token refreshes and logins are
  serialized: while one runs, including its retries and rate-limit waits, other
  requests of the client wait for it.

## Files

Download call recordings and attachments, and upload files for entities that
reference them:

```python
from pathlib import Path

# Call recording of an activity
recording = client.download_recording("activity_123456789")
recording.save("call.mp3")
print(recording.filename, recording.content_type, recording.size)

# Attachment or another stored file, in its original size
attachment = client.download_file("activitiesEmail", "170", icon_hash="report.pdf")

# Upload, then reference the file once in the entity that uses it
uploaded = client.upload_file(Path("report.pdf").read_bytes(), "report.pdf")
client.post(
    "activities",
    {
        "type": "EMAIL",
        "queue": "5000",
        "to": "customer@example.com",
        "subject": "Your report",
        "message": "<p>The report is attached.</p>",
        "add_files": [uploaded.as_dict()],
        "sendMail": True,
        "action": "CLOSE",
    },
)
```

`DaktelaFile.filename` comes from the server and, for attachments, from whoever
sent the file. Build paths from `safe_filename`, its base name without
directory parts or control characters and with the characters Windows forbids
replaced, so it names a file inside the directory on every platform:
`recording.save(directory / (recording.safe_filename or "download"))`.

`download_file()` raises `DaktelaNotFoundException` for a missing file, and also
when the server does not accept the access token, which the download endpoint
reports as HTTP 404 too. Uploads are create requests: like `POST`, they are
resent only when the connection could not be established, on HTTP 429, and,
with a login session, once after an HTTP 401. The server removes unused uploads
after a short time and rejects blocked file types with
`DaktelaValidationException`.

## Retries and rate limits

Transient status codes, connection failures, and timeouts use exponential
backoff. Failures that occur after a request may have reached the server are
only retried for the methods in `RetryConfig.retry_on_methods` (GET, HEAD,
OPTIONS, PUT, DELETE by default). `POST` is not idempotent, so it is only
retried after an HTTP 429 or when the connection could not be opened. A
retried create could otherwise add duplicate records. Opt in with, for example,
`RetryConfig(retry_on_methods=("GET", "PUT", "DELETE", "POST"))`.

```python
from daktela import RateLimitConfig, RetryConfig

client = DaktelaClient(
    config,
    retry_config=RetryConfig(
        max_retries=4,
        initial_delay=0.5,
        max_delay=20.0,
        jitter=0.25,
    ),
    rate_limit_config=RateLimitConfig(
        enabled=True,
        max_retries=3,
        max_wait=120.0,
        default_retry_after=5.0,
    ),
)
```

`Retry-After` supports both numeric seconds and HTTP dates. Rate-limit retries
are independently bounded. Use `RetryConfig.disabled()` or
`RateLimitConfig.disabled()` when the application owns retry behavior.

## Responses and exceptions

```python
response.data
response.total
response.errors
response.first_error
response.status_code
response.is_success
response.is_empty
response.has_errors

response.as_list()
response.as_dict()
response.get("name", "fallback")
```

A `POST`, `PUT`, or `DELETE` whose response reports errors raises
`DaktelaValidationException`, even when the HTTP status is 2xx. GET responses
keep body errors in `response.errors`. Exception messages flatten nested API
errors into readable text, for example `title: required`, and the access token,
session tokens, and (for a login) the password are redacted from messages and
errors.

The SDK raises specific exceptions for common failures:

```python
from daktela import (
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

try:
    ticket = client.get_one("tickets", "missing")
except DaktelaNotFoundException:
    print("Ticket not found")
except DaktelaForbiddenException:
    print("Token lacks access to tickets")
except DaktelaRateLimitException as error:
    print("Retry after", error.retry_after)
except DaktelaRedirectException as error:
    print("Check the instance URL; redirected to", error.location)
except DaktelaProtocolException as error:
    print("Unexpected API response", error)
except DaktelaException as error:
    print(error.status_code, error.errors)
```

## Health checks

```python
if client.ping():
    print("API is reachable and accepts the access token")

health = client.health_check()
# Healthy:         {"healthy": True, "latency_ms": 45.2, "status_code": 200}
# Token rejected:  {"healthy": False, "latency_ms": 40.1, "status_code": 200,
#                   "error": "The access token was not accepted: the API did not identify a user."}
# API error:       {"healthy": False, "latency_ms": 52.7, "status_code": 400,
#                   "error": "New password should be set"}
# Network failure: {"healthy": False, "latency_ms": 2001.3, "error": "Request failed: ..."}
```

Both call the `whoim` endpoint and report the API as healthy only when it
identifies the user of the access token. `whoim` also answers requests whose
token was not accepted (an invalid, expired, or revoked token, or a deactivated
user) with HTTP 200 and no user. For an account with an unfinished password
change, `whoim` answers HTTP 400 although other endpoints still accept the
token. `whoim` is heavier than a typical read: use the health check at startup
or for monitoring, not before every request.

## Phone-number normalization

```python
from daktela import normalize_phone_number

normalize_phone_number("773 794 604")
# "00420773794604"

normalize_phone_number("(773) 794-604", plus_sign=True)
# "+420773794604"
```

Whitespace and the separators `-`, `(`, `)`, `.`, and `/` are removed. An empty
number stays empty.

## Development

All project tooling runs in Docker. `requirements-dev.txt` pins the development
environment, so local runs and CI use the same tool versions:

```bash
# Build the development image
docker compose build sdk

# Tests with 100% line and branch coverage required
docker compose run --rm sdk pytest

# Lint and type-check
docker compose run --rm sdk ruff check src/ tests/ examples/
docker compose run --rm sdk mypy src/daktela

# Build and validate release artifacts
docker compose run --rm sdk python -m build
docker compose run --rm sdk twine check dist/*
```

## License

MIT License. See [LICENSE](LICENSE).
