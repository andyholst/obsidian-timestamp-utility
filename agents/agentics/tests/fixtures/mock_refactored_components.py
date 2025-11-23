"""
Comprehensive mock fixtures and test infrastructure for refactored components.
Provides mocks for all new architecture components including AgentComposer,
ComposableWorkflows, immutable state management, and collaborative generation.
"""

from unittest.mock import MagicMock, patch, AsyncMock
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from langchain_core.runnables import Runnable
from langchain.tools import Tool

# Import the actual classes to mock
from src.agent_composer import AgentComposer, WorkflowConfig
from src.composable_workflows import ComposableWorkflows
from src.state import CodeGenerationState
from src.models import CodeSpec, TestSpec, ValidationResults
from src.collaborative_generator import CollaborativeGenerator
from src.monitoring import MetricsStore, StructuredLogger, WorkflowTracker, PerformanceMonitor
from src.services import OllamaClient, GitHubClient, MCPClient, ServiceManager
from src.circuit_breaker import CircuitBreaker, ServiceHealthMonitor as HealthMonitor


# ===== CONFIGURATION AND ENVIRONMENT MOCKS =====

def create_mock_llm_config():
    """Create mock LLM configuration."""
    mock_config = MagicMock()
    mock_config.model = "llama3.2:3b"
    mock_config.base_url = "http://localhost:11434"
    mock_config.temperature = 0.7
    mock_config.top_p = 0.9
    mock_config.top_k = 40
    mock_config.min_p = 0.05
    mock_config.presence_penalty = 0.0
    mock_config.num_ctx = 4096
    mock_config.num_predict = 1024
    return mock_config


def create_mock_config():
    """Create mock application configuration."""
    mock_config = MagicMock()
    mock_config.github_token = "mock_github_token_12345"
    mock_config.get_reasoning_llm_config.return_value = create_mock_llm_config()
    mock_config.get_code_llm_config.return_value = create_mock_llm_config()
    return mock_config


def patch_environment_variables():
    """Context manager to patch environment variables."""
    env_vars = {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "llama3.2:3b",
        "GITHUB_TOKEN": "mock_github_token_12345",
        "MCP_SERVER_URL": "http://localhost:3000"
    }
    return patch.dict('os.environ', env_vars)


# ===== SERVICE CLIENT MOCKS =====

def create_mock_ollama_client():
    """Create mock Ollama client with realistic responses."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.name = "ollama"
    mock_client.is_available.return_value = True
    mock_client.invoke.return_value = "Mock LLM response for testing"
    mock_client.health_check = AsyncMock(return_value=True)
    return mock_client


def create_mock_github_client():
    """Create mock GitHub client with realistic responses."""
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.name = "github"
    mock_client.is_available.return_value = True
    mock_client.get_user.return_value = MagicMock(login="testuser", id=12345)
    mock_client.health_check = AsyncMock(return_value=True)

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo"
    mock_repo.name = "repo"
    mock_repo.get_issue.return_value = MagicMock(
        number=1,
        title="Test Issue",
        body="Test body",
        state="open"
    )
    mock_client.get_repo.return_value = mock_repo

    return mock_client


def create_mock_mcp_client():
    """Create mock MCP client with realistic responses."""
    mock_client = MagicMock(spec=MCPClient)
    mock_client.name = "mcp"
    mock_client.is_available.return_value = True
    mock_client.get_context = AsyncMock(return_value="Mock MCP context response")
    mock_client.store_memory = AsyncMock(return_value=None)
    mock_client.retrieve_memory = AsyncMock(return_value="Mock retrieved memory")
    mock_client.health_check = AsyncMock(return_value=True)
    mock_client.initialize = AsyncMock(return_value=None)
    mock_client.close = AsyncMock(return_value=None)

    # Mock tools
    mock_tool = MagicMock(spec=Tool)
    mock_tool.name = "mcp_context_search"
    mock_client.get_tools.return_value = [mock_tool]

    return mock_client


def create_mock_service_manager():
    """Create mock service manager with all clients."""
    mock_manager = MagicMock(spec=ServiceManager)
    mock_manager.ollama_reasoning = create_mock_ollama_client()
    mock_manager.ollama_code = create_mock_ollama_client()
    mock_manager.github = create_mock_github_client()
    mock_manager.mcp = create_mock_mcp_client()
    mock_manager.check_services_health = AsyncMock(return_value={
        "ollama_reasoning": True,
        "ollama_code": True,
        "github": True,
        "mcp": True
    })
    mock_manager.initialize_services = AsyncMock(return_value=None)
    mock_manager.close_services = AsyncMock(return_value=None)
    return mock_manager


# ===== CIRCUIT BREAKER AND HEALTH MONITOR MOCKS =====

def create_mock_circuit_breaker():
    """Create mock circuit breaker that always allows calls."""
    mock_cb = MagicMock(spec=CircuitBreaker)
    mock_cb.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
    mock_cb.state = "closed"
    mock_cb.failure_count = 0
    mock_cb.name = "mock_circuit_breaker"
    return mock_cb


def create_mock_health_monitor():
    """Create mock health monitor."""
    mock_monitor = MagicMock(spec=HealthMonitor)
    mock_monitor.is_service_healthy.return_value = True
    mock_monitor.register_service.return_value = None
    mock_monitor.check_health.return_value = True
    return mock_monitor


def patch_circuit_breakers():
    """Context manager to patch all circuit breaker creation."""
    return patch('src.circuit_breaker.get_circuit_breaker', side_effect=create_mock_circuit_breaker)


def patch_health_monitor():
    """Context manager to patch health monitor."""
    return patch('src.circuit_breaker.get_health_monitor', return_value=create_mock_health_monitor())


# ===== WORKFLOW AND AGENT MOCKS =====

def create_mock_agent(name: str = "mock_agent"):
    """Create mock agent that implements Runnable interface."""
    mock_agent = MagicMock(spec=Runnable)
    mock_agent.name = name

    def mock_invoke(input, config=None):
        # Return modified input with agent processing marker
        if isinstance(input, dict):
            return {**input, f"{name}_processed": True}
        elif hasattr(input, '__dict__'):
            # For CodeGenerationState or similar dataclasses
            return input
        return input

    mock_agent.invoke.side_effect = mock_invoke
    return mock_agent


def create_mock_agent_composer():
    """Create mock AgentComposer with registered agents and tools."""
    mock_composer = MagicMock(spec=AgentComposer)

    # Mock agents registry
    mock_agents = {
        "fetch_issue": create_mock_agent("fetch_issue"),
        "ticket_clarity": create_mock_agent("ticket_clarity"),
        "implementation_planner": create_mock_agent("implementation_planner"),
        "code_extractor": create_mock_agent("code_extractor"),
        "collaborative_generator": create_mock_agent("collaborative_generator"),
        "code_integrator": create_mock_agent("code_integrator"),
        "post_test_runner": create_mock_agent("post_test_runner"),
        "code_reviewer": create_mock_agent("code_reviewer"),
        "output_result": create_mock_agent("output_result")
    }
    mock_composer.agents = mock_agents

    # Mock tools registry
    mock_tools = [
        MagicMock(spec=Tool, name="mcp_context_search"),
        MagicMock(spec=Tool, name="mcp_memory_store")
    ]
    mock_composer.tools = {tool.name: tool for tool in mock_tools}

    # Mock workflows registry
    mock_workflows = {}
    mock_composer.workflows = mock_workflows

    # Mock methods
    mock_composer.register_agent.return_value = None
    mock_composer.register_tool.return_value = None

    def mock_create_workflow(name, config):
        # Create a simple sequential workflow mock
        mock_workflow = MagicMock(spec=Runnable)
        mock_workflow.name = name

        def mock_invoke(input, config=None):
            result = input
            for agent_name in config.agent_names:
                if agent_name in mock_agents:
                    result = mock_agents[agent_name].invoke(result, config)
            return result

        mock_workflow.invoke.side_effect = mock_invoke
        mock_workflows[name] = mock_workflow
        return mock_workflow

    mock_composer.create_workflow.side_effect = mock_create_workflow

    return mock_composer


def create_mock_composable_workflows():
    """Create mock ComposableWorkflows with all sub-workflows."""
    mock_workflows = MagicMock(spec=ComposableWorkflows)

    # Mock individual workflows
    mock_workflows.issue_processing_workflow = create_mock_agent("issue_processing_workflow")
    mock_workflows.code_generation_workflow = create_mock_agent("code_generation_workflow")
    mock_workflows.integration_testing_workflow = create_mock_agent("integration_testing_workflow")
    mock_workflows.full_workflow = create_mock_agent("full_workflow")

    # Mock composer
    mock_workflows.composer = create_mock_agent_composer()

    # Mock service clients
    mock_workflows.llm_reasoning = create_mock_ollama_client()
    mock_workflows.llm_code = create_mock_ollama_client()
    mock_workflows.github_client = create_mock_github_client()
    mock_workflows.mcp_tools = []

    # Mock processing method
    def mock_process_issue(issue_url):
        return {
            "url": issue_url,
            "generated_code": "mock generated code",
            "generated_tests": "mock generated tests",
            "validation_results": {"success": True, "errors": [], "warnings": []}
        }

    mock_workflows.process_issue.side_effect = mock_process_issue

    return mock_workflows


# ===== STATE AND MODEL MOCKS =====

def create_mock_code_spec():
    """Create mock CodeSpec."""
    return CodeSpec(
        language="typescript",
        framework="obsidian",
        dependencies=["uuid"]
    )


def create_mock_test_spec():
    """Create mock TestSpec."""
    return TestSpec(
        test_framework="jest",
        coverage_requirements=["lines > 80%", "functions > 85%"]
    )


def create_mock_validation_results():
    """Create mock ValidationResults."""
    return ValidationResults(
        success=True,
        errors=[],
        warnings=["Minor style issue"]
    )


def create_mock_code_generation_state():
    """Create mock CodeGenerationState with realistic data."""
    return CodeGenerationState(
        issue_url="https://github.com/test/repo/issues/1",
        ticket_content="# Test Issue\n\nTest description",
        title="Test Issue",
        description="Test description for mocking",
        requirements=["Requirement 1", "Requirement 2"],
        acceptance_criteria=["AC 1", "AC 2"],
        code_spec=create_mock_code_spec(),
        test_spec=create_mock_test_spec(),
        implementation_steps=["Step 1", "Step 2"],
        npm_packages=["uuid"],
        manual_implementation_notes="Mock notes",
        generated_code="export class TestClass { test() { return true; } }",
        generated_tests="describe('TestClass', () => { it('should work', () => { expect(true).toBe(true); }); });",
        validation_results=create_mock_validation_results(),
        result={"status": "success"},
        relevant_code_files=[{"path": "src/main.ts", "content": "mock content"}],
        relevant_test_files=[{"path": "src/main.test.ts", "content": "mock test"}],
        feedback={"quality": "good"},
        method_name="test",
        command_id="test-command"
    )


# ===== COLLABORATIVE GENERATOR MOCKS =====

def create_mock_collaborative_generator():
    """Create mock CollaborativeGenerator."""
    mock_gen = MagicMock(spec=CollaborativeGenerator)
    mock_gen.name = "CollaborativeGenerator"
    mock_gen.max_refinement_iterations = 3

    # Mock agents
    mock_gen.code_generator = create_mock_agent("code_generator")
    mock_gen.test_generator = create_mock_agent("test_generator")

    # Mock invoke method
    def mock_invoke(input, config=None):
        if isinstance(input, CodeGenerationState):
            return input.with_code("collaboratively generated code").with_tests("collaboratively generated tests")
        return input

    mock_gen.invoke.side_effect = mock_invoke
    mock_gen.generate_collaboratively.side_effect = mock_invoke

    return mock_gen


# ===== MONITORING AND LOGGING MOCKS =====

def create_mock_metrics_store():
    """Create mock MetricsStore."""
    mock_store = MagicMock(spec=MetricsStore)
    mock_store.increment_counter.return_value = None
    mock_store.record_timer.return_value = None
    mock_store.set_gauge.return_value = None
    mock_store.record_histogram.return_value = None
    mock_store.get_metrics.return_value = {
        "counters": {"test_counter": 5},
        "gauges": {"test_gauge": 10.0},
        "timers": {"test_timer": {"count": 3, "avg": 1.5}},
        "histograms": {"test_histogram": {"count": 2, "avg": 2.0}}
    }
    return mock_store


def create_mock_structured_logger():
    """Create mock StructuredLogger."""
    mock_logger = MagicMock(spec=StructuredLogger)
    mock_logger.name = "mock_logger"
    mock_logger.info.return_value = None
    mock_logger.error.return_value = None
    mock_logger.warning.return_value = None
    mock_logger.debug.return_value = None
    return mock_logger


def create_mock_workflow_tracker():
    """Create mock WorkflowTracker."""
    mock_tracker = MagicMock(spec=WorkflowTracker)
    mock_tracker.start_workflow.return_value = None
    mock_tracker.update_workflow_step.return_value = None
    mock_tracker.complete_workflow.return_value = None
    mock_tracker.fail_workflow.return_value = None
    mock_tracker.get_workflow_status.return_value = {"status": "running"}
    mock_tracker.get_active_workflows.return_value = []
    mock_tracker.get_workflow_metrics.return_value = {"total_workflows": 0}
    return mock_tracker


def create_mock_performance_monitor():
    """Create mock PerformanceMonitor."""
    mock_monitor = MagicMock(spec=PerformanceMonitor)
    mock_monitor.metrics = create_mock_metrics_store()
    mock_monitor.workflow_tracker = create_mock_workflow_tracker()
    mock_monitor.logger = create_mock_structured_logger()

    mock_monitor.time_execution.return_value = lambda func: func
    mock_monitor.track_agent_execution.return_value = lambda func: func
    mock_monitor.track_workflow_progress.return_value = lambda func: func
    mock_monitor.record_circuit_breaker_state.return_value = None
    mock_monitor.get_monitoring_data.return_value = {
        "metrics": {"test": "data"},
        "workflows": {"total": 0},
        "active_workflows": []
    }

    return mock_monitor


# ===== TEST DATA FIXTURES =====

def create_well_formed_ticket_data():
    """Create test data for a well-formed GitHub issue."""
    return {
        "url": "https://github.com/test/repo/issues/1",
        "title": "Implement UUID Generator",
        "description": "Add UUID generation functionality",
        "requirements": ["Generate UUID v7", "Insert at cursor", "Handle no active note"],
        "acceptance_criteria": ["Command in palette", "Valid UUID inserted", "Error on no note"],
        "expected_code": "export class UUIDPlugin { generateUUID() { /* implementation */ } }",
        "expected_tests": "describe('UUIDPlugin', () => { it('generates UUID', () => { /* test */ }); });"
    }


def create_malformed_ticket_data():
    """Create test data for a malformed GitHub issue."""
    return {
        "url": "https://github.com/test/repo/issues/2",
        "title": "",
        "description": "",
        "requirements": [],
        "acceptance_criteria": [],
        "expected_code": None,
        "expected_tests": None
    }


def create_complex_ticket_data():
    """Create test data for a complex multi-step GitHub issue."""
    return {
        "url": "https://github.com/test/repo/issues/3",
        "title": "Implement Advanced Code Analysis",
        "description": "Complex code analysis with multiple components",
        "requirements": ["Parse AST", "Analyze dependencies", "Generate reports", "Handle errors"],
        "acceptance_criteria": ["AST parsed correctly", "Dependencies identified", "Reports generated", "Errors handled"],
        "expected_code": "export class CodeAnalyzer { analyze() { /* complex implementation */ } }",
        "expected_tests": "describe('CodeAnalyzer', () => { it('analyzes code', () => { /* complex tests */ }); });"
    }


def create_validation_failure_scenarios():
    """Create test scenarios for validation failures."""
    return {
        "missing_tests": {
            "code": "export class TestClass { method() { return true; } }",
            "tests": "",
            "expected_errors": ["Untested methods"]
        },
        "wrong_method_names": {
            "code": "export class TestClass { correctMethod() { return true; } }",
            "tests": "describe('TestClass', () => { it('tests wrong method', () => { expect(true).toBe(true); }); });",
            "expected_errors": ["Tests do not reference method"]
        },
        "syntax_errors": {
            "code": "export class TestClass { method() { return true; }",
            "tests": "describe('TestClass', () => { it('should work', () => { expect(true).toBe(true); }); });",
            "expected_errors": ["Syntax error in code"]
        }
    }


# ===== CLEANUP AND RESET UTILITIES =====

class MockStateManager:
    """Manager for resetting global mock state between tests."""

    def __init__(self):
        self.originals = {}
        self.mocks = {}

    def register_mock(self, target: str, mock):
        """Register a mock for later restoration."""
        if target not in self.originals:
            # Store original if not already stored
            try:
                self.originals[target] = __import__(target, fromlist=[''])
            except ImportError:
                self.originals[target] = None

        self.mocks[target] = mock

    def apply_mocks(self):
        """Apply all registered mocks."""
        for target, mock in self.mocks.items():
            # This would need to be implemented based on how mocking is done
            # For now, just store the mapping
            pass

    def reset_all(self):
        """Reset all mocks and restore originals."""
        self.mocks.clear()
        # Note: In a real implementation, this would restore the original modules

    def cleanup(self):
        """Clean up all mock state."""
        self.reset_all()
        self.originals.clear()


# Global mock state manager
_mock_state_manager = MockStateManager()

def get_mock_state_manager():
    """Get the global mock state manager."""
    return _mock_state_manager


def reset_global_mocks():
    """Reset all global mock state."""
    _mock_state_manager.reset_all()


def cleanup_test_mocks():
    """Clean up all test mocks."""
    _mock_state_manager.cleanup()


# ===== CONTEXT MANAGERS FOR COMPREHENSIVE MOCKING =====

def create_comprehensive_mock_context():
    """Create context manager that patches all major components."""
    from contextlib import contextmanager

    @contextmanager
    def comprehensive_mock_context():
        """Context manager providing comprehensive mocking for refactored components."""
        mocks = {
            'src.agent_composer.AgentComposer': patch('src.agent_composer.AgentComposer', return_value=create_mock_agent_composer()),
            'src.composable_workflows.ComposableWorkflows': patch('src.composable_workflows.ComposableWorkflows', return_value=create_mock_composable_workflows()),
            'src.services.ServiceManager': patch('src.services.ServiceManager', return_value=create_mock_service_manager()),
            'src.circuit_breaker.get_circuit_breaker': patch('src.circuit_breaker.get_circuit_breaker', side_effect=create_mock_circuit_breaker),
            'src.circuit_breaker.get_health_monitor': patch('src.circuit_breaker.get_health_monitor', return_value=create_mock_health_monitor()),
            'src.monitoring.get_monitor': patch('src.monitoring.get_monitor', return_value=create_mock_performance_monitor()),
            'src.monitoring.structured_log': patch('src.monitoring.structured_log', side_effect=create_mock_structured_logger)
        }

        # Start all patches
        started_mocks = []
        try:
            for target, patcher in mocks.items():
                started_mocks.append(patcher.start())
            yield
        finally:
            # Stop all patches in reverse order
            for mock in reversed(started_mocks):
                mock.stop()

    return comprehensive_mock_context()


# ===== UTILITY FUNCTIONS =====

def create_mock_response_for_scenario(scenario: str) -> Dict[str, Any]:
    """Create appropriate mock responses based on test scenario."""
    scenarios = {
        "success": {
            "generated_code": "export class SuccessClass { success() { return true; } }",
            "generated_tests": "describe('SuccessClass', () => { it('succeeds', () => { expect(true).toBe(true); }); });",
            "validation_results": {"success": True, "errors": [], "warnings": []}
        },
        "failure": {
            "generated_code": "export class FailureClass { fail() { throw new Error('fail'); } }",
            "generated_tests": "describe('FailureClass', () => { it('fails', () => { expect(() => { throw new Error(); }).toThrow(); }); });",
            "validation_results": {"success": False, "errors": ["Test failure"], "warnings": []}
        },
        "partial": {
            "generated_code": "export class PartialClass { partial() { return 'partial'; } }",
            "generated_tests": "",  # Missing tests
            "validation_results": {"success": False, "errors": ["Missing tests"], "warnings": []}
        }
    }

    return scenarios.get(scenario, scenarios["success"])


def assert_mock_called_with_expected(mock, expected_calls):
    """Assert that a mock was called with expected arguments."""
    actual_calls = mock.call_args_list
    assert len(actual_calls) == len(expected_calls), f"Expected {len(expected_calls)} calls, got {len(actual_calls)}"

    for i, (actual, expected) in enumerate(zip(actual_calls, expected_calls)):
        if isinstance(expected, dict):
            # Check if key-value pairs match
            for key, value in expected.items():
                assert actual[1].get(key) == value, f"Call {i}: expected {key}={value}, got {actual[1].get(key)}"
        else:
            return scenarios.get(scenario, scenarios["success"])


def create_enhanced_mcp_client_mock():
    """Create an enhanced MCP client mock with comprehensive tool support and error handling."""
    mock_client = MagicMock(spec=MCPClient)
    mock_client.name = "mcp"
    mock_client.is_available.return_value = True
    mock_client.initialize = AsyncMock(return_value=None)
    mock_client.close = AsyncMock(return_value=None)
    mock_client.health_check = AsyncMock(return_value=True)

    # Enhanced context responses
    context_responses = {
        "code_review": "The code follows best practices with proper error handling and type safety.",
        "architecture": "This appears to be a layered architecture with clear separation of concerns.",
        "security": "No obvious security vulnerabilities detected in the provided code.",
        "performance": "The code is optimized for the given use case with efficient algorithms."
    }

    def mock_get_context(query, max_tokens=4096):
        # Return context based on query keywords
        for key, response in context_responses.items():
            if key in query.lower():
                return response
        return "General context information retrieved from MCP server."

    mock_client.get_context = AsyncMock(side_effect=mock_get_context)

    # Enhanced memory operations
    memory_store = {}

    def mock_store_memory(key, value):
        memory_store[key] = value

    def mock_retrieve_memory(key):
        return memory_store.get(key, f"No memory found for key: {key}")

    mock_client.store_memory = AsyncMock(side_effect=mock_store_memory)
    mock_client.retrieve_memory = AsyncMock(side_effect=mock_retrieve_memory)

    # Comprehensive tool set
    tools = [
        MagicMock(spec=Tool, name="mcp_context_search", description="Search for contextual information"),
        MagicMock(spec=Tool, name="mcp_memory_store", description="Store key-value pairs in memory"),
        MagicMock(spec=Tool, name="mcp_memory_retrieve", description="Retrieve stored values from memory"),
        MagicMock(spec=Tool, name="mcp_code_analysis", description="Analyze code for patterns and issues"),
        MagicMock(spec=Tool, name="mcp_documentation_search", description="Search documentation and references"),
        MagicMock(spec=Tool, name="mcp_test_generation", description="Generate test cases for code"),
        MagicMock(spec=Tool, name="mcp_dependency_analysis", description="Analyze code dependencies"),
        MagicMock(spec=Tool, name="mcp_security_scan", description="Scan code for security vulnerabilities")
    ]

    # Set up tool functions
    for tool in tools:
        if tool.name == "mcp_code_analysis":
            tool.func = lambda code: f"Analysis of: {code[:50]}..."
        elif tool.name == "mcp_documentation_search":
            tool.func = lambda query: f"Documentation for: {query}"
        elif tool.name == "mcp_test_generation":
            tool.func = lambda code: f"Generated tests for: {code[:30]}..."
        elif tool.name == "mcp_dependency_analysis":
            tool.func = lambda code: "Dependencies: React, TypeScript, Jest"
        elif tool.name == "mcp_security_scan":
            tool.func = lambda code: "Security scan: No vulnerabilities found"

    mock_client.get_tools.return_value = tools

    return mock_client


def create_mcp_error_scenarios():
    """Create MCP client mocks that simulate various error conditions."""

    # Connection error
    connection_error_mock = MagicMock(spec=MCPClient)
    connection_error_mock.is_available.return_value = False
    connection_error_mock.get_context = AsyncMock(side_effect=ConnectionError("Cannot connect to MCP server"))
    connection_error_mock.store_memory = AsyncMock(side_effect=ConnectionError("Cannot connect to MCP server"))
    connection_error_mock.retrieve_memory = AsyncMock(side_effect=ConnectionError("Cannot connect to MCP server"))
    connection_error_mock.health_check = AsyncMock(return_value=False)

    # Timeout error
    timeout_error_mock = MagicMock(spec=MCPClient)
    timeout_error_mock.is_available.return_value = True
    timeout_error_mock.get_context = AsyncMock(side_effect=TimeoutError("MCP request timed out"))
    timeout_error_mock.store_memory = AsyncMock(side_effect=TimeoutError("MCP request timed out"))
    timeout_error_mock.retrieve_memory = AsyncMock(side_effect=TimeoutError("MCP request timed out"))
    timeout_error_mock.health_check = AsyncMock(return_value=True)

    # Authentication error
    auth_error_mock = MagicMock(spec=MCPClient)
    auth_error_mock.is_available.return_value = False
    auth_error_mock.get_context = AsyncMock(side_effect=Exception("MCP authentication failed"))
    auth_error_mock.store_memory = AsyncMock(side_effect=Exception("MCP authentication failed"))
    auth_error_mock.retrieve_memory = AsyncMock(side_effect=Exception("MCP authentication failed"))
    auth_error_mock.health_check = AsyncMock(return_value=False)

    # Server error
    server_error_mock = MagicMock(spec=MCPClient)
    server_error_mock.is_available.return_value = True
    server_error_mock.get_context = AsyncMock(side_effect=Exception("MCP server internal error"))
    server_error_mock.store_memory = AsyncMock(side_effect=Exception("MCP server internal error"))
    server_error_mock.retrieve_memory = AsyncMock(side_effect=Exception("MCP server internal error"))
    server_error_mock.health_check = AsyncMock(return_value=False)

    return {
        "connection": connection_error_mock,
        "timeout": timeout_error_mock,
        "auth": auth_error_mock,
        "server": server_error_mock
    }


def create_mcp_with_rate_limiting():
    """Create an MCP client mock that simulates rate limiting."""
    mock_client = create_enhanced_mcp_client_mock()

    call_count = 0
    rate_limit_threshold = 10

    def rate_limited_get_context(query, max_tokens=4096):
        nonlocal call_count
        call_count += 1
        if call_count > rate_limit_threshold:
            raise Exception("MCP rate limit exceeded. Please try again later.")
        return "Context information retrieved successfully."

    def rate_limited_store_memory(key, value):
        nonlocal call_count
        call_count += 1
        if call_count > rate_limit_threshold:
            raise Exception("MCP rate limit exceeded. Please try again later.")

    def rate_limited_retrieve_memory(key):
        nonlocal call_count
        call_count += 1
        if call_count > rate_limit_threshold:
            raise Exception("MCP rate limit exceeded. Please try again later.")
        return f"Retrieved: {key}"

    mock_client.get_context = AsyncMock(side_effect=rate_limited_get_context)
    mock_client.store_memory = AsyncMock(side_effect=rate_limited_store_memory)
    mock_client.retrieve_memory = AsyncMock(side_effect=rate_limited_retrieve_memory)

    return mock_client


def create_mcp_streaming_responses():
    """Create an MCP client mock that supports streaming responses."""
    mock_client = create_enhanced_mcp_client_mock()

    async def mock_stream_context(query, max_tokens=4096):
        """Mock streaming context retrieval."""
        chunks = [
            "Starting context analysis...",
            f"Processing query: {query[:30]}...",
            "Gathering relevant information...",
            "Compiling response...",
            "Context retrieval complete."
        ]
        for chunk in chunks:
            yield chunk

    mock_client.stream_context = mock_stream_context

    return mock_client
