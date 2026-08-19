"""Tests for RetryConfig."""

import pytest

from daktela import RetryConfig


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.retry_on_connection_error is True
        assert config.retry_on_timeout is True

    def test_get_delay(self) -> None:
        """Test get_delay calculation."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0)
        assert config.get_delay(0) == 1.0  # 1 * 2^0
        assert config.get_delay(1) == 2.0  # 1 * 2^1
        assert config.get_delay(2) == 4.0  # 1 * 2^2
        assert config.get_delay(3) == 8.0  # 1 * 2^3

    def test_get_delay_max_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=5.0)
        assert config.get_delay(10) == 5.0

    def test_should_retry_on_retryable_status(self) -> None:
        """Test should_retry for retryable status codes."""
        config = RetryConfig(max_retries=3)
        assert config.should_retry(408, 0) is True
        assert config.should_retry(500, 0) is True
        assert config.should_retry(502, 0) is True
        assert config.should_retry(503, 0) is True
        assert config.should_retry(504, 0) is True

    def test_should_retry_non_retryable_status(self) -> None:
        """Test should_retry for non-retryable status codes."""
        config = RetryConfig(max_retries=3)
        assert config.should_retry(400, 0) is False
        assert config.should_retry(401, 0) is False
        assert config.should_retry(404, 0) is False
        assert config.should_retry(429, 0) is False

    def test_should_retry_max_attempts(self) -> None:
        """Test should_retry at max attempts."""
        config = RetryConfig(max_retries=3)
        assert config.should_retry(500, 2) is True  # attempt 2 < 3
        assert config.should_retry(500, 3) is False  # attempt 3 >= 3

    def test_disabled_factory(self) -> None:
        """Test disabled factory method."""
        config = RetryConfig.disabled()
        assert config.max_retries == 0
        assert config.should_retry(500, 0) is False

    def test_aggressive_factory(self) -> None:
        """Test aggressive factory method."""
        config = RetryConfig.aggressive()
        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0

    def test_delay_with_jitter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("daktela.http.retry.uniform", lambda start, end: end)
        config = RetryConfig(initial_delay=1.0, jitter=0.5)
        assert config.get_delay(0) == 1.5

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"max_retries": -1},
            {"initial_delay": -1},
            {"max_delay": -1},
            {"exponential_base": 0.5},
            {"jitter": -1},
        ],
    )
    def test_invalid_config(self, kwargs: dict[str, float]) -> None:
        with pytest.raises(ValueError):
            RetryConfig(**kwargs)  # type: ignore[arg-type]

    def test_negative_attempt_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="attempt"):
            RetryConfig().get_delay(-1)
