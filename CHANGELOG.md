# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
