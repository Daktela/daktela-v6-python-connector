"""Tests for DaktelaQuery."""

from daktela import DaktelaFilter, DaktelaPagination, DaktelaQuery, DaktelaSort


class TestDaktelaQuery:
    """Tests for DaktelaQuery class."""

    def test_empty_query(self) -> None:
        """Test empty query."""
        q = DaktelaQuery()
        assert q.get_fields() == []
        assert q.get_filters() == []
        assert q.get_sorts() == []
        assert q.get_take() is None
        assert q.get_skip() is None

    def test_fields(self) -> None:
        """Test adding fields."""
        q = DaktelaQuery().fields("name", "title", "status")
        assert q.get_fields() == ["name", "title", "status"]

    def test_filter(self) -> None:
        """Test adding filter."""
        f = DaktelaFilter.eq("stage", "OPEN")
        q = DaktelaQuery().filter(f)
        assert len(q.get_filters()) == 1
        assert q.get_filters()[0].value == "OPEN"

    def test_multiple_filters(self) -> None:
        """Test adding multiple filters."""
        q = DaktelaQuery().filters(
            DaktelaFilter.eq("stage", "OPEN"),
            DaktelaFilter.gte("created", "2024-01-01"),
        )
        assert len(q.get_filters()) == 2

    def test_sort(self) -> None:
        """Test adding sort."""
        s = DaktelaSort.desc("created")
        q = DaktelaQuery().sort(s)
        assert len(q.get_sorts()) == 1
        assert q.get_sorts()[0].direction == "desc"

    def test_multiple_sorts(self) -> None:
        """Test adding multiple sorts."""
        q = DaktelaQuery().sorts(
            DaktelaSort.asc("name"),
            DaktelaSort.desc("created"),
        )
        assert len(q.get_sorts()) == 2

    def test_pagination_with_values(self) -> None:
        """Test pagination with take/skip values."""
        q = DaktelaQuery().pagination(take=50, skip=100)
        assert q.get_take() == 50
        assert q.get_skip() == 100

    def test_pagination_with_object(self) -> None:
        """Test pagination with DaktelaPagination object."""
        p = DaktelaPagination(take=25, skip=50)
        q = DaktelaQuery().pagination(pagination=p)
        assert q.get_take() == 25
        assert q.get_skip() == 50

    def test_take_and_skip(self) -> None:
        """Test take and skip methods."""
        q = DaktelaQuery().take(100).skip(200)
        assert q.get_take() == 100
        assert q.get_skip() == 200

    def test_method_chaining(self) -> None:
        """Test fluent method chaining."""
        q = (
            DaktelaQuery()
            .fields("name", "title")
            .filter(DaktelaFilter.eq("stage", "OPEN"))
            .sort(DaktelaSort.desc("created"))
            .take(50)
        )
        assert q.get_fields() == ["name", "title"]
        assert len(q.get_filters()) == 1
        assert len(q.get_sorts()) == 1
        assert q.get_take() == 50

    def test_to_params(self) -> None:
        """Test to_params method."""
        q = (
            DaktelaQuery()
            .fields("name", "title")
            .filter(DaktelaFilter.eq("stage", "OPEN"))
            .sort(DaktelaSort.desc("created"))
            .take(50)
            .skip(0)
        )
        params = q.to_params()

        assert params["fields"] == ["name", "title"]
        assert len(params["filter"]) == 1
        assert params["filter"][0]["field"] == "stage"
        assert len(params["sort"]) == 1
        assert params["sort"][0]["field"] == "created"
        assert params["take"] == 50
        assert params["skip"] == 0

    def test_copy(self) -> None:
        """Test copy method."""
        q1 = DaktelaQuery().fields("name").take(50)
        q2 = q1.copy()

        assert q2.get_fields() == ["name"]
        assert q2.get_take() == 50

        # Modify copy shouldn't affect original
        q2.fields("title")
        assert q1.get_fields() == ["name"]
        assert q2.get_fields() == ["name", "title"]

    def test_repr(self) -> None:
        """Test repr."""
        q = DaktelaQuery().fields("name").take(50)
        r = repr(q)
        assert "fields" in r
        assert "take" in r


class TestDaktelaPagination:
    """Tests for DaktelaPagination class."""

    def test_basic_pagination(self) -> None:
        """Test basic pagination."""
        p = DaktelaPagination(take=50, skip=100)
        assert p.take == 50
        assert p.skip == 100

    def test_page_factory(self) -> None:
        """Test page factory method."""
        p = DaktelaPagination.page(page_number=3, page_size=25)
        assert p.take == 25
        assert p.skip == 50  # (3-1) * 25

    def test_limit_factory(self) -> None:
        """Test limit factory method."""
        p = DaktelaPagination.limit(take=100, skip=200)
        assert p.take == 100
        assert p.skip == 200

    def test_next_page(self) -> None:
        """Test next_page method."""
        p1 = DaktelaPagination(take=25, skip=0)
        p2 = p1.next_page()
        assert p2.take == 25
        assert p2.skip == 25

    def test_next_page_without_take(self) -> None:
        """Test next_page when take is None."""
        p1 = DaktelaPagination()
        p2 = p1.next_page()
        assert p2.take is None
        assert p2.skip is None
