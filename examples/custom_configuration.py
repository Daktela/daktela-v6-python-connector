"""Examples of custom client configuration."""

import logging

from daktela import (
    AuthMethod,
    DaktelaClient,
    DaktelaConfig,
    RateLimitConfig,
    RetryConfig,
)


def main() -> None:
    # Basic configuration
    config = DaktelaConfig(
        url="my.daktela.com",
        access_token="your-access-token",
    )

    # Full configuration with all options
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("daktela")

    config = DaktelaConfig(
        url="my.daktela.com",
        access_token="your-access-token",
        auth_method=AuthMethod.HEADER,  # or QUERY, COOKIE
        timeout=60.0,  # Request timeout in seconds
        user_agent="MyApp/1.0",
        verify_ssl=True,  # Set False for self-signed certs (not recommended)
        logger=logger,  # Enable debug logging
    )

    # Custom retry configuration
    retry_config = RetryConfig(
        max_retries=5,  # More retries
        initial_delay=0.5,  # Start with shorter delay
        max_delay=30.0,  # Cap at 30 seconds
        exponential_base=2.0,  # Double delay each retry
        retry_on_status=(429, 500, 502, 503, 504),  # Which status codes to retry
    )

    # Disable retries entirely
    no_retry = RetryConfig.disabled()

    # Aggressive retry settings
    aggressive_retry = RetryConfig.aggressive()

    # Custom rate limit handling
    rate_limit_config = RateLimitConfig(
        enabled=True,
        max_wait=120.0,  # Maximum time to wait for rate limit reset
        default_retry_after=60.0,  # Default wait if no Retry-After header
    )

    # Disable rate limit handling (will raise exception immediately)
    no_rate_limit = RateLimitConfig.disabled()

    # Patient rate limit handling (willing to wait longer)
    patient_rate_limit = RateLimitConfig.patient()

    # Create client with custom configuration
    client = DaktelaClient(
        config=config,
        retry_config=retry_config,
        rate_limit_config=rate_limit_config,
    )

    # Using the client as a context manager (auto-closes)
    with DaktelaClient(config) as client:
        response = client.get("tickets")
        print(f"Got {len(response)} tickets")
    # Client is automatically closed here

    # URL normalization examples
    # All of these produce the same base URL
    configs = [
        DaktelaConfig(url="my.daktela.com", access_token="token"),
        DaktelaConfig(url="https://my.daktela.com", access_token="token"),
        DaktelaConfig(url="http://my.daktela.com/", access_token="token"),
        DaktelaConfig(url="https://my.daktela.com/api/v6/", access_token="token"),
    ]

    for c in configs:
        print(f"Normalized URL: {c.url}")
        print(f"Base URL: {c.base_url}")

    # Authentication methods
    # Header (default, recommended)
    header_auth = DaktelaConfig(
        url="my.daktela.com",
        access_token="token",
        auth_method=AuthMethod.HEADER,  # Sends X-AUTH-TOKEN header
    )

    # Query parameter
    query_auth = DaktelaConfig(
        url="my.daktela.com",
        access_token="token",
        auth_method=AuthMethod.QUERY,  # Sends accessToken query param
    )

    # Cookie
    cookie_auth = DaktelaConfig(
        url="my.daktela.com",
        access_token="token",
        auth_method=AuthMethod.COOKIE,  # Sends accessToken cookie
    )


if __name__ == "__main__":
    main()
