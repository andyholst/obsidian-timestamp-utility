"""
Mock circuit breaker utilities for testing.
These mocks prevent circuit breaker state from persisting between tests.
"""

from unittest.mock import MagicMock, patch
from src.circuit_breaker import CircuitBreaker


def create_mock_circuit_breaker():
    """Create a mock circuit breaker that always allows calls through."""
    mock_cb = MagicMock(spec=CircuitBreaker)
    mock_cb.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
    mock_cb.state = "closed"
    mock_cb.failure_count = 0
    return mock_cb


def patch_circuit_breakers():
    """Context manager to patch all circuit breaker creation."""
    return patch('src.circuit_breaker.get_circuit_breaker', side_effect=create_mock_circuit_breaker)


def mock_circuit_breaker_for_agent(agent_instance):
    """Mock the circuit breaker for a specific agent instance."""
    agent_instance.circuit_breaker = create_mock_circuit_breaker()
    return agent_instance