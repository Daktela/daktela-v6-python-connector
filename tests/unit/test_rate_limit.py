"""Tests for RateLimitConfig."""

from daktela import RateLimitConfig


class TestRateLimitConfig:
    """Tests for RateLimitConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.max_wait == 120.0
        assert config.default_retry_after == 60.0

    def test_get_wait_time_with_retry_after(self) -> None:
        """Test get_wait_time with Retry-After value."""
        config = RateLimitConfig()
        assert config.get_wait_time(30) == 30.0

    def test_get_wait_time_without_retry_after(self) -> None:
        """Test get_wait_time without Retry-After value."""
        config = RateLimitConfig(default_retry_after=45.0)
        assert config.get_wait_time(None) == 45.0

    def test_get_wait_time_exceeds_max(self) -> None:
        """Test get_wait_time when wait exceeds max_wait."""
        config = RateLimitConfig(max_wait=60.0)
        assert config.get_wait_time(120) is None

    def test_get_wait_time_disabled(self) -> None:
        """Test get_wait_time when disabled."""
        config = RateLimitConfig(enabled=False)
        assert config.get_wait_time(30) is None

    def test_disabled_factory(self) -> None:
        """Test disabled factory method."""
        config = RateLimitConfig.disabled()
        assert config.enabled is False
        assert config.get_wait_time(30) is None

    def test_patient_factory(self) -> None:
        """Test patient factory method."""
        config = RateLimitConfig.patient()
        assert config.enabled is True
        assert config.max_wait == 300.0
        assert config.get_wait_time(200) == 200.0
