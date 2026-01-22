"""Tests for DaktelaFilter."""

from daktela import DaktelaFilter


class TestDaktelaFilter:
    """Tests for DaktelaFilter class."""

    def test_eq_filter(self) -> None:
        """Test equals filter."""
        f = DaktelaFilter.eq("stage", "OPEN")
        assert f.field == "stage"
        assert f.operator == "eq"
        assert f.value == "OPEN"
        assert not f.is_or

    def test_neq_filter(self) -> None:
        """Test not equals filter."""
        f = DaktelaFilter.neq("status", "CLOSED")
        assert f.field == "status"
        assert f.operator == "neq"
        assert f.value == "CLOSED"

    def test_gt_filter(self) -> None:
        """Test greater than filter."""
        f = DaktelaFilter.gt("priority", 5)
        assert f.field == "priority"
        assert f.operator == "gt"
        assert f.value == 5

    def test_gte_filter(self) -> None:
        """Test greater than or equal filter."""
        f = DaktelaFilter.gte("created", "2024-01-01")
        assert f.field == "created"
        assert f.operator == "gte"
        assert f.value == "2024-01-01"

    def test_lt_filter(self) -> None:
        """Test less than filter."""
        f = DaktelaFilter.lt("priority", 10)
        assert f.field == "priority"
        assert f.operator == "lt"
        assert f.value == 10

    def test_lte_filter(self) -> None:
        """Test less than or equal filter."""
        f = DaktelaFilter.lte("edited", "2024-12-31")
        assert f.field == "edited"
        assert f.operator == "lte"
        assert f.value == "2024-12-31"

    def test_like_filter(self) -> None:
        """Test like filter."""
        f = DaktelaFilter.like("name", "test")
        assert f.field == "name"
        assert f.operator == "like"
        assert f.value == "test"

    def test_in_filter(self) -> None:
        """Test in filter."""
        f = DaktelaFilter.in_("status", ["NEW", "OPEN", "PENDING"])
        assert f.field == "status"
        assert f.operator == "in"
        assert f.value == ["NEW", "OPEN", "PENDING"]

    def test_not_in_filter(self) -> None:
        """Test not in filter."""
        f = DaktelaFilter.not_in("category", ["spam", "deleted"])
        assert f.field == "category"
        assert f.operator == "nin"
        assert f.value == ["spam", "deleted"]

    def test_or_filter(self) -> None:
        """Test OR combination of filters."""
        f = DaktelaFilter.or_(
            DaktelaFilter.eq("stage", "OPEN"),
            DaktelaFilter.eq("stage", "NEW"),
        )
        assert f.is_or
        assert f.or_filters is not None
        assert len(f.or_filters) == 2
        assert f.or_filters[0].value == "OPEN"
        assert f.or_filters[1].value == "NEW"

    def test_to_dict_simple(self) -> None:
        """Test to_dict for simple filter."""
        f = DaktelaFilter.eq("name", "test")
        d = f.to_dict()
        assert d == {
            "field": "name",
            "operator": "eq",
            "value": "test",
        }

    def test_to_dict_or(self) -> None:
        """Test to_dict for OR filter."""
        f = DaktelaFilter.or_(
            DaktelaFilter.eq("a", 1),
            DaktelaFilter.eq("b", 2),
        )
        d = f.to_dict()
        assert "or" in d
        assert len(d["or"]) == 2

    def test_repr_simple(self) -> None:
        """Test repr for simple filter."""
        f = DaktelaFilter.eq("stage", "OPEN")
        assert "eq" in repr(f)
        assert "stage" in repr(f)
        assert "OPEN" in repr(f)

    def test_repr_or(self) -> None:
        """Test repr for OR filter."""
        f = DaktelaFilter.or_(
            DaktelaFilter.eq("a", 1),
            DaktelaFilter.eq("b", 2),
        )
        assert "or_" in repr(f)
