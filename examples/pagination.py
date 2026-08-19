"""Examples of efficient pagination through large datasets."""

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaFilter,
    DaktelaQuery,
)


def main() -> None:
    client = DaktelaClient(
        DaktelaConfig(
            url="my.daktela.com",
            access_token="your-access-token",
        )
    )

    # Basic iteration - fetches pages automatically
    query = DaktelaQuery().filter(DaktelaFilter.eq("stage", "OPEN"))

    print("Iterating through all open tickets:")
    for ticket in client.iterate("tickets", query):
        print(f"  - {ticket.get('name')}: {ticket.get('title')}")

    # Limit the number of results
    print("\nFirst 100 tickets:")
    for ticket in client.iterate("tickets", query, max_items=100):
        print(f"  - {ticket.get('name')}")

    # Custom page size for memory efficiency
    print("\nIterating with small page size:")
    for ticket in client.iterate("tickets", query, page_size=25):
        print(f"  - {ticket.get('name')}")

    # Get just the first item
    iterator = client.iterate("tickets", query)
    first_ticket = iterator.first()
    if first_ticket:
        print(f"\nFirst ticket: {first_ticket.get('name')}")

    # Collect all results into a list (be careful with large datasets!)
    all_tickets = client.iterate("tickets", query, max_items=10).collect()
    print(f"\nCollected {len(all_tickets)} tickets")

    # Access iteration metadata
    iterator = client.iterate("tickets", query, page_size=50, max_items=200)
    for ticket in iterator:
        pass  # Process tickets

    print("\nIteration stats:")
    print(f"  Total items in dataset: {iterator.total}")
    print(f"  Items processed: {iterator.items_yielded}")

    # Iterate page responses when totals and status are needed per request
    for page in client.iterate("tickets", query, page_size=50).pages():
        print(f"Page status: {page.status_code}, total: {page.total}")

    client.close()


if __name__ == "__main__":
    main()
