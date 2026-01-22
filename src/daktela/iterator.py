"""Memory-efficient paginated iterator for Daktela API."""

from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

from .query import DaktelaQuery
from .response import DaktelaResponse

if TYPE_CHECKING:
    from .client import DaktelaClient


class PaginatedIterator:
    """Memory-efficient iterator for paginating through large datasets.

    Fetches data in pages and yields individual items.
    Supports early termination and maximum item limits.

    Example:
        >>> for ticket in client.iterate("tickets", query):
        ...     print(ticket["name"])
    """

    def __init__(
        self,
        client: "DaktelaClient",
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
        page_size: int = 100,
        max_items: Optional[int] = None,
        stop_on_error: bool = True,
    ) -> None:
        """Initialize the paginated iterator.

        Args:
            client: DaktelaClient instance
            endpoint: API endpoint to iterate
            query: Base query (will be cloned and modified for pagination)
            page_size: Number of items per page
            max_items: Maximum items to return (None for unlimited)
            stop_on_error: Whether to stop iteration on first error
        """
        self._client = client
        self._endpoint = endpoint
        self._base_query = query.copy() if query else DaktelaQuery()
        self._page_size = page_size
        self._max_items = max_items
        self._stop_on_error = stop_on_error

        self._current_page: int = 0
        self._items_yielded: int = 0
        self._current_items: List[Dict[str, Any]] = []
        self._current_index: int = 0
        self._total: Optional[int] = None
        self._exhausted: bool = False
        self._last_response: Optional[DaktelaResponse] = None

    @property
    def total(self) -> Optional[int]:
        """Get the total count of items (if known from API response)."""
        return self._total

    @property
    def items_yielded(self) -> int:
        """Get the number of items yielded so far."""
        return self._items_yielded

    @property
    def last_response(self) -> Optional[DaktelaResponse]:
        """Get the last API response."""
        return self._last_response

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Return the iterator."""
        return self

    def __next__(self) -> Dict[str, Any]:
        """Get the next item.

        Returns:
            Next item from the dataset

        Raises:
            StopIteration: When no more items are available
        """
        if self._max_items is not None and self._items_yielded >= self._max_items:
            raise StopIteration

        if self._current_index >= len(self._current_items):
            if self._exhausted:
                raise StopIteration
            self._fetch_next_page()
            if not self._current_items:
                raise StopIteration

        item = self._current_items[self._current_index]
        self._current_index += 1
        self._items_yielded += 1
        return item

    def _fetch_next_page(self) -> None:
        """Fetch the next page of results."""
        skip = self._current_page * self._page_size

        query = self._base_query.copy()
        query.take(self._page_size).skip(skip)

        response = self._client.get(self._endpoint, query)
        self._last_response = response

        if response.has_errors and self._stop_on_error:
            self._exhausted = True
            self._current_items = []
            return

        self._current_items = response.as_list()
        self._current_index = 0
        self._current_page += 1

        if response.total is not None:
            self._total = response.total

        if len(self._current_items) < self._page_size:
            self._exhausted = True

    def collect(self) -> List[Dict[str, Any]]:
        """Collect all remaining items into a list.

        Warning: This loads all items into memory.

        Returns:
            List of all remaining items
        """
        return list(self)

    def first(self) -> Optional[Dict[str, Any]]:
        """Get the first item without iterating through all results.

        Returns:
            First item or None if no items
        """
        try:
            return next(iter(self))
        except StopIteration:
            return None
