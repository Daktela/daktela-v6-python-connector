# Daktela V6 Python SDK

A typed Python client for the Daktela V6 REST API. It supports CRUD operations,
nested queries, all authentication modes, bounded retries, rate-limit handling,
health checks, and memory-efficient pagination.

## Requirements

- Python 3.10 or newer
- A Daktela V6 instance URL
- An API access token with permissions for the resources you use

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

# Read one resource; the identifier is safely URL-encoded
ticket = client.get_one("tickets", "ticket-123").as_dict()

# Read a relation
activities = client.get_relation(
    "tickets",
    "ticket-123",
    "activities",
    DaktelaQuery().take(100),
)

# Create, update, and delete
created = client.post("tickets", {"title": "New request"})
updated = client.put("tickets/ticket-123", {"stage": "RESOLVED"})
deleted = client.delete("tickets/ticket-123")
```

Every operation accepts additional API-specific query parameters:

```python
client.post("tickets", {"title": "New request"}, {"custom": "value"})
client.delete("tickets/ticket-123", {"audit": True})

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
DaktelaFilter.neq("stage", "CLOSED")
DaktelaFilter.gt("priority", 5)
DaktelaFilter.gte("priority", 5)
DaktelaFilter.lt("priority", 10)
DaktelaFilter.lte("priority", 10)
DaktelaFilter.like("title", "urgent")
DaktelaFilter.not_like("title", "spam")
DaktelaFilter.begins("name", "ticket-")
DaktelaFilter.not_begins("name", "test-")
DaktelaFilter.ends("email", "@example.com")
DaktelaFilter.not_ends("email", "@invalid.example")
DaktelaFilter.in_("stage", ["OPEN", "PENDING"])
DaktelaFilter.not_in("stage", ["CLOSED", "ARCHIVED"])
DaktelaFilter.is_null("owner")
DaktelaFilter.is_not_null("owner")
```

Filters added directly to a query are combined with AND. Logical groups can be
nested:

```python
query = (
    DaktelaQuery()
    .filter(DaktelaFilter.gte("priority", 5))
    .filter(
        DaktelaFilter.or_(
            DaktelaFilter.eq("stage", "OPEN"),
            DaktelaFilter.eq("stage", "PENDING"),
        )
    )
)
```

Use `custom()` for API operators that are not represented by a named helper:

```python
filter_ = DaktelaFilter.custom(
    "title",
    "futureOperator",
    "value",
    ignore_case=True,
)
```

## Pagination

`iterate()` requests pages only as they are needed:

```python
iterator = client.iterate(
    "tickets",
    DaktelaQuery().filter(DaktelaFilter.eq("stage", "OPEN")),
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

By default, request exceptions propagate and API error pages stop iteration.
Set `stop_on_error=False` to skip failed pages. `max_error_pages` bounds
consecutive skipped pages so a persistent failure cannot loop forever.

## Authentication and client configuration

```python
from daktela import AuthMethod, DaktelaConfig

config = DaktelaConfig(
    url="https://my.daktela.com/api/v6/",
    access_token="your-access-token",
    auth_method=AuthMethod.HEADER,
    timeout=30.0,
    user_agent="MyIntegration/1.0",
    verify_ssl=True,
)
```

Authentication modes:

- `AuthMethod.HEADER` sends `X-AUTH-TOKEN` and is the recommended default.
- `AuthMethod.QUERY` sends the `accessToken` query parameter.
- `AuthMethod.COOKIE` sends the `c_user` cookie.

Hostnames without a scheme default to HTTPS. Explicit HTTP URLs are preserved
for local development. Never disable certificate verification in production.

An existing `httpx.Client` can be supplied for proxies, custom transports, or
application-managed connection pools:

```python
import httpx

http_client = httpx.Client(proxy="http://proxy.example:8080")
client = DaktelaClient(config, http_client=http_client)
```

The SDK does not close an injected client; its owner remains responsible for it.

## Retries and rate limits

Transient status codes, connection failures, and timeouts use exponential
backoff:

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

The SDK raises specific exceptions for common failures:

```python
from daktela import (
    DaktelaConnectionException,
    DaktelaException,
    DaktelaNotFoundException,
    DaktelaProtocolException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)

try:
    ticket = client.get_one("tickets", "missing")
except DaktelaNotFoundException:
    print("Ticket not found")
except DaktelaRateLimitException as error:
    print("Retry after", error.retry_after)
except DaktelaProtocolException as error:
    print("Unexpected API response", error)
except DaktelaException as error:
    print(error.status_code, error.errors)
```

## Health checks

```python
if client.ping():
    print("API is healthy")

health = client.health_check()
print(health["healthy"], health["latency_ms"])
```

## Phone-number normalization

```python
from daktela import normalize_phone_number

normalize_phone_number("773 794 604")
# "00420773794604"

normalize_phone_number("773 794 604", plus_sign=True)
# "+420773794604"
```

## Development

All project tooling runs in Docker:

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

Live integration tests require `DAKTELA_URL` and `DAKTELA_ACCESS_TOKEN`; without
them they are skipped.

## License

MIT License. See [LICENSE](LICENSE).
