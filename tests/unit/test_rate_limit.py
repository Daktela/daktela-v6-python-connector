"""Tests for RateLimitConfig."""

from datetime import datetime, timezone

import pytest

from daktela import RateLimitConfig


def test_default_config() -> None:
    config = RateLimitConfig()
    assert config.enabled is True
    assert config.max_retries == 3
    assert config.max_wait == 120.0
    assert config.default_retry_after == 60.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [("30", 30.0), ("0", 0.0), ("-2", 0.0), (None, None), ("", None), ("bad", None)],
)
def test_parse_retry_after_seconds(value: str | None, expected: float | None) -> None:
    assert RateLimitConfig().parse_retry_after(value) == expected


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    value = "Wed, 19 Aug 2026 12:00:30 GMT"
    assert RateLimitConfig().parse_retry_after(value, now=now) == 30.0


def test_parse_retry_after_past_and_naive_dates() -> None:
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert RateLimitConfig().parse_retry_after(
        "Wed, 19 Aug 2026 11:59:00 GMT", now=now
    ) == 0.0
    assert RateLimitConfig().parse_retry_after(
        "Wed, 19 Aug 2026 12:00:10", now=now
    ) == 10.0


def test_wait_time_configuration() -> None:
    config = RateLimitConfig(default_retry_after=45.0, max_wait=60.0)
    assert config.get_wait_time(None) == 45.0
    assert config.get_wait_time(0) == 0.0
    assert config.get_wait_time(30) == 30.0
    assert config.get_wait_time(120) is None
    assert RateLimitConfig.disabled().get_wait_time(30) is None


def test_patient_factory() -> None:
    config = RateLimitConfig.patient()
    assert config.enabled is True
    assert config.max_retries == 5
    assert config.max_wait == 300.0
    assert config.get_wait_time(200) == 200.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retries": -1},
        {"max_wait": -1},
        {"default_retry_after": -1},
    ],
)
def test_invalid_config(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        RateLimitConfig(**kwargs)
