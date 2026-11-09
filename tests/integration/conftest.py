"""Conftest for integration tests.

Import the app fixture from the main conftest and add API key/Bearer fixtures.
"""

import pytest

from app.config import get_settings
from app.api.main import app  # noqa: F401
from tests.conftest import client  # noqa: F401, for the client fixture registration


@pytest.fixture(scope="session")
def app():
    """App fixture for integration test suites."""
    from app.api.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client_with_api_key(app):
    """Test client with API key authentication configured."""
    # Configure API key mode
    settings = get_settings()
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
    settings = get_settings()
    settings.auth_method = "bearer"
    settings.cache_clear()
    from fastapi.testclient import TestClient
    return TestClient(app)