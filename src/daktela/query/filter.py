"""Filter builder for Daktela API queries."""

from typing import Any, Dict, List, Optional, Sequence


class DaktelaFilter:
    """Builder for Daktela API filter expressions.

    Supports all standard filter operators and OR combinations.

    Example:
        >>> DaktelaFilter.eq("stage", "OPEN")
        >>> DaktelaFilter.gte("created", "2024-01-01")
        >>> DaktelaFilter.in_("status", ["NEW", "OPEN"])
        >>> DaktelaFilter.or_(
        ...     DaktelaFilter.eq("stage", "OPEN"),
        ...     DaktelaFilter.eq("stage", "NEW")
        ... )
    """

    def __init__(
        self,
        field: Optional[str] = None,
        operator: Optional[str] = None,
        value: Any = None,
        or_filters: Optional[List["DaktelaFilter"]] = None,
    ) -> None:
        """Initialize a filter.

        Use the static factory methods instead of calling this directly.
        """
        self._field = field
        self._operator = operator
        self._value = value
        self._or_filters = or_filters
        self._is_or = or_filters is not None

    @property
    def field(self) -> Optional[str]:
        """Get the field name."""
        return self._field

    @property
    def operator(self) -> Optional[str]:
        """Get the operator."""
        return self._operator

    @property
    def value(self) -> Any:
        """Get the filter value."""
        return self._value

    @property
    def is_or(self) -> bool:
        """Check if this is an OR filter combination."""
        return self._is_or

    @property
    def or_filters(self) -> Optional[List["DaktelaFilter"]]:
        """Get the list of OR filters."""
        return self._or_filters

    @staticmethod
    def eq(field: str, value: Any) -> "DaktelaFilter":
        """Create an equals filter (field = value).

        Args:
            field: The field name
            value: The value to match

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "eq", value)

    @staticmethod
    def neq(field: str, value: Any) -> "DaktelaFilter":
        """Create a not equals filter (field != value).

        Args:
            field: The field name
            value: The value to exclude

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "neq", value)

    @staticmethod
    def gt(field: str, value: Any) -> "DaktelaFilter":
        """Create a greater than filter (field > value).

        Args:
            field: The field name
            value: The value to compare

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "gt", value)

    @staticmethod
    def gte(field: str, value: Any) -> "DaktelaFilter":
        """Create a greater than or equal filter (field >= value).

        Args:
            field: The field name
            value: The value to compare

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "gte", value)

    @staticmethod
    def lt(field: str, value: Any) -> "DaktelaFilter":
        """Create a less than filter (field < value).

        Args:
            field: The field name
            value: The value to compare

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "lt", value)

    @staticmethod
    def lte(field: str, value: Any) -> "DaktelaFilter":
        """Create a less than or equal filter (field <= value).

        Args:
            field: The field name
            value: The value to compare

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "lte", value)

    @staticmethod
    def like(field: str, value: Any) -> "DaktelaFilter":
        """Create a like filter (field contains value).

        Args:
            field: The field name
            value: The value to search for

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "like", value)

    @staticmethod
    def in_(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        """Create an in filter (field in values).

        Args:
            field: The field name
            values: The values to match

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "in", list(values))

    @staticmethod
    def not_in(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        """Create a not in filter (field not in values).

        Args:
            field: The field name
            values: The values to exclude

        Returns:
            A new filter instance
        """
        return DaktelaFilter(field, "nin", list(values))

    @staticmethod
    def or_(*filters: "DaktelaFilter") -> "DaktelaFilter":
        """Create an OR combination of filters.

        Args:
            *filters: The filters to combine with OR

        Returns:
            A new filter instance representing the OR combination
        """
        return DaktelaFilter(or_filters=list(filters))

    def to_dict(self) -> Dict[str, Any]:
        """Convert this filter to a dictionary for API serialization.

        Returns:
            Dictionary representation of the filter
        """
        if self._is_or and self._or_filters:
            return {
                "or": [f.to_dict() for f in self._or_filters]
            }
        return {
            "field": self._field,
            "operator": self._operator,
            "value": self._value,
        }

    def __repr__(self) -> str:
        if self._is_or:
            return f"DaktelaFilter.or_({', '.join(repr(f) for f in (self._or_filters or []))})"
        return f"DaktelaFilter.{self._operator}({self._field!r}, {self._value!r})"
