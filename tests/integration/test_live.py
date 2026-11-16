"""Integration tests against a live Daktela instance.

Run with: pytest tests/integration/ -v --no-cov

Requires environment variables:
- DAKTELA_URL: Your Daktela instance URL
- DAKTELA_ACCESS_TOKEN: A static access token with read access to users

Optional:
- DAKTELA_USERNAME and DAKTELA_PASSWORD: Credentials of an account without
  two-factor authentication, for the login-session test
- DAKTELA_RECORDING_ACTIVITY: Name of a call activity with a recording
"""

import os
from typing import Callable

import pytest

from daktela import (
    AuthMethod,
    DaktelaClient,
    DaktelaConfig,
    DaktelaFilter,
    DaktelaQuery,
    DaktelaSort,
)


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} must be set")
    return value


@pytest.fixture
def live_url() -> str:
    return _env("DAKTELA_URL")


@pytest.fixture
def live_client(live_url: str) -> DaktelaClient:
    """Create a client for live testing."""
    return DaktelaClient(DaktelaConfig(url=live_url, access_token=_env("DAKTELA_ACCESS_TOKEN")))


class TestLiveAPI:
    """Integration tests against live Daktela API."""

    def test_ping(self, live_client: DaktelaClient) -> None:
        assert live_client.ping() is True

    def test_health_check(self, live_client: DaktelaClient) -> None:
        result = live_client.health_check()
        assert result["healthy"] is True, result
        assert result["latency_ms"] > 0

    def test_rejected_token_is_unhealthy(self, live_url: str) -> None:
        client = DaktelaClient(DaktelaConfig(url=live_url, access_token="0" * 40))
        result = client.health_check()
        assert result["healthy"] is False
        assert client.ping() is False

    def test_bearer_authentication(self, live_url: str) -> None:
        client = DaktelaClient(
            DaktelaConfig(
                url=live_url,
                access_token=_env("DAKTELA_ACCESS_TOKEN"),
                auth_method=AuthMethod.BEARER,
            )
        )
        assert client.ping() is True

    def test_get_users(self, live_client: DaktelaClient) -> None:
        response = live_client.get("users", DaktelaQuery().take(5))
        assert response.is_success

    def test_iterate_tickets(self, live_client: DaktelaClient) -> None:
        query = DaktelaQuery().sort(DaktelaSort.asc("name"))
        count = 0
        for ticket in live_client.iterate("tickets", query, page_size=5, max_items=10):
            count += 1
            assert "name" in ticket or "title" in ticket
        assert count <= 10

    @pytest.mark.parametrize(
        "make_filter",
        [
            lambda name: DaktelaFilter.eq("name", name),
            lambda name: DaktelaFilter.like("name", f"%{name[1:-1]}%"),
            lambda name: DaktelaFilter.contains("name", name[1:-1]),
            lambda name: DaktelaFilter.starts_with("name", name[:-1]),
            lambda name: DaktelaFilter.ends_with("name", name[1:]),
            lambda name: DaktelaFilter.in_("name", [name]),
        ],
    )
    def test_matching_filter_operators(
        self, live_client: DaktelaClient, make_filter: Callable[[str], DaktelaFilter]
    ) -> None:
        name = self._sample_user_name(live_client)
        query = DaktelaQuery().fields("name").filter(make_filter(name))
        names = [user["name"] for user in live_client.get_all("users", query, max_items=50)]
        assert name in names

    @pytest.mark.parametrize(
        "make_filter",
        [
            lambda name: DaktelaFilter.neq("name", name),
            lambda name: DaktelaFilter.not_like("name", name),
            lambda name: DaktelaFilter.not_contains("name", name),
            lambda name: DaktelaFilter.not_in("name", [name]),
            lambda name: DaktelaFilter.is_null("name"),
        ],
    )
    def test_excluding_filter_operators(
        self, live_client: DaktelaClient, make_filter: Callable[[str], DaktelaFilter]
    ) -> None:
        name = self._sample_user_name(live_client)
        query = DaktelaQuery().fields("name").filter(make_filter(name))
        names = [user["name"] for user in live_client.get_all("users", query, max_items=50)]
        assert name not in names

    @staticmethod
    def _sample_user_name(client: DaktelaClient) -> str:
        query = DaktelaQuery().fields("name").filter(DaktelaFilter.is_not_null("name"))
        user = client.iterate("users", query, max_items=1).first()
        if user is None or len(user["name"]) < 3:
            pytest.skip("no user with a name of at least three characters")
        return str(user["name"])

    def test_login_session(self, live_url: str) -> None:
        client = DaktelaClient.login(
            DaktelaConfig(url=live_url), _env("DAKTELA_USERNAME"), _env("DAKTELA_PASSWORD")
        )
        with client:
            assert client.ping() is True
            assert client.get("users", DaktelaQuery().take(1)).is_success

    def test_download_recording(self, live_client: DaktelaClient) -> None:
        recording = live_client.download_recording(_env("DAKTELA_RECORDING_ACTIVITY"))
        assert recording.size > 0
        assert recording.content_type
