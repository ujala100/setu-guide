"""Conftest for integration tests."""

import pytest

from app.config import settings


@pytest.fixture(scope="session")
def client_with_api_key(app):
    """Test client with API key authentication configured."""
    # Configure API key mode
    settings.auth_method = "api_key"
    settings.api_key = "test-api-key-value"
    # Clear cache to pick up new config
    settings.cache_clear()
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="session")
def client_with_bearer_token(app):
    """Test client with Bearer token authentication configured."""
    # Configure Bearer mode (just set auth method; actual token handling
    # is tested via the test fixtures and test logic)
    settings.auth_method = "bearer"
    settings.cache_clear()
    from fastapi.testclient import TestClient
    return TestClient(app)