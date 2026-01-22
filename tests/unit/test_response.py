"""Tests for DaktelaResponse."""

from daktela import DaktelaResponse


class TestDaktelaResponse:
    """Tests for DaktelaResponse class."""

    def test_success_response(self) -> None:
        """Test successful response."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"name": "Test"}],
            total=1,
        )
        assert r.status_code == 200
        assert r.is_success
        assert not r.has_errors
        assert r.total == 1

    def test_error_response(self) -> None:
        """Test error response."""
        r = DaktelaResponse(
            status_code=400,
            errors=["Invalid field"],
        )
        assert r.status_code == 400
        assert not r.is_success
        assert r.has_errors
        assert r.errors == ["Invalid field"]

    def test_as_list_with_list_data(self) -> None:
        """Test as_list with list data."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}, {"b": 2}],
        )
        assert r.as_list() == [{"a": 1}, {"b": 2}]

    def test_as_list_with_single_object(self) -> None:
        """Test as_list with single object."""
        r = DaktelaResponse(
            status_code=200,
            data={"name": "Test"},
        )
        assert r.as_list() == [{"name": "Test"}]

    def test_as_list_with_none(self) -> None:
        """Test as_list with None data."""
        r = DaktelaResponse(status_code=200, data=None)
        assert r.as_list() == []

    def test_as_dict_with_dict_data(self) -> None:
        """Test as_dict with dict data."""
        r = DaktelaResponse(
            status_code=200,
            data={"name": "Test"},
        )
        assert r.as_dict() == {"name": "Test"}

    def test_as_dict_with_list_data(self) -> None:
        """Test as_dict with list data."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}, {"b": 2}],
        )
        assert r.as_dict() == {"a": 1}

    def test_as_dict_with_empty_list(self) -> None:
        """Test as_dict with empty list."""
        r = DaktelaResponse(status_code=200, data=[])
        assert r.as_dict() == {}

    def test_as_dict_with_none(self) -> None:
        """Test as_dict with None data."""
        r = DaktelaResponse(status_code=200, data=None)
        assert r.as_dict() == {}

    def test_get_method(self) -> None:
        """Test get method."""
        r = DaktelaResponse(
            status_code=200,
            data={"name": "Test", "value": 123},
        )
        assert r.get("name") == "Test"
        assert r.get("value") == 123
        assert r.get("missing") is None
        assert r.get("missing", "default") == "default"

    def test_iteration(self) -> None:
        """Test iteration over response."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}, {"b": 2}],
        )
        items = list(r)
        assert items == [{"a": 1}, {"b": 2}]

    def test_len(self) -> None:
        """Test len()."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}, {"b": 2}, {"c": 3}],
        )
        assert len(r) == 3

    def test_bool_success_with_data(self) -> None:
        """Test bool with success and data."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}],
        )
        assert bool(r) is True

    def test_bool_success_without_data(self) -> None:
        """Test bool with success but no data."""
        r = DaktelaResponse(status_code=200, data=None)
        assert bool(r) is False

    def test_bool_error(self) -> None:
        """Test bool with error."""
        r = DaktelaResponse(
            status_code=400,
            data=[{"a": 1}],
        )
        assert bool(r) is False

    def test_repr(self) -> None:
        """Test repr."""
        r = DaktelaResponse(
            status_code=200,
            data=[{"a": 1}],
            total=100,
        )
        rep = repr(r)
        assert "200" in rep
        assert "1" in rep  # items
        assert "100" in rep  # total
