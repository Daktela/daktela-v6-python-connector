"""Filter builder for Daktela API queries."""

import warnings
from typing import Any, Dict, List, Optional, Sequence


def _deprecated(name: str, replacement: str) -> None:
    warnings.warn(
        f"DaktelaFilter.{name} is deprecated; use DaktelaFilter.{replacement}",
        DeprecationWarning,
        stacklevel=3,
    )


def _non_empty_values(name: str, values: Sequence[Any]) -> List[Any]:
    # An empty list serializes to no value at all, which the API may treat as
    # "no constraint" and match every record.
    result = list(values)
    if not result:
        raise ValueError(f"{name}() requires at least one value")
    return result


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
        field_type: Optional[str] = None,
    ) -> None:
        """Initialize a filter.

        ``or_filters`` is retained for compatibility with version 1.0. New
        code should use :meth:`or_` or :meth:`and_`.
        """
        if field_type is not None and not field_type:
            raise ValueError("filter field_type must not be empty")
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
        self._field_type = field_type

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
        field_type: Optional[str] = None,
    ) -> "DaktelaFilter":
        """Create a filter using an arbitrary API operator.

        Args:
            field: Field to filter, e.g. ``"customFields"`` or
                ``"customFields.email"``
            operator: API operator
            value: Filter value
            ignore_case: Sent as ``ignoreCase``. Current Daktela versions do
                not interpret it; string comparisons follow the database
                collation, which is usually case-insensitive.
            field_type: Sent as ``type`` to limit a ``customFields`` filter to
                custom fields of one type, such as ``"email"`` or ``"phone"``
        """
        return DaktelaFilter(
            field, operator, value, ignore_case=ignore_case, field_type=field_type
        )

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
        """Match an SQL ``LIKE`` pattern, e.g. ``"%urgent%"``.

        The value is used as given: ``%`` matches any text and ``_`` any single
        character. Use :meth:`contains` to match a plain substring.
        """
        return DaktelaFilter(field, "like", value)

    @staticmethod
    def not_like(field: str, value: Any) -> "DaktelaFilter":
        """Exclude values matching an SQL ``LIKE`` pattern, e.g. ``"%spam%"``."""
        return DaktelaFilter(field, "notlike", value)

    @staticmethod
    def contains(field: str, value: Any) -> "DaktelaFilter":
        """Match values that contain ``value``."""
        return DaktelaFilter(field, "contains", value)

    @staticmethod
    def not_contains(field: str, value: Any) -> "DaktelaFilter":
        """Match values that do not contain ``value``."""
        return DaktelaFilter(field, "doesnotcontain", value)

    @staticmethod
    def starts_with(field: str, value: Any) -> "DaktelaFilter":
        """Match values that start with ``value``."""
        return DaktelaFilter(field, "startswith", value)

    @staticmethod
    def ends_with(field: str, value: Any) -> "DaktelaFilter":
        """Match values that end with ``value``."""
        return DaktelaFilter(field, "endswith", value)

    @staticmethod
    def begins(field: str, value: Any) -> "DaktelaFilter":
        """Deprecated alias of :meth:`starts_with`.

        Versions before 1.3 sent the ``begins`` operator, which the Daktela API
        rejects; this alias now sends ``startswith``.
        """
        _deprecated("begins()", "starts_with()")
        return DaktelaFilter.starts_with(field, value)

    @staticmethod
    def not_begins(field: str, value: Any) -> "DaktelaFilter":
        """Deprecated: match values that do not start with ``value``.

        The API has no such operator, so this sends ``notlike`` with the
        pattern ``value%``; ``%`` and ``_`` in ``value`` act as wildcards. Use
        :meth:`not_like` with an explicit pattern.
        """
        _deprecated("not_begins()", 'not_like() with a "value%" pattern')
        return DaktelaFilter.not_like(field, f"{value}%")

    @staticmethod
    def ends(field: str, value: Any) -> "DaktelaFilter":
        """Deprecated alias of :meth:`ends_with`.

        Versions before 1.3 sent the ``ends`` operator, which the Daktela API
        rejects; this alias now sends ``endswith``.
        """
        _deprecated("ends()", "ends_with()")
        return DaktelaFilter.ends_with(field, value)

    @staticmethod
    def not_ends(field: str, value: Any) -> "DaktelaFilter":
        """Deprecated: match values that do not end with ``value``.

        The API has no such operator, so this sends ``notlike`` with the
        pattern ``%value``; ``%`` and ``_`` in ``value`` act as wildcards. Use
        :meth:`not_like` with an explicit pattern.
        """
        _deprecated("not_ends()", 'not_like() with a "%value" pattern')
        return DaktelaFilter.not_like(field, f"%{value}")

    @staticmethod
    def in_(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        return DaktelaFilter(field, "in", _non_empty_values("in_", values))

    @staticmethod
    def not_in(field: str, values: Sequence[Any]) -> "DaktelaFilter":
        return DaktelaFilter(field, "notin", _non_empty_values("not_in", values))

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
        if self._field_type is not None:
            result["type"] = self._field_type
        return result

    def __repr__(self) -> str:
        if self._filters is not None:
            filters = ", ".join(repr(filter_) for filter_ in self._filters)
            return f"DaktelaFilter.{self._logic}_({filters})"
        return f"DaktelaFilter.{self._operator}({self._field!r}, {self._value!r})"
