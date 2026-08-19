"""Tests for public formatting helpers."""

import pytest

from daktela import normalize_phone_number


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (None, None),
        ("773 794 604", "00420773794604"),
        ("420773794604", "00420773794604"),
        ("+420773794604", "00420773794604"),
        ("00420773794604", "00420773794604"),
    ],
)
def test_normalize_phone_number(number: str | None, expected: str | None) -> None:
    assert normalize_phone_number(number) == expected


def test_normalize_phone_number_with_plus_and_custom_prefix() -> None:
    assert normalize_phone_number(
        "905551234",
        plus_sign=True,
        international_prefix="421",
        international_length=12,
    ) == "+421905551234"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"international_prefix": ""},
        {"international_length": 0},
    ],
)
def test_invalid_phone_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        normalize_phone_number("123", **kwargs)  # type: ignore[arg-type]
