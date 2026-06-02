"""Unit test configuration and fixtures."""

import os
import pytest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests."""
    import src.services
    import src.config
    src.services._service_manager = None
    src.config._config = None
    yield
    src.services._service_manager = None
    src.config._config = None


@pytest.fixture(autouse=True)
def mock_github_token():
    """Mock GITHUB_TOKEN for unit tests."""
    original = os.environ.get("GITHUB_TOKEN")
    os.environ["GITHUB_TOKEN"] = "test_token"
    yield
    if original is not None:
        os.environ["GITHUB_TOKEN"] = original
    else:
        os.environ.pop("GITHUB_TOKEN", None)


def pytest_collection_finish(session):
    print(f"\n=== Collected {len(session.items)} tests before running ===")
