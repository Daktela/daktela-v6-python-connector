"""Tests for DaktelaClient."""

import json
from urllib.parse import unquote

import pytest
from pytest_httpx import HTTPXMock

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaFilter,
    DaktelaNotFoundException,
    DaktelaQuery,
    DaktelaSort,
    DaktelaUnauthorizedException,
    RetryConfig,
)


class TestDaktelaClient:
    """Tests for DaktelaClient class."""

    @pytest.fixture
    def config(self) -> DaktelaConfig:
        """Create test configuration."""
        return DaktelaConfig(
            url="test.daktela.com",
            access_token="test-token",
        )

    @pytest.fixture
    def client(self, config: DaktelaConfig) -> DaktelaClient:
        """Create test client."""
        return DaktelaClient(config)

    def test_get_simple(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test simple GET request."""
        httpx_mock.add_response(
            url="https://test.daktela.com/api/v6/tickets",
            json={"result": {"data": [{"name": "Test"}], "total": 1}},
        )

        response = client.get("tickets")

        assert response.is_success
        assert len(response) == 1
        assert response.as_list()[0]["name"] == "Test"

    def test_get_with_query(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test GET request with query."""
        httpx_mock.add_response(
            json={"result": {"data": [{"name": "Test"}], "total": 1}},
        )

        query = (
            DaktelaQuery()
            .fields("name", "title")
            .filter(DaktelaFilter.eq("stage", "OPEN"))
            .sort(DaktelaSort.desc("created"))
            .take(50)
        )
        response = client.get("tickets", query)

        assert response.is_success
        request = httpx_mock.get_request()
        assert request is not None
        url_str = unquote(str(request.url))
        assert "fields[0]=name" in url_str
        assert "fields[1]=title" in url_str
        assert "take=50" in url_str

    def test_get_single(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test GET request for single resource."""
        httpx_mock.add_response(
            url="https://test.daktela.com/api/v6/tickets/123",
            json={"result": {"data": {"name": "Test Ticket", "title": "123"}}},
        )

        response = client.get("tickets/123")

        assert response.is_success
        assert response.get("name") == "Test Ticket"

    def test_post(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test POST request."""
        httpx_mock.add_response(
            method="POST",
            json={"result": {"data": {"name": "new-ticket"}}},
        )

        response = client.post("tickets", {"title": "New Ticket"})

        assert response.is_success
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["title"] == "New Ticket"

    def test_put(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test PUT request."""
        httpx_mock.add_response(
            method="PUT",
            json={"result": {"data": {"name": "ticket-123"}}},
        )

        response = client.put("tickets/123", {"title": "Updated"})

        assert response.is_success
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "PUT"

    def test_delete(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test DELETE request."""
        httpx_mock.add_response(
            method="DELETE",
            json={"result": {"data": None}},
        )

        response = client.delete("tickets/123")

        assert response.is_success
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "DELETE"

    def test_unauthorized_error(
        self, client: DaktelaClient, httpx_mock: HTTPXMock
    ) -> None:
        """Test 401 error handling."""
        httpx_mock.add_response(
            status_code=401,
            json={"error": ["Invalid token"]},
        )

        with pytest.raises(DaktelaUnauthorizedException):
            client.get("tickets")

    def test_not_found_error(
        self, client: DaktelaClient, httpx_mock: HTTPXMock
    ) -> None:
        """Test 404 error handling."""
        httpx_mock.add_response(
            status_code=404,
            json={"error": ["Resource not found"]},
        )

        with pytest.raises(DaktelaNotFoundException):
            client.get("tickets/999")

    def test_auth_header(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test that auth header is sent."""
        httpx_mock.add_response(json={"result": {"data": []}})

        client.get("tickets")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["X-AUTH-TOKEN"] == "test-token"

    def test_context_manager(self, config: DaktelaConfig, httpx_mock: HTTPXMock) -> None:
        """Test client as context manager."""
        httpx_mock.add_response(json={"result": {"data": []}})

        with DaktelaClient(config) as client:
            response = client.get("tickets")
            assert response.is_success

    def test_ping_success(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test successful ping."""
        httpx_mock.add_response(
            url="https://test.daktela.com/api/v6/ping",
            json={"result": "pong"},
        )

        assert client.ping() is True

    def test_ping_failure(self, config: DaktelaConfig, httpx_mock: HTTPXMock) -> None:
        """Test failed ping."""
        # Use client with retries disabled to avoid multiple requests
        client = DaktelaClient(config, retry_config=RetryConfig.disabled())
        httpx_mock.add_response(
            url="https://test.daktela.com/api/v6/ping",
            status_code=500,
        )

        assert client.ping() is False

    def test_health_check(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test health check."""
        httpx_mock.add_response(
            url="https://test.daktela.com/api/v6/ping",
            json={"result": "pong"},
        )

        result = client.health_check()

        assert result["healthy"] is True
        assert "latency_ms" in result
        assert result["status_code"] == 200

    def test_file_endpoint_uses_raw_base_url(self, client: DaktelaClient, httpx_mock: HTTPXMock) -> None:
        """Test health check."""
        httpx_mock.add_response(
            url="https://test.daktela.com/file/recording/activity_123456789",
            content=b'x\00',
            headers={'content-type': 'audio/opus', 'filename': 'activity_123456789.opus'}
        )

        result = client.get('file/recording/activity_123456789')

        assert result.is_success
