"""Integration tests against a live Daktela instance.

Run with: pytest tests/integration/ -v

Requires environment variables:
- DAKTELA_URL: Your Daktela instance URL
- DAKTELA_ACCESS_TOKEN: Your access token
"""

import os

import pytest

from daktela import DaktelaClient, DaktelaConfig, DaktelaFilter, DaktelaQuery


@pytest.fixture
def live_client() -> DaktelaClient:
    """Create a client for live testing."""
    url = os.environ.get("DAKTELA_URL")
    token = os.environ.get("DAKTELA_ACCESS_TOKEN")

    if not url or not token:
        pytest.skip("DAKTELA_URL and DAKTELA_ACCESS_TOKEN must be set")

    config = DaktelaConfig(url=url, access_token=token)
    return DaktelaClient(config)


class TestLiveAPI:
    """Integration tests against live Daktela API."""

    def test_ping(self, live_client: DaktelaClient) -> None:
        """Test ping endpoint."""
        assert live_client.ping() is True

    def test_health_check(self, live_client: DaktelaClient) -> None:
        """Test health check."""
        result = live_client.health_check()
        assert result["healthy"] is True
        assert result["latency_ms"] > 0

    def test_get_users(self, live_client: DaktelaClient) -> None:
        """Test fetching users."""
        query = DaktelaQuery().take(5)
        response = live_client.get("users", query)
        assert response.is_success

    def test_iterate_tickets(self, live_client: DaktelaClient) -> None:
        """Test iterating through tickets."""
        query = DaktelaQuery().take(10)
        count = 0
        for ticket in live_client.iterate("tickets", query, page_size=5, max_items=10):
            count += 1
            assert "name" in ticket or "title" in ticket
        assert count <= 10
