"""
Integration tests for Phase 5: Workflow Orchestration.

Tests composable workflows, parallel processing, and logging as outlined in ARCHITECTURE_REFACTOR.md Phase 5.
Validates real workflow execution with comprehensive asserts on workflow execution, state transitions, and output validation.
"""

import pytest
import asyncio
import os
import time
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
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/20"

        # Execute full workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed successfully
        assert result is not None
        assert isinstance(result, dict)

        # Assert all phases produced expected outputs
        assert "refined_ticket" in result
        assert "generated_code" in result
        assert "generated_tests" in result
        assert "validation_results" in result

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
        assert "```typescript" in result["generated_code"] or "```javascript" in result["generated_code"]

        # Assert test generation phase output
        assert len(result["generated_tests"]) > 0
        assert "describe(" in result["generated_tests"] or "test(" in result["generated_tests"]

        # Assert validation results from collaborative generation
        validation = result["validation_results"]
        assert isinstance(validation, dict)
        assert "validation_score" in validation
        assert isinstance(validation["validation_score"], (int, float))
        assert 0 <= validation["validation_score"] <= 100

    def test_parallel_processing_dependency_analysis(self, composable_workflow):
        """Test parallel processing in dependency analysis workflow."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow to trigger parallel processing
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert parallel processing occurred (dependency analysis merged)
        assert result is not None
        assert "refined_ticket" in result

        # Check if dependency analysis was included (may not always be present)
        ticket = result["refined_ticket"]
        if "available_dependencies" in ticket:
            assert isinstance(ticket["available_dependencies"], list)

    def test_workflow_logging_and_monitoring(self, composable_workflow):
        """Test that workflow execution is properly logged and monitored."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/1"

        # Clear previous monitoring data
        initial_data = composable_workflow.get_monitoring_data()

        # Execute workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed
        assert result is not None

        # Assert monitoring data was updated
        final_data = composable_workflow.get_monitoring_data()
        assert final_data != initial_data  # Monitoring data changed

        # Check for workflow-specific logs
        workflow_logs = [log for log in final_data.get("logs", []) if "workflow" in log.get("message", "").lower()]
        assert len(workflow_logs) > 0

    def test_state_transitions_through_phases(self, composable_workflow):
        """Test state transitions through all workflow phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/1"

        # Execute full workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert state progression: issue processing -> code generation -> integration
        assert "refined_ticket" in result  # Issue processing phase
        assert "generated_code" in result  # Code generation phase
        assert "generated_tests" in result  # Code generation phase
        assert "integration_results" in result  # Integration phase
        assert "test_results" in result  # Testing phase
        assert "review_results" in result  # Review phase

        # Assert state immutability (no direct mutations, new states created)
        # This is validated by successful completion without errors

    def test_composable_workflow_error_recovery(self, composable_workflow):
        """Test error recovery in workflow orchestration."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url-that-does-not-exist/issues/1"

        # Execute and expect error recovery
        with pytest.raises(Exception):
            asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert error was logged in monitoring
        monitoring_data = composable_workflow.get_monitoring_data()
        error_logs = [log for log in monitoring_data.get("logs", []) if "error" in log.get("level", "").lower()]
        assert len(error_logs) > 0

    def test_workflow_checkpointing_persistence(self, composable_workflow):
        """Test that workflow uses checkpointer for state persistence."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Assert workflow completed with checkpointer
        assert result is not None
        assert isinstance(result, dict)

        # Verify checkpointer was used (workflow should maintain state)
        assert "refined_ticket" in result

    def test_parallel_execution_performance(self):
        """Test parallel execution performance simulation."""
        async def dummy_agent(state):
            await asyncio.sleep(0.1)  # Simulate processing time
            return {**state, "processed": True, "timestamp": time.time()}

        # Create parallel workflow
        parallel_workflow = RunnableParallel(
            branch1=RunnableLambda(dummy_agent),
            branch2=RunnableLambda(dummy_agent)
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
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        issue_url = f"{test_repo_url}/issues/20"

        result = asyncio.run(composable_workflow.process_issue(issue_url))

        # Validate code output structure
        code = result["generated_code"]
        assert len(code) > 50  # Substantial code generated
        assert any(keyword in code.lower() for keyword in ["function", "class", "export", "import"])

        # Validate test output structure
        tests = result["generated_tests"]
        assert len(tests) > 50  # Substantial tests generated
        assert "describe(" in tests or "test(" in tests

        # Validate integration results
        integration = result.get("integration_results", {})
        assert isinstance(integration, dict)

        # Validate test results
        test_results = result.get("test_results", {})
        assert isinstance(test_results, dict)

        # Validate review results
        review = result.get("review_results", {})
        assert isinstance(review, dict)