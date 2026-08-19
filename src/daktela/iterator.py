"""Memory-efficient paginated iteration for the Daktela API."""

from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional, TypeVar

from .exceptions import DaktelaException
from .query import DaktelaQuery
from .response import DaktelaResponse

if TYPE_CHECKING:
    from .client import DaktelaClient

T = TypeVar("T")


class PaginatedIterator:
    """A stateful iterator that loads API records one page at a time."""

    def __init__(
        self,
        client: "DaktelaClient",
        endpoint: str,
        query: Optional[DaktelaQuery] = None,
        page_size: int = 100,
        max_items: Optional[int] = None,
        stop_on_error: bool = True,
        max_error_pages: int = 3,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be greater than zero")
        if max_items is not None and max_items < 0:
            raise ValueError("max_items must not be negative")
        if max_error_pages <= 0:
            raise ValueError("max_error_pages must be greater than zero")

        self._client = client
        self._endpoint = endpoint
        self._base_query = query.copy() if query else DaktelaQuery()
        self._page_size = page_size
        self._max_items = max_items
        self._stop_on_error = stop_on_error
        self._max_error_pages = max_error_pages
        self._initial_offset = self._base_query.get_skip() or 0

        self._next_offset = self._initial_offset
        self._items_yielded = 0
        self._current_items: List[Dict[str, Any]] = []
        self._current_index = 0
        self._total: Optional[int] = None
        self._exhausted = max_items == 0
        self._last_response: Optional[DaktelaResponse] = None
        self._last_error: Optional[DaktelaException] = None
        self._consecutive_errors = 0

    @property
    def total(self) -> Optional[int]:
        """Return the most recently reported total record count."""
        return self._total

    @property
    def items_yielded(self) -> int:
        """Return the number of records yielded by item iteration."""
        return self._items_yielded

    @property
    def last_response(self) -> Optional[DaktelaResponse]:
        """Return the most recent successful HTTP response."""
        return self._last_response

    @property
    def last_error(self) -> Optional[DaktelaException]:
        """Return the most recent skipped request exception."""
        return self._last_error

    def __iter__(self) -> "PaginatedIterator":
        return self

    def __next__(self) -> Dict[str, Any]:
        if self._max_items is not None and self._items_yielded >= self._max_items:
            raise StopIteration

        if self._current_index >= len(self._current_items):
            self._load_next_items()
        if self._current_index >= len(self._current_items):
            raise StopIteration

        item = self._current_items[self._current_index]
        self._current_index += 1
        self._items_yielded += 1
        return item

    def _remaining_page_size(self, items_yielded: int) -> int:
        if self._max_items is None:
            return self._page_size
        return min(self._page_size, self._max_items - items_yielded)

    def _request_page(self, offset: int, take: int) -> DaktelaResponse:
        query = self._base_query.copy().take(take).skip(offset)
        return self._client.get(self._endpoint, query)

    def _load_next_items(self) -> None:
        self._current_items = []
        self._current_index = 0

        while not self._exhausted:
            take = self._remaining_page_size(self._items_yielded)
            offset = self._next_offset

            try:
                response = self._request_page(offset, take)
            except DaktelaException as exc:
                self._last_error = exc
                if self._stop_on_error:
                    raise
                self._consecutive_errors += 1
                self._next_offset += take
                if self._consecutive_errors >= self._max_error_pages:
                    self._exhausted = True
                    raise
                continue

            self._last_response = response
            if response.total is not None:
                self._total = response.total

            if response.has_errors:
                if self._stop_on_error:
                    self._exhausted = True
                    return
                self._consecutive_errors += 1
                self._next_offset += take
                if self._consecutive_errors >= self._max_error_pages:
                    self._exhausted = True
                    return
                continue

            self._consecutive_errors = 0
            items = response.as_list()
            self._current_items = items
            self._next_offset += take

            if not items:
                self._exhausted = True
            elif len(items) < take:
                self._exhausted = True
            elif self._total is not None and offset + len(items) >= self._total:
                self._exhausted = True
            elif (
                self._max_items is not None
                and self._items_yielded + len(items) >= self._max_items
            ):
                self._exhausted = True
            return

    def pages(self) -> Iterator[DaktelaResponse]:
        """Yield page responses, including response metadata and API errors."""
        offset = self._initial_offset
        item_count = 0
        consecutive_errors = 0

        while self._max_items is None or item_count < self._max_items:
            take = self._remaining_page_size(item_count)
            try:
                response = self._request_page(offset, take)
            except DaktelaException as exc:
                self._last_error = exc
                if self._stop_on_error:
                    raise
                consecutive_errors += 1
                offset += take
                if consecutive_errors >= self._max_error_pages:
                    raise
                continue

            self._last_response = response
            if response.total is not None:
                self._total = response.total
            yield response

            if response.has_errors:
                if self._stop_on_error:
                    return
                consecutive_errors += 1
                offset += take
                if consecutive_errors >= self._max_error_pages:
                    return
                continue

            consecutive_errors = 0
            items = response.as_list()
            item_count += len(items)
            if not items or len(items) < take:
                return
            if self._total is not None and offset + len(items) >= self._total:
                return
            offset += take

    def collect(self) -> List[Dict[str, Any]]:
        """Collect all remaining records into a list."""
        return list(self)

    def first(self) -> Optional[Dict[str, Any]]:
        """Return and consume the next record, or ``None`` when empty."""
        return next(self, None)

    def count(self) -> int:
        """Consume and count all remaining records."""
        return sum(1 for _ in self)

    def is_empty(self) -> bool:
        """Return whether no records remain, consuming one record if present."""
        return self.first() is None

    def each(self, callback: Callable[[Dict[str, Any], int], Any]) -> None:
        """Call ``callback(item, index)`` for every remaining record."""
        for index, item in enumerate(self):
            callback(item, index)

    def filter(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
    ) -> Iterator[Dict[str, Any]]:
        """Yield remaining records accepted by ``predicate``."""
        return (item for item in self if predicate(item))

    def map(self, transform: Callable[[Dict[str, Any]], T]) -> Iterator[T]:
        """Yield transformed values for all remaining records."""
        return (transform(item) for item in self)
