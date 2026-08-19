"""Basic usage examples for Daktela SDK."""

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaFilter,
    DaktelaPagination,
    DaktelaQuery,
    DaktelaSort,
)


def main() -> None:
    # Initialize the client
    client = DaktelaClient(
        DaktelaConfig(
            url="my.daktela.com",
            access_token="your-access-token",
        )
    )

    # Simple GET request
    response = client.get("tickets")
    print(f"Found {response.total} tickets")

    # GET with query parameters
    query = (
        DaktelaQuery()
        .fields("name", "title", "stage")
        .filter(DaktelaFilter.eq("stage", "OPEN"))
        .sort(DaktelaSort.desc("created"))
        .take(50)
    )
    response = client.get("tickets", query)

    for ticket in response:
        print(f"Ticket: {ticket.get('name')} - {ticket.get('title')}")

    # Get a single resource
    response = client.get_one("tickets", "123")
    ticket = response.as_dict()
    print(f"Single ticket: {ticket}")

    # Create a new resource
    response = client.post(
        "tickets",
        {
            "title": "New Support Request",
            "description": "Customer needs help",
            "category": "support",
        },
    )
    if response.is_success:
        print(f"Created ticket: {response.get('name')}")

    # Update a resource
    response = client.put(
        "tickets/123",
        {
            "title": "Updated Title",
            "stage": "RESOLVED",
        },
    )

    # Delete a resource, with an optional API-specific query parameter
    response = client.delete("tickets/123", {"audit": True})

    # Using pagination helper
    pagination = DaktelaPagination.page(page_number=2, page_size=25)
    query = DaktelaQuery().pagination(pagination=pagination)
    response = client.get("tickets", query)

    # Check API health
    if client.ping():
        print("API is healthy!")

    health = client.health_check()
    print(f"API latency: {health['latency_ms']}ms")

    # Always close the client when done
    client.close()


if __name__ == "__main__":
    main()
