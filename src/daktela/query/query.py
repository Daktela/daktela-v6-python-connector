"""Query builder for Daktela API requests."""

from typing import Any, Dict, List, Optional

from .filter import DaktelaFilter
from .pagination import DaktelaPagination
from .sort import DaktelaSort


class DaktelaQuery:
    """Fluent query builder for Daktela API requests.

    Combines fields, filters, sorts, and pagination into a single query.

    Example:
        >>> query = (DaktelaQuery()
        ...     .fields("name", "title", "category")
        ...     .filter(DaktelaFilter.eq("stage", "OPEN"))
        ...     .filter(DaktelaFilter.gte("created", "2024-01-01"))
        ...     .sort(DaktelaSort.desc("edited"))
        ...     .pagination(take=50, skip=0))
    """

    def __init__(self) -> None:
        """Initialize an empty query."""
        self._fields: List[str] = []
        self._filters: List[DaktelaFilter] = []
        self._sorts: List[DaktelaSort] = []
        self._take: Optional[int] = None
        self._skip: Optional[int] = None

    def fields(self, *field_names: str) -> "DaktelaQuery":
        """Add fields to retrieve.

        Args:
            *field_names: Field names to include in the response

        Returns:
            Self for method chaining
        """
        self._fields.extend(field_names)
        return self

    def filter(self, f: DaktelaFilter) -> "DaktelaQuery":
        """Add a filter to the query.

        Args:
            f: The filter to add

        Returns:
            Self for method chaining
        """
        self._filters.append(f)
        return self

    def filters(self, *filters: DaktelaFilter) -> "DaktelaQuery":
        """Add multiple filters to the query.

        Args:
            *filters: The filters to add

        Returns:
            Self for method chaining
        """
        self._filters.extend(filters)
        return self

    def sort(self, s: DaktelaSort) -> "DaktelaQuery":
        """Add a sort to the query.

        Args:
            s: The sort to add

        Returns:
            Self for method chaining
        """
        self._sorts.append(s)
        return self

    def sorts(self, *sorts: DaktelaSort) -> "DaktelaQuery":
        """Add multiple sorts to the query.

        Args:
            *sorts: The sorts to add

        Returns:
            Self for method chaining
        """
        self._sorts.extend(sorts)
        return self

    def pagination(
        self,
        take: Optional[int] = None,
        skip: Optional[int] = None,
        pagination: Optional[DaktelaPagination] = None,
    ) -> "DaktelaQuery":
        """Set pagination parameters.

        Can be called with take/skip values or a DaktelaPagination object.

        Args:
            take: Number of records to retrieve
            skip: Number of records to skip
            pagination: Pagination object (overrides take/skip)

        Returns:
            Self for method chaining
        """
        if pagination is not None:
            self._take = pagination.take
            self._skip = pagination.skip
        else:
            self._take = take
            self._skip = skip
        return self

    def take(self, value: int) -> "DaktelaQuery":
        """Set the take (limit) value.

        Args:
            value: Number of records to retrieve

        Returns:
            Self for method chaining
        """
        self._take = value
        return self

    def skip(self, value: int) -> "DaktelaQuery":
        """Set the skip (offset) value.

        Args:
            value: Number of records to skip

        Returns:
            Self for method chaining
        """
        self._skip = value
        return self

    def get_fields(self) -> List[str]:
        """Get the list of fields."""
        return list(self._fields)

    def get_filters(self) -> List[DaktelaFilter]:
        """Get the list of filters."""
        return list(self._filters)

    def get_sorts(self) -> List[DaktelaSort]:
        """Get the list of sorts."""
        return list(self._sorts)

    def get_take(self) -> Optional[int]:
        """Get the take value."""
        return self._take

    def get_skip(self) -> Optional[int]:
        """Get the skip value."""
        return self._skip

    def to_params(self) -> Dict[str, Any]:
        """Convert the query to URL parameters dictionary.

        Returns:
            Dictionary suitable for use as query parameters
        """
        params: Dict[str, Any] = {}

        if self._fields:
            params["fields"] = self._fields

        if self._filters:
            params["filter"] = [f.to_dict() for f in self._filters]

        if self._sorts:
            params["sort"] = [s.to_dict() for s in self._sorts]

        if self._take is not None:
            params["take"] = self._take

        if self._skip is not None:
            params["skip"] = self._skip

        return params

    def copy(self) -> "DaktelaQuery":
        """Create a copy of this query.

        Returns:
            A new DaktelaQuery instance with the same parameters
        """
        query = DaktelaQuery()
        query._fields = list(self._fields)
        query._filters = list(self._filters)
        query._sorts = list(self._sorts)
        query._take = self._take
        query._skip = self._skip
        return query

    def __repr__(self) -> str:
        parts = []
        if self._fields:
            parts.append(f"fields={self._fields}")
        if self._filters:
            parts.append(f"filters={len(self._filters)}")
        if self._sorts:
            parts.append(f"sorts={len(self._sorts)}")
        if self._take is not None:
            parts.append(f"take={self._take}")
        if self._skip is not None:
            parts.append(f"skip={self._skip}")
        return f"DaktelaQuery({', '.join(parts)})"
