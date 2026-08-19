"""Pagination configuration for Daktela API queries."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DaktelaPagination:
    """Pagination parameters for API queries.

    Attributes:
        take: Number of records to retrieve (limit)
        skip: Number of records to skip (offset)
    """

    take: Optional[int] = None
    skip: Optional[int] = None

    def __post_init__(self) -> None:
        if self.take is not None and self.take < 0:
            raise ValueError("take must not be negative")
        if self.skip is not None and self.skip < 0:
            raise ValueError("skip must not be negative")

    @staticmethod
    def page(page_number: int, page_size: int) -> "DaktelaPagination":
        """Create pagination for a specific page.

        Args:
            page_number: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Pagination instance configured for the specified page
        """
        if page_number < 1:
            raise ValueError("page_number must be at least one")
        if page_size <= 0:
            raise ValueError("page_size must be greater than zero")
        skip = (page_number - 1) * page_size
        return DaktelaPagination(take=page_size, skip=skip)

    @staticmethod
    def limit(take: int, skip: int = 0) -> "DaktelaPagination":
        """Create pagination with take/skip values.

        Args:
            take: Number of records to retrieve
            skip: Number of records to skip

        Returns:
            Pagination instance
        """
        if take < 0:
            raise ValueError("take must not be negative")
        if skip < 0:
            raise ValueError("skip must not be negative")
        return DaktelaPagination(take=take, skip=skip)

    def next_page(self) -> "DaktelaPagination":
        """Get pagination for the next page.

        Returns:
            Pagination instance for the next page
        """
        if self.take is None:
            return self
        skip = (self.skip or 0) + self.take
        return DaktelaPagination(take=self.take, skip=skip)

    def __repr__(self) -> str:
        return f"DaktelaPagination(take={self.take}, skip={self.skip})"
