"""Query builder for Daktela API requests."""

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional

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
        self._additional_params: Dict[str, Any] = {}

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
            if take is not None:
                self.take(take)
            else:
                self._take = None
            if skip is not None:
                self.skip(skip)
            else:
                self._skip = None
        return self

    def take(self, value: int) -> "DaktelaQuery":
        """Set the take (limit) value.

        Args:
            value: Number of records to retrieve

        Returns:
            Self for method chaining
        """
        if value < 0:
            raise ValueError("take must not be negative")
        self._take = value
        return self

    def skip(self, value: int) -> "DaktelaQuery":
        """Set the skip (offset) value.

        Args:
            value: Number of records to skip

        Returns:
            Self for method chaining
        """
        if value < 0:
            raise ValueError("skip must not be negative")
        self._skip = value
        return self

    def param(self, key: str, value: Any) -> "DaktelaQuery":
        """Add an API-specific query parameter.

        Standard fields, filters, sorts, and pagination values take precedence
        over additional parameters with the same key.
        """
        if not key:
            raise ValueError("query parameter key must not be empty")
        self._additional_params[key] = value
        return self

    def params(self, values: Mapping[str, Any]) -> "DaktelaQuery":
        """Add multiple API-specific query parameters."""
        for key, value in values.items():
            self.param(key, value)
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

    def get_params(self) -> Dict[str, Any]:
        """Get a copy of the API-specific query parameters."""
        return deepcopy(self._additional_params)

    def to_params(self) -> Dict[str, Any]:
        """Convert the query to URL parameters dictionary.

        Returns:
            Dictionary suitable for use as query parameters
        """
        params: Dict[str, Any] = deepcopy(self._additional_params)

        if self._fields:
            params["fields"] = self._fields

        if self._filters:
            if len(self._filters) == 1 and self._filters[0].is_group:
                params["filter"] = self._filters[0].to_dict()
            else:
                params["filter"] = {
                    "logic": "and",
                    "filters": [filter_.to_dict() for filter_ in self._filters],
                }

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
        query._additional_params = deepcopy(self._additional_params)
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
        if self._additional_params:
            parts.append(f"params={len(self._additional_params)}")
        return f"DaktelaQuery({', '.join(parts)})"
