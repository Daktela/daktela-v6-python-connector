"""Tests for DaktelaFilter."""

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
        (DaktelaFilter.like("field", "x"), "like", "x"),
        (DaktelaFilter.not_like("field", "x"), "notlike", "x"),
        (DaktelaFilter.begins("field", "x"), "begins", "x"),
        (DaktelaFilter.not_begins("field", "x"), "notbegins", "x"),
        (DaktelaFilter.ends("field", "x"), "ends", "x"),
        (DaktelaFilter.not_ends("field", "x"), "notends", "x"),
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
