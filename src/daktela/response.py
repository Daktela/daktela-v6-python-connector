"""Response wrapper for Daktela API responses."""

from typing import Any, Dict, Iterator, List, Mapping, Optional, TypeVar

T = TypeVar("T")


class DaktelaResponse:
    """Wrapper for Daktela API responses.

    Provides convenient access to response data with type helpers.

    Attributes:
        status_code: HTTP status code
        data: Response data (single object or list)
        total: Total count of records (for paginated responses)
        errors: List of error details if present
    """

    def __init__(
        self,
        status_code: int,
        data: Any = None,
        total: Optional[int] = None,
        errors: Optional[List[Any]] = None,
    ) -> None:
        self._status_code = status_code
        self._data = data
        self._total = total
        self._errors = errors or []

    @property
    def status_code(self) -> int:
        """HTTP status code of the response."""
        return self._status_code

    @property
    def data(self) -> Any:
        """Response data.

        Can be a single object (dict), a list of objects, or None.
        """
        return self._data

    @property
    def total(self) -> Optional[int]:
        """Total count of records for paginated responses.

        Returns None if the response doesn't include pagination info.
        """
        return self._total

    @property
    def errors(self) -> List[Any]:
        """List of error details from the response."""
        return self._errors

    @property
    def is_success(self) -> bool:
        """Check if the response indicates success (2xx status code)."""
        return 200 <= self._status_code < 300

    @property
    def has_errors(self) -> bool:
        """Check if the response contains any errors."""
        return len(self._errors) > 0

    @property
    def first_error(self) -> Any:
        """Return the first API error, or ``None`` when there are no errors."""
        return self._errors[0] if self._errors else None

    @property
    def is_empty(self) -> bool:
        """Return whether the response contains no data."""
        if self._data is None:
            return True
        if isinstance(self._data, (list, dict, str)):
            return len(self._data) == 0
        return False

    def as_list(self) -> List[Any]:
        """Get the response data as a list.

        Returns:
            List of values. If data is a single value, wraps it in a list.
            If data is None, returns an empty list.
        """
        if self._data is None:
            return []
        if isinstance(self._data, list):
            return self._data
        return [self._data]

    def as_dict(self) -> Dict[str, Any]:
        """Get the response data as a dictionary.

        Returns:
            Dictionary. If data is a list, returns the first element.
            If data is None or empty list, returns an empty dict.
        """
        if isinstance(self._data, Mapping):
            return dict(self._data)
        if (
            isinstance(self._data, list)
            and self._data
            and isinstance(self._data[0], Mapping)
        ):
            return dict(self._data[0])
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the response data by key.

        Args:
            key: The key to look up
            default: Default value if key is not found

        Returns:
            The value for the key, or default if not found
        """
        data = self.as_dict()
        return data.get(key, default)

    def __iter__(self) -> Iterator[Any]:
        """Iterate over response data items."""
        return iter(self.as_list())

    def __len__(self) -> int:
        """Return the number of items in the response data."""
        return len(self.as_list())

    def __bool__(self) -> bool:
        """Return True if response is successful and has data."""
        return self.is_success and not self.is_empty

    def __repr__(self) -> str:
        return (
            f"DaktelaResponse(status_code={self._status_code}, "
            f"items={len(self)}, total={self._total})"
        )
