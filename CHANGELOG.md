# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-22

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
