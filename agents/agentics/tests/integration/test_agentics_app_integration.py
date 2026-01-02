"""
Enhanced Integration Tests for AgenticsApp and New Architecture Components.

These tests validate the AgenticsApp class and new architecture components working together
in realistic scenarios with real services (Ollama, GitHub, MCP) where available.

Tests cover:
1. AgenticsApp initialization with real services and configuration
2. End-to-end issue processing workflow through AgenticsApp
3. Batch processing with real concurrent execution
4. Service health monitoring integration
5. Error handling and recovery with real services
6. Configuration loading and validation in integration scenarios
"""

import pytest
import os
import asyncio
import json
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

# Import the new architecture components
from src.agentics import AgenticsApp
from src.config import AgenticsConfig, init_config
from src.services import init_services, ServiceManager
from src.workflows import init_workflows, WorkflowManager
from src.monitoring import ServiceHealthMonitor, structured_log
from src.exceptions import AgenticsError, ServiceUnavailableError, ValidationError
from src.utils import validate_github_url




class TestAgenticsAppIntegration:
    """Integration tests for AgenticsApp with real services and components."""

    @pytest.fixture
    async def agentics_app(self):
        """Fixture for real AgenticsApp instance with initialized services."""
        # Ensure required environment variables are set

        app = AgenticsApp()
        await app.initialize()
        yield app
        await app.shutdown()

    @pytest.fixture
    def test_issue_url(self):
        """Fixture for test issue URL from environment."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        return f"{test_repo_url}/issues/20"

    @pytest.fixture
    def test_issue_urls(self):
        """Fixture for multiple test issue URLs."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        return [
            f"{test_repo_url}/issues/20",
            f"{test_repo_url}/issues/22"
        ]

    @pytest.mark.integration
    async def test_initialize_success(self):
        """Test successful initialization with real services."""
        # Use real AgenticsConfig with environment variables
        config = AgenticsConfig(
            github_token=os.environ.get('GITHUB_TOKEN', 'test_token'),
            ollama_host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'),
            ollama_reasoning_model=os.environ.get('OLLAMA_REASONING_MODEL', 'qwen2.5:14b'),
            ollama_code_model=os.environ.get('OLLAMA_CODE_MODEL', 'qwen2.5-coder:14b')
        )

        app = AgenticsApp(config)

        await app.initialize()

        assert app._initialized is True
        assert app.service_manager is not None
        assert app.composable_workflows is not None
        # Assert real initialization - services should be initialized
        assert app.service_manager.ollama_reasoning is not None
        assert app.service_manager.ollama_code is not None
        assert app.service_manager.github is not None

    @pytest.mark.integration
    async def test_agentics_app_initialization_with_real_services(self, agentics_app):
        """Test AgenticsApp initialization with real services and configuration."""
        # Verify app is initialized
        assert agentics_app._initialized is True
        assert agentics_app.config is not None
        assert agentics_app.service_manager is not None
        assert agentics_app.composable_workflows is not None

        # Verify services are initialized
        assert agentics_app.service_manager.ollama_reasoning is not None
        assert agentics_app.service_manager.ollama_code is not None
        assert agentics_app.service_manager.github is not None

        # Verify composable workflows are initialized
        assert agentics_app.composable_workflows.issue_processing_workflow is not None
        assert agentics_app.composable_workflows.code_generation_workflow is not None
        assert agentics_app.composable_workflows.integration_testing_workflow is not None
        assert agentics_app.composable_workflows.full_workflow is not None

        # Verify service health checks passed during initialization
        health_status = await agentics_app.get_service_health()
        assert isinstance(health_status, dict)
        assert "ollama_reasoning" in health_status
        assert "ollama_code" in health_status
        assert "github" in health_status

    @pytest.mark.integration
    async def test_end_to_end_issue_processing_workflow(self, agentics_app, test_issue_url):
        """Test end-to-end issue processing workflow through AgenticsApp."""
        # Process the issue
        result = await agentics_app.process_issue(test_issue_url)

        # Verify result structure
        assert isinstance(result, dict)
        assert "refined_ticket" in result
        assert "generated_code" in result
        assert "generated_tests" in result

        # Verify ticket structure
        refined_ticket = result["refined_ticket"]
        assert "title" in refined_ticket
        assert "description" in refined_ticket
        assert "requirements" in refined_ticket
        assert "acceptance_criteria" in refined_ticket
        assert isinstance(refined_ticket["requirements"], list)
        assert isinstance(refined_ticket["acceptance_criteria"], list)
        assert len(refined_ticket["requirements"]) > 0
        assert len(refined_ticket["acceptance_criteria"]) > 0

        # Verify code generation
        assert len(result["generated_code"]) > 0
        assert "function" in result["generated_code"].lower() or "class" in result["generated_code"].lower()

        # Verify test generation
        assert len(result["generated_tests"]) > 0
        assert "describe" in result["generated_tests"] or "test" in result["generated_tests"]

    @pytest.mark.integration
    async def test_batch_processing_with_concurrent_execution(self, agentics_app, test_issue_urls):
        """Test batch processing with real concurrent execution."""
        # Process multiple issues concurrently
        batch_result = await agentics_app.process_issues_batch(test_issue_urls)

        # Verify batch result structure
        assert isinstance(batch_result, dict)
        assert "total_issues" in batch_result
        assert "successful" in batch_result
        assert "failed" in batch_result
        assert "results" in batch_result

        assert batch_result["total_issues"] == len(test_issue_urls)
        assert isinstance(batch_result["results"], list)
        assert len(batch_result["results"]) == len(test_issue_urls)

        # Verify individual results
        for result in batch_result["results"]:
            assert "issue_url" in result
            if result.get("success", False):
                assert "refined_ticket" in result
                assert "generated_code" in result
                assert "generated_tests" in result
            else:
                assert "error" in result

        # At least one should succeed in integration test
        assert batch_result["successful"] >= 1

    @pytest.mark.integration
    async def test_service_health_monitoring_integration(self, agentics_app):
        """Test service health monitoring integration."""
        # Get health status
        health_status = await agentics_app.get_service_health()

        # Verify all expected services are checked
        expected_services = ["ollama_reasoning", "ollama_code", "github", "mcp"]
        for service in expected_services:
            assert service in health_status
            assert isinstance(health_status[service], bool)

        # Verify health monitor is tracking services
        from src.monitoring import get_monitor
        monitor = get_monitor()
        monitoring_data = monitor.get_monitoring_data()

        # Should have workflow tracking data
        assert "workflows" in monitoring_data
        assert "active_workflows" in monitoring_data

    @pytest.mark.integration
    async def test_error_handling_and_recovery_with_real_services(self, agentics_app):
        """Test error handling and recovery with real services."""
        # Test with invalid URL
        with pytest.raises(ValidationError):
            await agentics_app.process_issue("https://invalid-url/issues/1")

        # Test with non-existent issue
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        if test_repo_url:
            nonexistent_url = f"{test_repo_url}/issues/999999"
            with pytest.raises(AgenticsError):
                await agentics_app.process_issue(nonexistent_url)

        # Test batch processing with mixed valid/invalid URLs
        valid_urls = [f"{test_repo_url}/issues/20"] if test_repo_url else []
        invalid_urls = ["https://invalid-url/issues/1"]
        mixed_urls = valid_urls + invalid_urls

        # Should raise ValidationError for invalid URLs in batch
        with pytest.raises(ValidationError):
            await agentics_app.process_issues_batch(mixed_urls)

    @pytest.mark.integration
    async def test_configuration_loading_and_validation(self):
        """Test configuration loading and validation in integration scenarios."""
        # Test with environment variables
        original_token = os.getenv('GITHUB_TOKEN')
        original_host = os.getenv('OLLAMA_HOST')

        try:
            # Test valid configuration
            config = AgenticsConfig()
            assert config.github_token is not None
            assert config.ollama_host.startswith(('http://', 'https://'))

            # Test configuration validation
            with patch.dict(os.environ, {'GITHUB_TOKEN': ''}):
                with pytest.raises(Exception):  # ConfigValidationError
                    init_config(AgenticsConfig())

            with patch.dict(os.environ, {'OLLAMA_HOST': 'invalid-url'}):
                with pytest.raises(Exception):  # ConfigValidationError
                    AgenticsConfig()

            # Test app initialization with custom config
            custom_config = AgenticsConfig(
                github_token=original_token,
                ollama_host="http://localhost:11434",
                ollama_reasoning_model="test-model",
                ollama_code_model="test-code-model"
            )

            app = AgenticsApp(custom_config)
            assert app.config.ollama_reasoning_model == "test-model"
            assert app.config.ollama_code_model == "test-code-model"

        finally:
            # Restore environment
            if original_token:
                os.environ['GITHUB_TOKEN'] = original_token
            if original_host:
                os.environ['OLLAMA_HOST'] = original_host



    @pytest.mark.integration
    async def test_service_manager_health_checks_integration(self, agentics_app):
        """Test service manager health checks integration."""
        # Test individual service health checks
        health_results = await agentics_app.service_manager.check_services_health()

        # Verify structure
        assert isinstance(health_results, dict)
        assert "ollama_reasoning" in health_results
        assert "ollama_code" in health_results
        assert "github" in health_results
        assert "mcp" in health_results

        # Test that health checks are callable
        for service_name, is_healthy in health_results.items():
            assert isinstance(is_healthy, bool)

    @pytest.mark.integration
    async def test_composable_workflows_integration(self, agentics_app, test_issue_url):
        """Test composable workflows integration."""
        # Test direct workflow execution
        result = await agentics_app.composable_workflows.process_issue(test_issue_url)

        # Verify workflow result
        assert isinstance(result, dict)
        assert "refined_ticket" in result
        assert "generated_code" in result
        assert "generated_tests" in result

        # Test batch workflow execution through app
        test_urls = [test_issue_url]
        batch_result = await agentics_app.process_issues_batch(test_urls)

        assert "total_issues" in batch_result
        assert batch_result["total_issues"] == 1
        assert "successful" in batch_result
        assert "failed" in batch_result
        assert "results" in batch_result

    @pytest.mark.integration
    async def test_monitoring_and_logging_integration(self, agentics_app, test_issue_url):
        """Test monitoring and logging integration."""
        from src.monitoring import get_monitor

        monitor = get_monitor()

        # Execute workflow to generate monitoring data
        result = await agentics_app.process_issue(test_issue_url)

        # Check monitoring data
        monitoring_data = monitor.get_monitoring_data()

        # Verify monitoring structure
        assert "metrics" in monitoring_data
        assert "workflows" in monitoring_data
        assert "active_workflows" in monitoring_data

        # Verify metrics contain expected data
        metrics = monitoring_data["metrics"]
        assert "counters" in metrics
        assert "timers" in metrics
        assert "gauges" in metrics
        assert "histograms" in metrics

    @pytest.mark.integration
    async def test_error_recovery_with_circuit_breakers(self, agentics_app):
        """Test error recovery with circuit breakers."""
        from src.circuit_breaker import get_circuit_breaker

        # Test circuit breaker instances exist
        ollama_cb = get_circuit_breaker("ollama_reasoning")
        github_cb = get_circuit_breaker("github")

        assert ollama_cb is not None
        assert github_cb is not None

        # Circuit breakers should be in closed state initially
        assert ollama_cb.state.name == "CLOSED"
        assert github_cb.state.name == "CLOSED"

    @pytest.mark.integration
    async def test_app_lifecycle_management(self):
        """Test complete app lifecycle management."""
        # Create and initialize app
        app = AgenticsApp()
        assert app._initialized is False

        await app.initialize()
        assert app._initialized is True

        # Test that multiple initialize calls are safe
        await app.initialize()  # Should not fail
        assert app._initialized is True

        # Test shutdown
        await app.shutdown()
        assert app._initialized is False

        # Test that shutdown on uninitialized app is safe
        await app.shutdown()  # Should not fail
        assert app._initialized is False

    @pytest.mark.integration
    async def test_configuration_override_scenarios(self):
        """Test configuration override scenarios."""
        # Test with custom configuration
        custom_config = AgenticsConfig(
            github_token=os.getenv('GITHUB_TOKEN'),
            ollama_host="http://localhost:11434",
            ollama_reasoning_model="custom-reasoning-model",
            ollama_code_model="custom-code-model",
            circuit_breaker_failure_threshold=10,
            circuit_breaker_recovery_timeout=120
        )

        app = AgenticsApp(custom_config)
        await app.initialize()

        try:
            # Verify custom config is used
            assert app.config.ollama_reasoning_model == "custom-reasoning-model"
            assert app.config.ollama_code_model == "custom-code-model"
            assert app.config.circuit_breaker_failure_threshold == 10
            assert app.config.circuit_breaker_recovery_timeout == 120

            # Verify services use custom config
            assert app.service_manager.config.ollama_reasoning_model == "custom-reasoning-model"
            assert app.service_manager.config.ollama_code_model == "custom-code-model"

        finally:
            await app.shutdown()
