# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-06

Fixes duplicate records from retried POST requests, silent truncation during
iteration, and access-token leaks.

### Behaviour changes

Existing callers should check these before upgrading:

- `POST` is no longer resent after a 5xx response, a timeout, or a dropped
  connection, because the server may already have created the record. It is
  still retried after HTTP 429 and when the connection never opened. To opt
  back in, pass
  `RetryConfig(retry_on_methods=("GET", "HEAD", "OPTIONS", "PUT", "DELETE", "POST"))`.
- `POST`, `PUT`, `PATCH`, and `DELETE` responses that report errors in the body
  raise `DaktelaValidationException`, even when the HTTP status is 2xx.
  Previously they returned normally with the errors in `response.errors`.
- With `stop_on_error=True` (the default), a page whose response reports errors
  raises `DaktelaException` instead of silently ending iteration. `pages()`
  yields that page before raising.
- With `stop_on_error=False`, reaching `max_error_pages` consecutive error
  responses raises the last error instead of silently ending iteration.
- `DaktelaFilter.in_()` and `not_in()` raise `ValueError` for an empty list.
  Previously the filter was sent without a value, which could match every
  record.
- A `PaginatedIterator` supports either item iteration or `pages()`. Mixing
  them raises `RuntimeError`.
- `RetryConfig(retry_on_methods=...)` raises `TypeError` for a bare string such
  as `"POST"`. Pass a tuple, for example `("POST",)`.

### Added

- `DaktelaForbiddenException` for HTTP 403 responses (subclass of
  `DaktelaException`, which 403 previously raised)
- `RetryConfig.retry_on_methods` to choose which HTTP methods may be resent

### Changed

- The default User-Agent is `DaktelaPythonSDK/1.2`
- The publish workflow runs tests on every supported Python version, adds type
  checking and linting, verifies that the release tag matches the package
  version, and limits the workflow token to read access

### Fixed

- POST requests could be sent up to four times after a server error or a
  timeout, which could create duplicate records
- Iteration stopped after the first page when the server returned fewer records
  than `page_size`. It now advances by the number of records received and uses
  the reported `total` to decide when to stop
- `repr(DaktelaConfig)` exposed the access token
- With `AuthMethod.QUERY`, the access token appeared in `httpx` request logs
- `get_one()` addressed the wrong object when its name ended in `.json`
- Skipped error pages are now recorded in `PaginatedIterator.last_error`

## [1.1.0] - 2026-08-19

### Changed

- Require Python 3.10 or newer
- Normalize API endpoints to canonical lower-camel `.json` paths
- Serialize filters using nested `logic` and `filters` groups
- Use the authenticated `whoim` resource for health checks
- Preserve explicitly configured HTTP URLs for local development
- Reject malformed successful JSON responses with `DaktelaProtocolException`
- Bound status, connection, timeout, and rate-limit retry loops
- Parse both numeric and HTTP-date `Retry-After` values
- Make paginated iteration total-aware and preserve an initial query offset
- Enforce 100% line and branch coverage in the release test suite

### Added

- `DaktelaClient.get_one()`, `get_relation()`, and `get_all()`
- Additional query parameters on every CRUD operation
- Page iteration and `count`, `is_empty`, `each`, `filter`, and `map` helpers
- Bounded failed-page skipping with `max_error_pages`
- Complete named filter operators, nested AND groups, and custom operators
- Correct `c_user` cookie authentication
- `DaktelaResponse.first_error` and `DaktelaResponse.is_empty`
- `normalize_phone_number()` utility
- Docker-based development and release workflow
- Package build validation in continuous integration

### Fixed

- `not_in()` now emits the API's `notin` operator
- A zero-second `Retry-After` value is honored
- Repeated HTTP 429 responses can no longer retry indefinitely
- Pagination no longer makes an unnecessary empty request when totals are known
- API errors can be skipped safely without creating an unbounded loop

## [1.0.0] - 2026-01-22

### Added

- Initial release of Daktela V6 Python SDK
- `DaktelaClient` with full CRUD operations (GET, POST, PUT, DELETE)
- `DaktelaConfig` for client configuration with URL normalization
- `DaktelaQuery` fluent query builder
- `DaktelaFilter` with support for all comparison and list operators
- `DaktelaSort` for ascending and descending sorts
- `DaktelaPagination` helper for pagination parameters
- `PaginatedIterator` for memory-efficient iteration through large datasets
- `DaktelaResponse` wrapper with convenient data access methods
- Exception hierarchy:
  - `DaktelaException` (base)
  - `DaktelaUnauthorizedException` (401)
  - `DaktelaNotFoundException` (404)
  - `DaktelaRateLimitException` (429)
  - `DaktelaValidationException` (400/422)
  - `DaktelaConnectionException`
  - `DaktelaTimeoutException`
- `RetryConfig` for automatic retry with exponential backoff
- `RateLimitConfig` for handling rate limits with Retry-After support
- `AuthMethod` enum for HEADER, QUERY, and COOKIE authentication
- Health check methods (`ping()`, `health_check()`)
- Full type hints (PEP 561 compatible)
- Comprehensive unit tests
- Usage examples
