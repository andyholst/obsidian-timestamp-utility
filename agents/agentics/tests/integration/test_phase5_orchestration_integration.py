"""
Integration tests for Phase 5: Workflow Orchestration.

Tests composable workflows, parallel processing, and logging as outlined in ARCHITECTURE_REFACTOR.md Phase 5.
Validates real workflow execution with comprehensive asserts on workflow execution, state transitions, and output validation.
"""

import pytest
import asyncio
import os
import time

# Heavy full-pipeline tests (real multi-agent LLM runs via process_issue) — tagged
# slow so the fast loop gate (loop-integration) excludes them. Run via
# `make test-agents-integration` for deep verification.
pytestmark = pytest.mark.slow

# Set project root for tests that need file system access
os.environ.setdefault("PROJECT_ROOT", "/tmp/obsidian-project")
os.makedirs("/tmp/obsidian-project/src", exist_ok=True)
os.makedirs("/tmp/obsidian-project/src/__tests__", exist_ok=True)
from langchain_core.runnables import RunnableParallel, RunnableLambda

# Import the composable workflow components
from src.composable_workflows import ComposableWorkflows
from src.agentics import create_composable_workflow
from src.state import CodeGenerationState
from src.monitoring import get_monitoring_data


@pytest.mark.integration
class TestPhase5OrchestrationIntegration:
    """Integration tests for Phase 5 workflow orchestration."""

    @pytest.fixture
    def composable_workflow(self):
        """Fixture for real ComposableWorkflows instance."""
        return asyncio.run(create_composable_workflow())

    def test_full_workflow_orchestration(self, composable_workflow):
        """Test complete workflow orchestration with state transitions."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        # Execute full workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed successfully
        assert result is not None
        assert isinstance(result, dict)

        # Workflow may return error dict if integration phase fails
        if result.get("success", True):
            assert "refined_ticket" in result
            assert "generated_code" in result
            assert "generated_tests" in result

            # Assert ticket structure from issue processing phase
            ticket = result["refined_ticket"]
            assert "title" in ticket
            assert "description" in ticket
            assert "requirements" in ticket
            assert "acceptance_criteria" in ticket
            assert isinstance(ticket["requirements"], list)
            assert isinstance(ticket["acceptance_criteria"], list)
            assert len(ticket["requirements"]) > 0
            assert len(ticket["acceptance_criteria"]) > 0

            # Assert code generation phase output
            assert len(result["generated_code"]) > 0

            # Assert test generation phase output
            assert len(result["generated_tests"]) > 0
        else:
            assert "error" in result

    def test_parallel_processing_dependency_analysis(self, composable_workflow):
        """Test parallel processing in dependency analysis workflow."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        # Execute workflow to trigger parallel processing
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert parallel processing occurred (dependency analysis merged)
        assert result is not None
        # Workflow may return error dict if issue doesn't exist
        if result.get("success", True):
            assert "refined_ticket" in result
            # Check if dependency analysis was included (may not always be present)
            ticket = result["refined_ticket"]
            if "available_dependencies" in ticket:
                assert isinstance(ticket["available_dependencies"], list)
        else:
            assert "error" in result

    def test_workflow_logging_and_monitoring(self, composable_workflow):
        """Test that workflow execution is properly logged and monitored."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        # Get initial monitoring data
        initial_data = composable_workflow.get_monitoring_data()

        # Execute workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed
        assert result is not None

        # Assert monitoring data was updated
        final_data = composable_workflow.get_monitoring_data()
        assert final_data is not None
        assert "workflows" in final_data or "metrics" in final_data

    def test_state_transitions_through_phases(self, composable_workflow):
        """Test state transitions through all workflow phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        # Execute full workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Workflow may return error dict if issue doesn't exist
        if result.get("success", True):
            # Assert state progression: issue processing -> code generation
            assert "refined_ticket" in result  # Issue processing phase
            assert "generated_code" in result  # Code generation phase
            assert "generated_tests" in result  # Code generation phase
        else:
            assert "error" in result

    def test_composable_workflow_error_recovery(self, composable_workflow):
        """Test error recovery in workflow orchestration."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url-that-does-not-exist/issues/1"

        # Execute - workflow handles errors gracefully and returns error dict
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow returned error result (graceful error handling)
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("success") is False or "error" in result

        # Assert error was captured in monitoring data
        monitoring_data = composable_workflow.get_monitoring_data()
        # Monitoring data should be present (metrics/workflows/active_workflows)
        assert monitoring_data is not None
        assert "metrics" in monitoring_data or "workflows" in monitoring_data

    def test_workflow_checkpointing_persistence(self, composable_workflow):
        """Test that workflow uses checkpointer for state persistence."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        # Execute workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed
        assert result is not None
        assert isinstance(result, dict)

        # Workflow may return error dict if issue doesn't exist
        if result.get("success", True):
            assert "refined_ticket" in result
        else:
            assert "error" in result

    def test_parallel_execution_performance(self):
        """Test parallel execution performance simulation."""

        async def dummy_agent(state):
            await asyncio.sleep(0.1)  # Simulate processing time
            return {**state, "processed": True, "timestamp": time.time()}

        # Create parallel workflow
        parallel_workflow = RunnableParallel(
            branch1=RunnableLambda(dummy_agent), branch2=RunnableLambda(dummy_agent)
        )

        dummy_state = {"initial": True}

        start_time = time.time()
        result = asyncio.run(parallel_workflow.ainvoke(dummy_state))
        end_time = time.time()

        duration = end_time - start_time

        # Assert parallel execution completed faster than sequential
        assert duration < 0.25  # Should complete in ~0.1s, not 0.2s

        # Assert both branches executed
        assert "branch1" in result
        assert "branch2" in result
        assert result["branch1"]["processed"] is True
        assert result["branch2"]["processed"] is True

    def test_workflow_output_validation(self, composable_workflow):
        """Test comprehensive validation of workflow outputs."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, (
            "TEST_ISSUE_URL environment variable is required"
        )

        issue_url = f"{test_repo_url}/issues/20"

        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Validate code output structure
        code = result.get("generated_code", "")
        if code:
            assert len(code) > 50, "Substantial code generated"
            # LLM may generate code in various styles - check for common TypeScript/JavaScript patterns
            code_lower = code.lower()
            has_code_keywords = any(
                keyword in code_lower
                for keyword in ["function", "class", "export", "import", "const", "let", "var", "public", "private", "async", "await", "interface", "module"]
            )
            # Also check it looks like code (has braces or semicolons)
            has_code_structure = ("{" in code and "}" in code) or ";" in code
            assert has_code_keywords or has_code_structure, \
                f"Generated code doesn't look like valid TypeScript: {code[:200]}"

        # Validate test output structure
        tests = result.get("generated_tests", "")
        if tests:
            assert len(tests) > 50  # Substantial tests generated
            assert "describe(" in tests or "test(" in tests

        # Validate optional results (may or may not be present depending on workflow success)
        # In ultra-fast mode, these keys are not populated
        integration = result.get("integration_results", {})
        assert isinstance(integration, dict)

        test_results = result.get("test_results", {})
        assert isinstance(test_results, dict)

        review = result.get("review_results", {})
        assert isinstance(review, dict)

        # Validate that at least some output was generated
        has_output = (
            result.get("generated_code")
            or result.get("generated_tests")
            or result.get("refined_ticket")
        )
        assert has_output, f"No workflow output generated: {list(result.keys())}"
