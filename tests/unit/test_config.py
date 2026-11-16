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
            ({"url": "https://example.com/a/../b"}, "relative"),
            ({"url": "https://example.com/a//b"}, "empty"),
            ({"url": "https://example.com/%2e%2e"}, "relative"),
            ({"url": "https://example.com/a\\b"}, "backslash"),
            ({"url": "https://user:secret@example.com"}, "credentials"),
            ({"url": "https://example.com?source=test"}, "query string"),
            ({"url": "https://example.com#fragment"}, "fragment"),
            ({"access_token": ""}, "access_token"),
            ({"access_token": "token\n"}, "line breaks"),
            ({"access_token": " token"}, "whitespace"),
            ({"access_token": "tok\ten"}, "control"),
            ({"access_token": "tokén"}, "non-ASCII"),
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


def test_access_token_is_hidden_from_repr() -> None:
    config = DaktelaConfig(url="my.daktela.com", access_token="super-secret")
    assert "super-secret" not in repr(config)
    assert "super-secret" not in str(config)


def test_invalid_token_is_not_echoed() -> None:
    with pytest.raises(ValueError) as raised:
        DaktelaConfig(url="my.daktela.com", access_token="super-secret\n")
    assert "super-secret" not in str(raised.value)


@pytest.mark.parametrize(
    ("url", "location", "instance_url"),
    [
        ("https://example.com/daktela/", "example.com/daktela", "https://example.com/daktela"),
        ("example.com/daktela/api/v6", "example.com/daktela", "https://example.com/daktela"),
        ("http://example.com:8080/a/b/API/V6/", "example.com:8080/a/b", "http://example.com:8080/a/b"),
    ],
)
def test_url_with_path_prefix(url: str, location: str, instance_url: str) -> None:
    config = DaktelaConfig(url=url, access_token="token")
    assert config.url == location
    assert config.instance_url == instance_url
    assert config.base_url == f"{instance_url}/api/v6"


def test_access_token_is_optional_for_login_sessions() -> None:
    config = DaktelaConfig(url="my.daktela.com")
    assert config.access_token is None


def test_bearer_auth_method() -> None:
    config = DaktelaConfig(url="my.daktela.com", access_token="t", auth_method=AuthMethod.BEARER)
    assert config.auth_method == AuthMethod.BEARER


def test_cookie_auth_method_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match="c_user") as warning:
        DaktelaConfig(url="my.daktela.com", access_token="t", auth_method=AuthMethod.COOKIE)
    assert warning[0].filename == __file__


def test_default_user_agent_tracks_the_package_version() -> None:
    from daktela import __version__

    assert DaktelaConfig(url="my.daktela.com", access_token="t").user_agent == (
        f"DaktelaPythonSDK/{__version__}"
    )
