"""Tests for DaktelaSort."""

from daktela import DaktelaSort


class TestDaktelaSort:
    """Tests for DaktelaSort class."""

    def test_asc_sort(self) -> None:
        """Test ascending sort."""
        s = DaktelaSort.asc("name")
        assert s.field == "name"
        assert s.direction == "asc"

    def test_desc_sort(self) -> None:
        """Test descending sort."""
        s = DaktelaSort.desc("created")
        assert s.field == "created"
        assert s.direction == "desc"

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        s = DaktelaSort.desc("edited")
        d = s.to_dict()
        assert d == {
            "field": "edited",
            "dir": "desc",
        }

    def test_repr(self) -> None:
        """Test repr."""
        s = DaktelaSort.asc("name")
        assert "asc" in repr(s)
        assert "name" in repr(s)
