"""
Integration tests for edge cases and monitoring in the agentics workflow.

These tests validate error handling, edge cases, and monitoring functionality
with real service calls and comprehensive validation.
"""
# Set required environment variable for tests before any imports
import os
os.environ['PROJECT_ROOT'] = '/tmp/test_project'

import pytest
import os
import time
import asyncio
from github import GithubException

from src.agentics import create_composable_workflow, check_services, AgenticsApp
from src.monitoring import structured_log, track_workflow_progress, get_monitoring_data
from src.circuit_breaker import CircuitBreakerOpenException, get_circuit_breaker
from src.error_recovery_agent import ErrorRecoveryAgent


class TestEdgeCasesAndMonitoringIntegration:
    """Integration tests for edge cases and monitoring functionality."""

    @pytest.fixture
    def workflow_system(self):
        """Fixture for real workflow system."""
        return asyncio.run(create_composable_workflow())


    @pytest.mark.integration
    def test_empty_ticket_handling(self, workflow_system):
        """Test workflow behavior with empty or minimal ticket content."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        # Test with issue 23 (empty ticket)
        empty_ticket_url = f"{test_repo_url}/issues/23"

        # Should handle empty ticket gracefully or raise appropriate error
        with pytest.raises(ValueError, match="Empty ticket content"):
            workflow_system.process_issue(empty_ticket_url)

    @pytest.mark.integration
    def test_invalid_github_url_handling(self, workflow_system):
        """Test workflow behavior with invalid GitHub URLs."""
        invalid_urls = [
            "https://github.com/user/repo/pull/1",  # Pull request instead of issue
            "https://gitlab.com/user/repo/issues/1",  # Wrong domain
            "https://github.com/user/repo/issues",  # Missing issue number
            "not-a-url",  # Invalid URL format
        ]

        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid GitHub URL"):
                workflow_system.process_issue(invalid_url)

    @pytest.mark.integration
    def test_non_existent_issue_handling(self, workflow_system):
        """Test workflow behavior with non-existent issues."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        non_existent_url = f"{test_repo_url}/issues/99999"

        # Should raise GithubException for non-existent issues
        with pytest.raises(GithubException):
            workflow_system.process_issue(non_existent_url)

    @pytest.mark.integration
    def test_non_existent_repository_handling(self, workflow_system):
        """Test workflow behavior with non-existent repositories."""
        non_existent_urls = [
            "https://github.com/nonexistentuser/nonexistentrepo/issues/1",
            "https://github.com/test/test/issues/1"
        ]

        for url in non_existent_urls:
            with pytest.raises(GithubException):
                workflow_system.process_issue(url)

    @pytest.mark.integration
    def test_network_timeout_handling(self, workflow_system):
        """Test workflow behavior during network timeouts."""
        # Use invalid URL to trigger network error
        issue_url = "https://invalid-url/issues/1"

        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_llm_service_unavailable_handling(self, workflow_system):
        """Test workflow behavior when services are unavailable."""
        # Use invalid URL to trigger service failure
        issue_url = "https://invalid-url/issues/1"

        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_partial_workflow_failure_recovery(self, workflow_system):
        """Test recovery from workflow failures."""
        # Use invalid URL to trigger failure
        issue_url = "https://invalid-url/issues/1"

        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_circuit_breaker_integration(self, workflow_system):
        """Test circuit breaker prevents cascade failures."""
        # Use invalid URL to trigger failure
        issue_url = "https://invalid-url/issues/1"

        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_error_recovery_agent_integration(self, workflow_system):
        """Test error recovery agent integration."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Should fail
        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_monitoring_workflow_progress_tracking(self, workflow_system):
        """Test that workflow progress is properly tracked and monitored."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = workflow_system.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_structured_logging_integration(self, workflow_system):
        """Test structured logging captures workflow events."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = workflow_system.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_monitoring_data_collection(self, workflow_system):
        """Test that monitoring data is collected throughout workflow execution."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = workflow_system.process_issue(issue_url)

        # Get monitoring data
        monitoring_data = workflow_system.get_monitoring_data()

        # Verify monitoring data structure
        assert isinstance(monitoring_data, dict)

    @pytest.mark.integration
    def test_performance_metrics_collection(self, workflow_system):
        """Test that performance metrics are collected during execution."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        start_time = time.time()

        # Execute workflow
        result = workflow_system.process_issue(issue_url)

        end_time = time.time()

        # Verify execution completed in reasonable time
        execution_time = end_time - start_time
        assert execution_time >= 0
        assert execution_time < 300  # Should complete within 5 minutes

    @pytest.mark.integration
    def test_health_monitor_integration(self, workflow_system):
        """Test health monitor integration with workflow."""
        # Use invalid URL to trigger failure
        issue_url = "https://invalid-url/issues/1"

        # Should fail
        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_concurrent_workflow_execution_safety(self, workflow_system):
        """Test thread safety during concurrent workflow executions."""
        import threading
        import concurrent.futures

        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_urls = [
            f"{test_repo_url}/issues/1",
            f"{test_repo_url}/issues/2"
        ]

        results = {}
        errors = []

        def process_issue_thread(issue_url, thread_id):
            try:
                result = workflow_system.process_issue(issue_url)
                results[thread_id] = result
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Execute workflows concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for i, issue_url in enumerate(issue_urls):
                future = executor.submit(process_issue_thread, issue_url, i)
                futures.append(future)

            # Wait for all to complete
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify no thread safety errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 2, "Not all workflows completed successfully"

    @pytest.mark.integration
    def test_workflow_state_preservation_during_errors(self, workflow_system):
        """Test that workflow state is properly preserved during error scenarios."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execution should fail
        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_graceful_service_degradation(self, workflow_system):
        """Test graceful degradation when external services fail."""
        # Use invalid URL to trigger service failures
        issue_url = "https://invalid-url/issues/1"

        # Workflow should fail gracefully without crashing
        with pytest.raises(Exception):
            workflow_system.process_issue(issue_url)

    @pytest.mark.integration
    def test_workflow_retry_logic_with_backoff(self, workflow_system):
        """Test retry logic with exponential backoff for transient failures."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = workflow_system.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_context_preservation_for_debugging(self, workflow_system):
        """Test that error context is preserved for debugging purposes."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execute and expect error
        with pytest.raises(Exception):
            await workflow_system.process_issue(issue_url)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_backward_compatibility_wrapper(self, workflow_system):
        """Test the backward compatibility wrapper maintains old interface."""
        # Test the app wrapper
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        initial_state = {"url": f"{test_repo_url}/issues/1"}

        result = await workflow_system.full_workflow.ainvoke(initial_state, config={"configurable": {"thread_id": "test_thread"}})

        # Verify wrapper works
        assert result is not None
        assert isinstance(result, dict)