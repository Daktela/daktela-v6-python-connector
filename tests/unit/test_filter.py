"""Tests for DaktelaFilter."""

from typing import Any

import pytest

from daktela import DaktelaFilter


@pytest.mark.parametrize(
    ("filter_", "operator", "value"),
    [
        (DaktelaFilter.eq("field", 1), "eq", 1),
        (DaktelaFilter.neq("field", 1), "neq", 1),
        (DaktelaFilter.gt("field", 1), "gt", 1),
        (DaktelaFilter.gte("field", 1), "gte", 1),
        (DaktelaFilter.lt("field", 1), "lt", 1),
        (DaktelaFilter.lte("field", 1), "lte", 1),
        (DaktelaFilter.like("field", "%x%"), "like", "%x%"),
        (DaktelaFilter.not_like("field", "%x%"), "notlike", "%x%"),
        (DaktelaFilter.contains("field", "x"), "contains", "x"),
        (DaktelaFilter.not_contains("field", "x"), "doesnotcontain", "x"),
        (DaktelaFilter.starts_with("field", "x"), "startswith", "x"),
        (DaktelaFilter.ends_with("field", "x"), "endswith", "x"),
        (DaktelaFilter.in_("field", [1, 2]), "in", [1, 2]),
        (DaktelaFilter.not_in("field", [1, 2]), "notin", [1, 2]),
        (DaktelaFilter.is_null("field"), "isnull", None),
        (DaktelaFilter.is_not_null("field"), "isnotnull", None),
    ],
)
def test_named_filter_factories(
    filter_: DaktelaFilter, operator: str, value: object
) -> None:
    assert filter_.field == "field"
    assert filter_.operator == operator
    assert filter_.value == value
    assert not filter_.is_group
    assert not filter_.is_or
    assert filter_.logic is None
    assert filter_.filters is None
    assert filter_.or_filters is None


def test_custom_filter_and_ignore_case() -> None:
    filter_ = DaktelaFilter.custom("name", "future", "Alice", ignore_case=True)
    assert filter_.to_dict() == {
        "field": "name",
        "operator": "future",
        "value": "Alice",
        "ignoreCase": True,
    }


def test_custom_field_type_filter() -> None:
    filter_ = DaktelaFilter.custom(
        "customFields", "endswith", "@example.com", field_type="email"
    )
    assert filter_.to_dict() == {
        "field": "customFields",
        "operator": "endswith",
        "value": "@example.com",
        "type": "email",
    }


def test_custom_field_type_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="field_type"):
        DaktelaFilter.custom("customFields", "eq", "x", field_type="")


@pytest.mark.parametrize(
    ("factory", "operator", "value"),
    [
        (DaktelaFilter.begins, "startswith", "x"),
        (DaktelaFilter.ends, "endswith", "x"),
        (DaktelaFilter.not_begins, "notlike", "x%"),
        (DaktelaFilter.not_ends, "notlike", "%x"),
    ],
)
def test_deprecated_factories_send_supported_operators(
    factory: Any, operator: str, value: str
) -> None:
    # The API rejects begins, notbegins, ends, and notends.
    with pytest.warns(DeprecationWarning, match="deprecated") as warning:
        filter_ = factory("field", "x")
    assert warning[0].filename == __file__
    assert filter_.to_dict() == {"field": "field", "operator": operator, "value": value}


def test_null_filter_omits_value() -> None:
    assert DaktelaFilter.is_null("deleted").to_dict() == {
        "field": "deleted",
        "operator": "isnull",
    }


def test_nested_filter_groups() -> None:
    filter_ = DaktelaFilter.and_(
        DaktelaFilter.eq("active", True),
        DaktelaFilter.or_(
            DaktelaFilter.eq("team", "sales"),
            DaktelaFilter.eq("team", "support"),
        ),
    )

    assert filter_.is_group
    assert filter_.logic == "and"
    assert filter_.filters is not None
    assert filter_.to_dict() == {
        "logic": "and",
        "filters": [
            {"field": "active", "operator": "eq", "value": True},
            {
                "logic": "or",
                "filters": [
                    {"field": "team", "operator": "eq", "value": "sales"},
                    {"field": "team", "operator": "eq", "value": "support"},
                ],
            },
        ],
    }
    assert "and_" in repr(filter_)


def test_or_group_and_compatibility_alias() -> None:
    filters = [DaktelaFilter.eq("stage", "OPEN"), DaktelaFilter.eq("stage", "NEW")]
    filter_ = DaktelaFilter(or_filters=filters)

    assert filter_.is_or
    assert filter_.or_filters is not None
    assert [item.value for item in filter_.or_filters] == ["OPEN", "NEW"]
    assert filter_.to_dict()["logic"] == "or"
    assert "or_" in repr(filter_)


def test_group_filters_property_is_a_copy() -> None:
    group = DaktelaFilter.or_(DaktelaFilter.eq("field", "value"))
    returned = group.filters
    assert returned is not None
    returned.clear()
    assert group.filters is not None
    assert len(group.filters) == 1


def test_simple_repr() -> None:
    representation = repr(DaktelaFilter.eq("stage", "OPEN"))
    assert "eq" in representation
    assert "stage" in representation
    assert "OPEN" in representation


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DaktelaFilter(),
        lambda: DaktelaFilter("field", ""),
        lambda: DaktelaFilter("field", "eq", logic="and", filters=[]),
        lambda: DaktelaFilter(logic="xor", filters=[DaktelaFilter.eq("a", 1)]),
        lambda: DaktelaFilter(logic="and", filters=[]),
    ],
)
def test_invalid_filters(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


@pytest.mark.parametrize("factory", [DaktelaFilter.in_, DaktelaFilter.not_in])
def test_list_filters_reject_empty_values(factory: Any) -> None:
    with pytest.raises(ValueError, match="at least one value"):
        factory("name", [])
