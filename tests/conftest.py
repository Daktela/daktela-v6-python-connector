"""Pytest fixtures for Daktela SDK tests."""

import pytest

from daktela import DaktelaClient, DaktelaConfig


@pytest.fixture
def config() -> DaktelaConfig:
    """Create a test configuration."""
    return DaktelaConfig(
        url="test.daktela.com",
        access_token="test-token",
    )


@pytest.fixture
def client(config: DaktelaConfig) -> DaktelaClient:
    """Create a test client."""
    return DaktelaClient(config)
