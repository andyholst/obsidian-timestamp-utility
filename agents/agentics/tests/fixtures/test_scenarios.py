"""
Reusable test scenarios and fixtures for comprehensive testing.

This module provides common test scenarios that can be used across different
test files to ensure consistent testing patterns and reduce code duplication.
"""

from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, List, Optional
import pytest

from .mock_github_responses import (
    create_well_formed_ticket_data,
    create_malformed_ticket_data,
    create_complex_ticket_data,
    create_validation_failure_scenarios
)
from .mock_llm_responses import create_process_llm_mock_responses, create_code_generator_mock_responses
from .mock_refactored_components import create_mock_service_manager


class TestScenario:
    """Base class for test scenarios."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def setup(self):
        """Set up the test scenario."""
        pass

    def teardown(self):
        """Clean up after the test scenario."""
        pass

    def get_mocks(self) -> Dict[str, Any]:
        """Get the mocks for this scenario."""
        return {}


class GitHubIssueProcessingScenario(TestScenario):
    """Test scenario for GitHub issue processing workflows."""

    def __init__(self, ticket_type: str = "well_formed"):
        super().__init__(
            f"github_issue_{ticket_type}",
            f"Test scenario for processing {ticket_type} GitHub issues"
        )
        self.ticket_type = ticket_type

    def get_mocks(self):
        """Get mocks for GitHub issue processing."""
        ticket_data = {
            "well_formed": create_well_formed_ticket_data(),
            "malformed": create_malformed_ticket_data(),
            "complex": create_complex_ticket_data()
        }.get(self.ticket_type, create_well_formed_ticket_data())

        return {
            "ticket_data": ticket_data,
            "llm_responses": create_process_llm_mock_responses(),
            "service_manager": create_mock_service_manager()
        }


class CodeGenerationScenario(TestScenario):
    """Test scenario for code generation workflows."""

    def __init__(self, complexity: str = "simple"):
        super().__init__(
            f"code_generation_{complexity}",
            f"Test scenario for {complexity} code generation"
        )
        self.complexity = complexity

    def get_mocks(self):
        """Get mocks for code generation."""
        return {
            "llm_responses": create_code_generator_mock_responses(),
            "service_manager": create_mock_service_manager(),
            "validation_scenarios": create_validation_failure_scenarios()
        }


class ErrorHandlingScenario(TestScenario):
    """Test scenario for error handling and recovery."""

    def __init__(self, error_type: str = "service_failure"):
        super().__init__(
            f"error_handling_{error_type}",
            f"Test scenario for handling {error_type} errors"
        )
        self.error_type = error_type

    def get_mocks(self):
        """Get mocks for error handling."""
        error_mocks = {
            "service_failure": self._create_service_failure_mocks(),
            "network_timeout": self._create_network_timeout_mocks(),
            "rate_limiting": self._create_rate_limiting_mocks(),
            "authentication": self._create_auth_failure_mocks()
        }.get(self.error_type, self._create_service_failure_mocks())

        return error_mocks

    def _create_service_failure_mocks(self):
        """Create mocks for service failure scenarios."""
        from .mock_refactored_components import create_mcp_error_scenarios
        from .mock_llm_responses import create_llm_error_scenarios

        return {
            "mcp_errors": create_mcp_error_scenarios(),
            "llm_errors": create_llm_error_scenarios(),
            "service_manager": create_mock_service_manager()
        }

    def _create_network_timeout_mocks(self):
        """Create mocks for network timeout scenarios."""
        from .mock_llm_responses import create_llm_error_scenarios

        return {
            "llm_errors": create_llm_error_scenarios()["timeout"],
            "network_patches": self._patch_network_operations()
        }

    def _create_rate_limiting_mocks(self):
        """Create mocks for rate limiting scenarios."""
        from .mock_refactored_components import create_mcp_with_rate_limiting
        from .mock_github_responses import create_github_client_with_errors

        return {
            "mcp_rate_limited": create_mcp_with_rate_limiting(),
            "github_rate_limited": create_github_client_with_errors()
        }

    def _create_auth_failure_mocks(self):
        """Create mocks for authentication failure scenarios."""
        from .mock_github_responses import create_github_error_responses

        return {
            "github_auth_errors": create_github_error_responses()["auth"],
            "service_manager": create_mock_service_manager()
        }

    def _patch_network_operations(self):
        """Patch network operations to simulate timeouts."""
        import asyncio
        from unittest.mock import patch

        async def timeout_operation(*args, **kwargs):
            await asyncio.sleep(30)  # Long timeout
            raise TimeoutError("Network operation timed out")

        return patch('asyncio.AbstractEventLoop.run_in_executor', side_effect=timeout_operation)


class PerformanceScenario(TestScenario):
    """Test scenario for performance testing."""

    def __init__(self, load_level: str = "normal"):
        super().__init__(
            f"performance_{load_level}",
            f"Test scenario for {load_level} load performance testing"
        )
        self.load_level = load_level

    def get_mocks(self):
        """Get mocks for performance testing."""
        from .mock_llm_responses import create_llm_batch_responses
        from .mock_refactored_components import create_mcp_streaming_responses

        return {
            "batch_responses": create_llm_batch_responses(),
            "streaming_responses": create_mcp_streaming_responses(),
            "service_manager": create_mock_service_manager()
        }


class IntegrationScenario(TestScenario):
    """Test scenario for integration testing."""

    def __init__(self, integration_type: str = "full_workflow"):
        super().__init__(
            f"integration_{integration_type}",
            f"Test scenario for {integration_type} integration"
        )
        self.integration_type = integration_type

    def get_mocks(self):
        """Get mocks for integration testing."""
        return {
            "service_manager": create_mock_service_manager(),
            "github_client": create_well_formed_ticket_data(),
            "llm_responses": create_process_llm_mock_responses()
        }


# Predefined test scenarios
WELL_FORMED_ISSUE_SCENARIO = GitHubIssueProcessingScenario("well_formed")
MALFORMED_ISSUE_SCENARIO = GitHubIssueProcessingScenario("malformed")
COMPLEX_ISSUE_SCENARIO = GitHubIssueProcessingScenario("complex")

SIMPLE_CODE_GENERATION = CodeGenerationScenario("simple")
COMPLEX_CODE_GENERATION = CodeGenerationScenario("complex")

SERVICE_FAILURE_ERROR = ErrorHandlingScenario("service_failure")
NETWORK_TIMEOUT_ERROR = ErrorHandlingScenario("network_timeout")
RATE_LIMITING_ERROR = ErrorHandlingScenario("rate_limiting")
AUTHENTICATION_ERROR = ErrorHandlingScenario("authentication")

NORMAL_LOAD_PERFORMANCE = PerformanceScenario("normal")
HIGH_LOAD_PERFORMANCE = PerformanceScenario("high")

FULL_WORKFLOW_INTEGRATION = IntegrationScenario("full_workflow")
PARTIAL_INTEGRATION = IntegrationScenario("partial")


def get_scenario_by_name(name: str) -> Optional[TestScenario]:
    """Get a test scenario by name."""
    scenarios = {
        "well_formed_issue": WELL_FORMED_ISSUE_SCENARIO,
        "malformed_issue": MALFORMED_ISSUE_SCENARIO,
        "complex_issue": COMPLEX_ISSUE_SCENARIO,
        "simple_code_gen": SIMPLE_CODE_GENERATION,
        "complex_code_gen": COMPLEX_CODE_GENERATION,
        "service_failure": SERVICE_FAILURE_ERROR,
        "network_timeout": NETWORK_TIMEOUT_ERROR,
        "rate_limiting": RATE_LIMITING_ERROR,
        "auth_error": AUTHENTICATION_ERROR,
        "normal_performance": NORMAL_LOAD_PERFORMANCE,
        "high_performance": HIGH_LOAD_PERFORMANCE,
        "full_integration": FULL_WORKFLOW_INTEGRATION,
        "partial_integration": PARTIAL_INTEGRATION
    }

    return scenarios.get(name)


@pytest.fixture(params=[
    "well_formed_issue",
    "malformed_issue",
    "complex_issue",
    "service_failure",
    "network_timeout"
])
def standard_test_scenarios(request):
    """Parameterized fixture providing standard test scenarios."""
    scenario_name = request.param
    scenario = get_scenario_by_name(scenario_name)
    if scenario:
        scenario.setup()
        yield scenario
        scenario.teardown()


@pytest.fixture
def custom_scenario():
    """Fixture for creating custom test scenarios."""
    def create_scenario(scenario_class, **kwargs):
        scenario = scenario_class(**kwargs)
        scenario.setup()
        return scenario

    return create_scenario


def run_scenario_test(scenario: TestScenario, test_function):
    """Helper function to run a test with a given scenario."""
    try:
        scenario.setup()
        mocks = scenario.get_mocks()
        test_function(**mocks)
    finally:
        scenario.teardown()


# Utility functions for common test patterns

def assert_service_health_status(service_manager, expected_status: Dict[str, bool]):
    """Assert that service health matches expected status."""
    import asyncio
    async def check_health():
        return await service_manager.check_services_health()

    result = asyncio.run(check_health())
    for service, expected in expected_status.items():
        assert result.get(service, False) == expected, f"Service {service} health mismatch"


def assert_mock_called_with_workflow(mock_agent, expected_workflow_steps: List[str]):
    """Assert that a mock agent was called with expected workflow steps."""
    calls = mock_agent.invoke.call_args_list
    for i, expected_step in enumerate(expected_workflow_steps):
        if i < len(calls):
            call_args = calls[i][0] if calls[i][0] else []
            assert expected_step in str(call_args), f"Step {i} mismatch: expected {expected_step}"


def assert_error_handling(mock_service, error_type: str, expected_behavior):
    """Assert proper error handling for a given error type."""
    try:
        # This would depend on the specific service and error type
        if hasattr(mock_service, error_type):
            getattr(mock_service, error_type)()
        expected_behavior()
    except Exception as e:
        # Verify error is handled appropriately
        assert isinstance(e, expected_behavior), f"Unexpected error type: {type(e)}"