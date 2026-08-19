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

    # Custom rate limit handling
    rate_limit_config = RateLimitConfig(
        enabled=True,
        max_retries=3,
        max_wait=120.0,  # Maximum time to wait for rate limit reset
        default_retry_after=60.0,  # Default wait if no Retry-After header
    )

    # Create client with custom configuration
    configured_client = DaktelaClient(
        config=config,
        retry_config=retry_config,
        rate_limit_config=rate_limit_config,
    )
    configured_client.close()

    # Using the client as a context manager (auto-closes)
    with DaktelaClient(config) as client:
        response = client.get("tickets")
        print(f"Got {len(response)} tickets")
    # Client is automatically closed here

    # URL normalization examples
    # HTTPS is the default; an explicit HTTP scheme is preserved
    configs = [
        DaktelaConfig(url="my.daktela.com", access_token="token"),
        DaktelaConfig(url="https://my.daktela.com", access_token="token"),
        DaktelaConfig(url="http://my.daktela.com/", access_token="token"),
        DaktelaConfig(url="https://my.daktela.com/api/v6/", access_token="token"),
    ]

    for normalized_config in configs:
        print(f"Normalized URL: {normalized_config.url}")
        print(f"Base URL: {normalized_config.base_url}")

    # Authentication methods
    authentication_configs = [
        DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            auth_method=AuthMethod.HEADER,  # Sends X-AUTH-TOKEN header
        ),
        DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            auth_method=AuthMethod.QUERY,  # Sends accessToken query param
        ),
        DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            auth_method=AuthMethod.COOKIE,  # Sends c_user cookie
        ),
    ]
    for authentication_config in authentication_configs:
        print(f"Authentication method: {authentication_config.auth_method.value}")


if __name__ == "__main__":
    main()
