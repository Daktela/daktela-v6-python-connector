"""Filter builder for Daktela API queries."""

from typing import Any, Dict, List, Optional, Sequence


class DaktelaFilter:
    """A simple filter or a nested logical filter group.

    Prefer the named constructors for common operators and :meth:`custom` for
    API operators introduced after this SDK release.
    """

    def __init__(
        self,
        field: Optional[str] = None,
        operator: Optional[str] = None,
        value: Any = None,
        or_filters: Optional[List["DaktelaFilter"]] = None,
        *,
        logic: Optional[str] = None,
        filters: Optional[Sequence["DaktelaFilter"]] = None,
        ignore_case: Optional[bool] = None,
    ) -> None:
        """Initialize a filter.

        ``or_filters`` is retained for compatibility with version 1.0. New
        code should use :meth:`or_` or :meth:`and_`.
        """
        group_filters = list(filters) if filters is not None else or_filters
        group_logic = logic or ("or" if or_filters is not None else None)

        if group_filters is not None:
            if field is not None or operator is not None:
                raise ValueError("filter groups cannot have a field or operator")
            if group_logic not in {"and", "or"}:
                raise ValueError("filter group logic must be 'and' or 'or'")
            if not group_filters:
                raise ValueError("filter groups must contain at least one filter")
        else:
            if not field:
                raise ValueError("filter field must not be empty")
            if not operator:
                raise ValueError("filter operator must not be empty")

        self._field = field
        self._operator = operator
        self._value = value
        self._filters = group_filters
        self._logic = group_logic
        self._ignore_case = ignore_case

    @property
    def field(self) -> Optional[str]:
        """Return the field name for a simple filter."""
        return self._field

    @property
    def operator(self) -> Optional[str]:
        """Return the operator for a simple filter."""
        return self._operator

    @property
    def value(self) -> Any:
        """Return the filter value."""
        return self._value

    @property
    def is_group(self) -> bool:
        """Return whether this filter is a logical group."""
        return self._filters is not None

    @property
    def is_or(self) -> bool:
        """Return whether this filter is an OR group."""
        return self.is_group and self._logic == "or"

    @property
    def logic(self) -> Optional[str]:
        """Return the group logic, if this is a group."""
        return self._logic

    @property
    def filters(self) -> Optional[List["DaktelaFilter"]]:
        """Return a copy of the filters in this group."""
        return list(self._filters) if self._filters is not None else None

    @property
    def or_filters(self) -> Optional[List["DaktelaFilter"]]:
        """Compatibility alias for the filters in an OR group."""
        return self.filters if self.is_or else None

    @staticmethod
    def custom(
        field: str,
        operator: str,
        value: Any = None,
        *,
        ignore_case: Optional[bool] = None,
    ) -> "DaktelaFilter":
        """Create a filter using an arbitrary API operator."""
        return DaktelaFilter(field, operator, value, ignore_case=ignore_case)

    @staticmethod
    def eq(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "eq", value)

    @staticmethod
    def neq(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "neq", value)

    @staticmethod
    def gt(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "gt", value)

    @staticmethod
    def gte(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "gte", value)

    @staticmethod
    def lt(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "lt", value)

    @staticmethod
    def lte(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "lte", value)

    @staticmethod
    def like(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "like", value)

    @staticmethod
    def not_like(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "notlike", value)

    @staticmethod
    def begins(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "begins", value)

    @staticmethod
    def not_begins(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "notbegins", value)

    @staticmethod
    def ends(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "ends", value)

    @staticmethod
    def not_ends(field: str, value: Any) -> "DaktelaFilter":
        return DaktelaFilter(field, "notends", value)

    @staticmethod
    def in_(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        return DaktelaFilter(field, "in", list(values))

    @staticmethod
    def not_in(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        return DaktelaFilter(field, "notin", list(values))

    @staticmethod
    def is_null(field: str) -> "DaktelaFilter":
        return DaktelaFilter(field, "isnull")

    @staticmethod
    def is_not_null(field: str) -> "DaktelaFilter":
        return DaktelaFilter(field, "isnotnull")

    @staticmethod
    def and_(*filters: "DaktelaFilter") -> "DaktelaFilter":
        return DaktelaFilter(logic="and", filters=filters)

    @staticmethod
    def or_(*filters: "DaktelaFilter") -> "DaktelaFilter":
        return DaktelaFilter(logic="or", filters=filters)

    def to_dict(self) -> Dict[str, Any]:
        """Convert this filter to the nested API query representation."""
        if self._filters is not None:
            return {
                "logic": self._logic,
                "filters": [filter_.to_dict() for filter_ in self._filters],
            }

        result: Dict[str, Any] = {
            "field": self._field,
            "operator": self._operator,
        }
        if self._value is not None:
            result["value"] = self._value
        if self._ignore_case is not None:
            result["ignoreCase"] = self._ignore_case
        return result

    def __repr__(self) -> str:
        if self._filters is not None:
            filters = ", ".join(repr(filter_) for filter_ in self._filters)
            return f"DaktelaFilter.{self._logic}_({filters})"
        return f"DaktelaFilter.{self._operator}({self._field!r}, {self._value!r})"
