"""Sort builder for Daktela API queries."""

from typing import Dict


class DaktelaSort:
    """Builder for Daktela API sort expressions.

    Example:
        >>> DaktelaSort.asc("name")
        >>> DaktelaSort.desc("created")
    """

    def __init__(self, field: str, direction: str) -> None:
        """Initialize a sort.

        Use the static factory methods instead of calling this directly.

        Args:
            field: The field name to sort by
            direction: Sort direction ("asc" or "desc")
        """
        self._field = field
        self._direction = direction

    @property
    def field(self) -> str:
        """Get the field name."""
        return self._field

    @property
    def direction(self) -> str:
        """Get the sort direction."""
        return self._direction

    @staticmethod
    def asc(field: str) -> "DaktelaSort":
        """Create an ascending sort.

        Args:
            field: The field to sort by

        Returns:
            A new sort instance
        """
        return DaktelaSort(field, "asc")

    @staticmethod
    def desc(field: str) -> "DaktelaSort":
        """Create a descending sort.

        Args:
            field: The field to sort by

        Returns:
            A new sort instance
        """
        return DaktelaSort(field, "desc")

    def to_dict(self) -> Dict[str, str]:
        """Convert this sort to a dictionary for API serialization.

        Returns:
            Dictionary representation of the sort
        """
        return {
            "field": self._field,
            "dir": self._direction,
        }

    def __repr__(self) -> str:
        return f"DaktelaSort.{self._direction}({self._field!r})"
