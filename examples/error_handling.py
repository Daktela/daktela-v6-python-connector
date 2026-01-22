"""Examples of error handling with Daktela SDK."""

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaConnectionException,
    DaktelaException,
    DaktelaNotFoundException,
    DaktelaRateLimitException,
    DaktelaTimeoutException,
    DaktelaUnauthorizedException,
    DaktelaValidationException,
)


def main() -> None:
    client = DaktelaClient(
        DaktelaConfig(
            url="my.daktela.com",
            access_token="your-access-token",
            timeout=30.0,
        )
    )

    # Handling specific exceptions
    try:
        response = client.get("tickets/non-existent-id")
    except DaktelaNotFoundException as e:
        print(f"Ticket not found: {e.message}")
        print(f"API errors: {e.errors}")

    try:
        response = client.get("tickets")
    except DaktelaUnauthorizedException as e:
        print(f"Authentication failed: {e.message}")
        print("Check your access token")

    try:
        # This might trigger rate limiting with many requests
        for i in range(1000):
            client.get("tickets")
    except DaktelaRateLimitException as e:
        print(f"Rate limited! Wait {e.retry_after} seconds before retrying")

    try:
        response = client.post("tickets", {"invalid": "data"})
    except DaktelaValidationException as e:
        print(f"Validation error: {e.message}")
        print(f"Field errors: {e.errors}")

    try:
        response = client.get("tickets")
    except DaktelaTimeoutException as e:
        print(f"Request timed out: {e.message}")

    try:
        response = client.get("tickets")
    except DaktelaConnectionException as e:
        print(f"Connection failed: {e.message}")

    # Catching all Daktela exceptions
    try:
        response = client.get("tickets")
    except DaktelaException as e:
        print(f"API error [{e.status_code}]: {e.message}")
        if e.errors:
            for error in e.errors:
                print(f"  - {error}")

    # Using response status checks
    response = client.get("tickets")
    if response.is_success:
        print(f"Success! Got {len(response)} tickets")
    elif response.has_errors:
        print(f"Errors: {response.errors}")

    # Safe access to response data
    response = client.get("tickets/123")
    name = response.get("name", "Unknown")
    title = response.get("title", "No title")
    print(f"Ticket: {name} - {title}")

    client.close()


if __name__ == "__main__":
    main()
