"""Examples of advanced query building."""

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaFilter,
    DaktelaQuery,
    DaktelaSort,
)


def main() -> None:
    client = DaktelaClient(
        DaktelaConfig(
            url="my.daktela.com",
            access_token="your-access-token",
        )
    )

    # Multiple filters (AND)
    query = (
        DaktelaQuery()
        .filter(DaktelaFilter.eq("stage", "OPEN"))
        .filter(DaktelaFilter.gte("priority", 5))
        .filter(DaktelaFilter.like("title", "urgent"))
    )
    response = client.get("tickets", query)
    print(f"High priority urgent open tickets: {response.total}")

    # OR filter
    query = DaktelaQuery().filter(
        DaktelaFilter.or_(
            DaktelaFilter.eq("stage", "OPEN"),
            DaktelaFilter.eq("stage", "PENDING"),
            DaktelaFilter.eq("stage", "IN_PROGRESS"),
        )
    )
    response = client.get("tickets", query)
    print(f"Active tickets (open, pending, or in progress): {response.total}")

    # Combining AND and OR
    query = (
        DaktelaQuery()
        .filter(DaktelaFilter.gte("priority", 8))  # AND
        .filter(
            DaktelaFilter.or_(
                DaktelaFilter.eq("stage", "OPEN"),
                DaktelaFilter.eq("stage", "PENDING"),
            )
        )
    )
    response = client.get("tickets", query)
    print(f"High priority active tickets: {response.total}")

    # IN filter for multiple values
    query = DaktelaQuery().filter(
        DaktelaFilter.in_("category", ["support", "billing", "technical"])
    )
    response = client.get("tickets", query)
    print(f"Support, billing, or technical tickets: {response.total}")

    # NOT IN filter
    query = DaktelaQuery().filter(
        DaktelaFilter.not_in("stage", ["CLOSED", "RESOLVED", "CANCELLED"])
    )
    response = client.get("tickets", query)
    print(f"Non-closed tickets: {response.total}")

    # Date range filtering
    query = (
        DaktelaQuery()
        .filter(DaktelaFilter.gte("created", "2024-01-01"))
        .filter(DaktelaFilter.lt("created", "2024-02-01"))
    )
    response = client.get("tickets", query)
    print(f"Tickets created in January 2024: {response.total}")

    # Multiple sorts
    query = DaktelaQuery().sorts(
        DaktelaSort.desc("priority"),
        DaktelaSort.asc("created"),
    )
    response = client.get("tickets", query)
    print("Tickets sorted by priority (high first), then by creation date")

    # Select specific fields only
    query = DaktelaQuery().fields("name", "title", "stage", "priority")
    response = client.get("tickets", query)
    for ticket in response:
        # Only these fields will be populated
        print(f"{ticket.get('name')}: {ticket.get('title')} [{ticket.get('stage')}]")

    # Complex query combining everything
    query = (
        DaktelaQuery()
        .fields("name", "title", "stage", "priority", "created", "owner")
        .filter(
            DaktelaFilter.or_(
                DaktelaFilter.eq("stage", "OPEN"),
                DaktelaFilter.eq("stage", "IN_PROGRESS"),
            )
        )
        .filter(DaktelaFilter.gte("priority", 5))
        .filter(DaktelaFilter.gte("created", "2024-01-01"))
        .sorts(
            DaktelaSort.desc("priority"),
            DaktelaSort.desc("created"),
        )
        .take(100)
        .skip(0)
    )
    response = client.get("tickets", query)
    print(f"\nComplex query results: {response.total} total, {len(response)} returned")

    client.close()


if __name__ == "__main__":
    main()
