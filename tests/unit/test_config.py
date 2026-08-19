"""Tests for DaktelaConfig."""

import pytest

from daktela import AuthMethod, DaktelaConfig


class TestDaktelaConfig:
    """Tests for DaktelaConfig class."""

    def test_basic_config(self) -> None:
        """Test basic configuration creation."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="test-token",
        )
        assert config.url == "my.daktela.com"
        assert config.access_token == "test-token"
        assert config.auth_method == AuthMethod.HEADER
        assert config.timeout == 30.0
        assert config.verify_ssl is True

    def test_url_normalization_removes_protocol(self) -> None:
        """Test that URL normalization removes protocol."""
        config = DaktelaConfig(
            url="https://my.daktela.com",
            access_token="token",
        )
        assert config.url == "my.daktela.com"

    def test_url_normalization_removes_http(self) -> None:
        """Test that URL normalization preserves the HTTP scheme."""
        config = DaktelaConfig(
            url="http://my.daktela.com",
            access_token="token",
        )
        assert config.url == "my.daktela.com"
        assert config.base_url == "http://my.daktela.com/api/v6"

    def test_url_normalization_removes_trailing_slash(self) -> None:
        """Test that URL normalization removes trailing slash."""
        config = DaktelaConfig(
            url="my.daktela.com/",
            access_token="token",
        )
        assert config.url == "my.daktela.com"

    def test_url_normalization_removes_api_path(self) -> None:
        """Test that URL normalization removes API path."""
        config = DaktelaConfig(
            url="https://my.daktela.com/api/v6/",
            access_token="token",
        )
        assert config.url == "my.daktela.com"

    def test_base_url_property(self) -> None:
        """Test the base_url property."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
        )
        assert config.base_url == "https://my.daktela.com/api/v6"

    def test_custom_auth_method(self) -> None:
        """Test custom authentication method."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            auth_method=AuthMethod.QUERY,
        )
        assert config.auth_method == AuthMethod.QUERY

    def test_custom_timeout(self) -> None:
        """Test custom timeout."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            timeout=60.0,
        )
        assert config.timeout == 60.0

    def test_custom_user_agent(self) -> None:
        """Test custom user agent."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
            user_agent="CustomAgent/1.0",
        )
        assert config.user_agent == "CustomAgent/1.0"

    def test_config_is_immutable(self) -> None:
        """Test that config is immutable (frozen dataclass)."""
        config = DaktelaConfig(
            url="my.daktela.com",
            access_token="token",
        )
        with pytest.raises(AttributeError):
            config.url = "other.daktela.com"  # type: ignore

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"url": ""}, "url"),
            ({"url": "ftp://example.com"}, "scheme"),
            ({"url": "http://"}, "hostname"),
            ({"url": "https://example.com/other"}, "path"),
            ({"url": "https://user:secret@example.com"}, "credentials"),
            ({"url": "https://example.com?source=test"}, "query string"),
            ({"url": "https://example.com#fragment"}, "fragment"),
            ({"access_token": ""}, "access_token"),
            ({"timeout": 0}, "timeout"),
            ({"user_agent": ""}, "user_agent"),
        ],
    )
    def test_invalid_configuration(self, kwargs: dict[str, object], message: str) -> None:
        values: dict[str, object] = {
            "url": "example.com",
            "access_token": "token",
        }
        values.update(kwargs)
        with pytest.raises(ValueError, match=message):
            DaktelaConfig(**values)  # type: ignore[arg-type]

    def test_url_with_port_and_api_resource(self) -> None:
        config = DaktelaConfig(
            url="http://localhost:8080/api/v6/users",
            access_token="token",
        )
        assert config.url == "localhost:8080"
        assert config.base_url == "http://localhost:8080/api/v6"
