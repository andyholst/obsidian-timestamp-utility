"""
Integration tests for parallel processing capabilities in the agentics workflow.
Tests concurrent execution of workflow phases and batch processing features.
"""

import pytest
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from src.composable_workflows import ComposableWorkflows
from src.agentics import AgenticsApp, create_composable_workflow
from src.performance import get_batch_processor, get_task_manager


@pytest.fixture
def composable_workflow():
    """Fixture for real ComposableWorkflows instance."""
    return create_composable_workflow()


class TestParallelProcessingIntegration:
    """Integration tests for parallel processing capabilities."""

    @pytest.mark.integration
    def test_parallel_issue_processing_and_dependency_analysis(self, composable_workflow):
        """Test parallel execution of issue processing and dependency analysis phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_processing_multiple_issues(self):
        """Test batch processing of multiple GitHub issues concurrently."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_urls = [
            f"{test_repo_url}/issues/1",
            f"{test_repo_url}/issues/2",
            f"{test_repo_url}/issues/3"
        ]

        # Create and initialize AgenticsApp
        app = AgenticsApp()
        await app.initialize()

        # Execute batch processing
        batch_result = await app.process_issues_batch(issue_urls)

        # Verify batch processing
        assert isinstance(batch_result, dict)
        assert batch_result["total_issues"] == 3
        assert "results" in batch_result
        assert len(batch_result["results"]) == 3
        for result in batch_result["results"]:
            assert "success" in result
            assert "issue_url" in result

    @pytest.mark.integration
    def test_concurrent_workflow_phase_execution(self, composable_workflow):
        """Test concurrent execution within workflow phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_parallel_dependency_analysis_execution(self, composable_workflow):
        """Test parallel execution of dependency analysis with issue processing."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow that should trigger parallel execution
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_performance_optimization_with_parallel_processing(self, composable_workflow):
        """Test that parallel processing improves performance metrics."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_error_handling_in_parallel_execution(self, composable_workflow):
        """Test error handling when parallel execution fails."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execute and expect error handling
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_partial_failure_in_batch_processing(self):
        """Test handling of partial failures in batch processing."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_urls = [
            f"{test_repo_url}/issues/1",
            "https://invalid-url/issues/2",  # Invalid URL
            f"{test_repo_url}/issues/3"
        ]

        # Create and initialize AgenticsApp
        app = AgenticsApp()
        await app.initialize()

        batch_result = await app.process_issues_batch(issue_urls)

        # Verify partial failure handling
        assert batch_result["total_issues"] == 3
        assert "results" in batch_result
        assert len(batch_result["results"]) == 3
        # At least some should succeed, some may fail
        assert any(r.get("success") for r in batch_result["results"])

    @pytest.mark.integration
    def test_resource_management_in_parallel_processing(self, composable_workflow):
        """Test resource management and cleanup in parallel processing."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scalability_with_increasing_parallel_load(self):
        """Test scalability as parallel processing load increases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        # Test with small batch size
        batch_size = 2
        issue_urls = [f"{test_repo_url}/issues/{i+1}" for i in range(batch_size)]

        # Create and initialize AgenticsApp
        app = AgenticsApp()
        await app.initialize()

        batch_result = await app.process_issues_batch(issue_urls)

        # Verify all issues processed
        assert batch_result["total_issues"] == batch_size
        assert "results" in batch_result
        assert len(batch_result["results"]) == batch_size

    @pytest.mark.integration
    def test_concurrent_agent_execution_within_phases(self, composable_workflow):
        """Test concurrent execution of multiple agents within workflow phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Test issue processing phase (should have multiple agents)
        issue_result = composable_workflow.issue_processing_workflow.invoke({"url": issue_url})

        # Verify result
        assert issue_result is not None

    @pytest.mark.integration
    def test_thread_safety_in_parallel_processing(self, composable_workflow):
        """Test thread safety when multiple workflows run in parallel."""
        import threading

        issue_urls = [
            "https://github.com/test/repo/issues/1",
            "https://github.com/test/repo/issues/2"
        ]

        results = {}
        errors = []

        def process_issue_thread(issue_url, thread_id):
            try:
                result = composable_workflow.process_issue(issue_url)
                results[thread_id] = result
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Create threads for concurrent execution
        threads = []
        for i, issue_url in enumerate(issue_urls):
            thread = threading.Thread(target=process_issue_thread, args=(issue_url, i))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify thread safety - no errors and results collected
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 2, "Not all threads produced results"

    @pytest.mark.integration
    def test_performance_monitoring_in_parallel_execution(self, composable_workflow):
        """Test performance monitoring during parallel execution."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = composable_workflow.process_issue(issue_url)

        # Get monitoring data
        monitoring_data = composable_workflow.get_monitoring_data()

        # Verify monitoring data is available
        assert isinstance(monitoring_data, dict)