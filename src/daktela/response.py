"""Response wrapper for Daktela API responses."""

from typing import Any, Dict, Iterator, List, Optional, TypeVar

from daktela.exceptions import DaktelaFileResponseException

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

    def as_list(self) -> List[Dict[str, Any]]:
        """Get the response data as a list.

        Returns:
            List of dictionaries. If data is a single object, wraps it in a list.
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
        if self._data is None:
            return {}
        if isinstance(self._data, list):
            return self._data[0] if self._data else {}
        return self._data

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

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over response data items."""
        return iter(self.as_list())

    def __len__(self) -> int:
        """Return the number of items in the response data."""
        return len(self.as_list())

    def __bool__(self) -> bool:
        """Return True if response is successful and has data."""
        return self.is_success and self._data is not None

    def __repr__(self) -> str:
        return (
            f"DaktelaResponse(status_code={self._status_code}, "
            f"items={len(self)}, total={self._total})"
        )

class DaktelaFileResponse(DaktelaResponse):
    """Wrapper for Daktela API file responses.

    Provides convenient access to response data with type helpers.

    Attributes:
        status_code: HTTP status code
        data: Response data (file content as bytes)
        filename: The given filename of the response header
        errors: List of error details if present
    """

    def __init__(
        self,
        status_code: int,
        data: Any = None,
        filename: str = '',
        errors: Optional[List[Any]] = None,
    ) -> None:
        self._status_code = status_code
        self._data = data
        self._total = None
        self._errors = errors or []
        self._filename = filename

    @property
    def filename(self) -> Any:
        """Filename.

        The given filename of the response header.
        """
        return self._filename

    @property
    def data(self) -> Any:
        """Response data.

        The file content as bytes.
        """
        return self._data

    @property
    def total(self) -> Optional[int]:
        """NOT AVAILABLE IN FILE RESPONSE"""

        raise DaktelaFileResponseException('daktela.response.DaktelaFileResponse.total')

    def as_list(self) -> List[Dict[str, Any]]:
        """NOT AVAILABLE IN FILE RESPONSE"""

        raise DaktelaFileResponseException('daktela.response.DaktelaFileResponse.as_list()')

    def as_dict(self) -> Dict[str, Any]:
        """NOT AVAILABLE IN FILE RESPONSE"""

        raise DaktelaFileResponseException('daktela.response.DaktelaFileResponse.as_dict()')

    def get(self, key: str, default: Any = None) -> Any:
        """NOT AVAILABLE IN FILE RESPONSE"""

        raise DaktelaFileResponseException('daktela.response.DaktelaFileResponse.get()')

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """NOT AVAILABLE IN FILE RESPONSE"""

        raise DaktelaFileResponseException('daktela.response.DaktelaFileResponse.__iter__()')

    def __len__(self) -> int:
        """Return the file size in bytes."""
        if self._data is None:
            return 0

        return self._data.__len__()

    def __repr__(self) -> str:
        return (
            f"DaktelaFileResponse(status_code={self._status_code}, "
            f"filename={self._filename}, len={len(self)})"
        )
