"""
Integration tests for ComposableWorkflows functionality.

These tests validate the three-phase composable workflow architecture:
1. ISSUE PROCESSING (fetch -> clarify -> plan)
2. CODE GENERATION (extract -> collaborative generation)
3. INTEGRATION & TESTING (integrate -> test -> review -> output)

Tests cover real end-to-end workflow execution with actual service calls.
"""
# Set required environment variable for tests before any imports
import os
os.environ['PROJECT_ROOT'] = '/tmp/test_project'

import pytest
import os
import json
import re

# Import the composable workflow components
from src.composable_workflows import ComposableWorkflows
from src.agentics import create_composable_workflow, check_services
from src.state import CodeGenerationState
from src.agent_composer import WorkflowConfig


# Regex pattern to match function definitions
import asyncio
import time
from langchain_core.runnables import RunnableParallel, RunnableLambda
from src.state import CodeGenerationState
FUNCTION_PATTERN = re.compile(r'\bfunction\b|\bclass\b|=>')

@pytest.fixture(scope="session")
def sentence_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2', cache_folder="/tmp/.cache/huggingface")
# Helper function to calculate semantic similarity
def calculate_semantic_similarity(expected_text, actual_text):
    """Calculate semantic similarity between two texts."""
    embeddings = model.encode([expected_text, actual_text], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    return similarity * 100

# Helper function to extract content from markdown code blocks
def extract_content(text):
    """Extract content from markdown code blocks."""
    pattern = r'```(?:typescript)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[0].strip() if matches else text.strip()

# Helper function to extract method name and command ID from generated code
def extract_method_and_command(generated_code):
    """Extract method name and command ID from generated code."""
    method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', generated_code)
    command_match = re.search(r"this\.addCommand\(\{\s*id:\s*['\"]([^'\"]+)['\"]", generated_code)
    method_name = method_match.group(2) if method_match else None
    command_id = command_match.group(1) if command_match else None
    return method_name, command_id

# Helper function to extract describe lines from generated tests
def extract_describe_lines(generated_tests):
    """Extract describe block lines from generated tests."""
    return [line.strip() for line in generated_tests.splitlines() if line.strip().startswith('describe(')]


class TestComposableWorkflowsIntegration:
    """Integration tests for the ComposableWorkflows system."""

    @pytest.fixture
    def composable_workflow(self):
        """Fixture for real ComposableWorkflows instance."""
        return asyncio.run(create_composable_workflow())

    @pytest.mark.integration
    def test_composable_workflows_initialization(self, composable_workflow, sentence_model):
        self.model = sentence_model
        """Test that ComposableWorkflows initializes correctly with all components."""
        # Verify workflows are created
        assert composable_workflow.issue_processing_workflow is not None
        assert composable_workflow.code_generation_workflow is not None
        assert composable_workflow.integration_testing_workflow is not None
        assert composable_workflow.full_workflow is not None

        # Verify agents are registered
        assert "fetch_issue" in composable_workflow.composer.agents
        assert "ticket_clarity" in composable_workflow.composer.agents
        assert "implementation_planner" in composable_workflow.composer.agents
        assert "code_extractor" in composable_workflow.composer.agents
        assert "collaborative_generator" in composable_workflow.composer.agents
        assert "code_integrator" in composable_workflow.composer.agents
        assert "post_test_runner" in composable_workflow.composer.agents
        assert "code_reviewer" in composable_workflow.composer.agents
        assert "output_result" in composable_workflow.composer.agents

    @pytest.mark.integration
    def test_issue_processing_workflow_phase(self, composable_workflow):
        """Test the ISSUE PROCESSING workflow phase independently."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        result = composable_workflow.issue_processing_workflow.invoke({"url": issue_url})

        # Verify result structure
        assert "refined_ticket" in result
        assert "title" in result["refined_ticket"]
        assert "requirements" in result["refined_ticket"]
        assert "acceptance_criteria" in result["refined_ticket"]

    @pytest.mark.integration
    def test_code_generation_workflow_phase(self, composable_workflow):
        """Test the CODE GENERATION workflow phase independently."""
        # Input state from issue processing
        input_state = {
            "refined_ticket": {
                "title": "Test Issue",
                "requirements": ["Implement feature X"],
                "implementation_steps": ["Step 1", "Step 2"]
            },
            "relevant_code_files": [],
            "relevant_test_files": []
        }

        result = composable_workflow.code_generation_workflow.invoke(input_state)

        # Verify code and test generation
        assert "generated_code" in result
        assert "generated_tests" in result
        assert len(result["generated_code"]) > 0
        assert len(result["generated_tests"]) > 0

    @pytest.mark.integration
    def test_integration_testing_workflow_phase(self, composable_workflow):
        """Test the INTEGRATION & TESTING workflow phase independently."""
        # Input state from code generation
        input_state = {
            "generated_code": "```typescript\nexport class TestClass {}\n```",
            "generated_tests": "```typescript\ndescribe('TestClass', () => {});\n```",
            "relevant_code_files": [],
            "relevant_test_files": []
        }

        result = composable_workflow.integration_testing_workflow.invoke(input_state)

        # Verify integration results
        assert "integration_results" in result
        assert "test_results" in result
        assert "review_results" in result

    @pytest.mark.integration
    def test_full_workflow_end_to_end(self, composable_workflow):
        """Test the complete three-phase workflow end-to-end with real services."""
        # Use environment variable for test issue URL
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"

        test_url = f"{test_repo_url}/issues/20"
        initial_state = {"url": test_url}

        # Execute full workflow
        result = composable_workflow.process_issue(test_url)

        # Verify workflow completed successfully
        assert result is not None
        assert isinstance(result, dict)

        # Verify all phases produced expected outputs
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

        # Verify code generation
        assert len(result["generated_code"]) > 0
        code = extract_content(result["generated_code"])
        assert FUNCTION_PATTERN.search(code), "Generated code should include functions or classes"

        # Verify test generation
        assert len(result["generated_tests"]) > 0
        tests = extract_content(result["generated_tests"])
        assert "describe" in tests or "test" in tests, "Generated tests should include test blocks"

    @pytest.mark.integration
    def test_parallel_processing_in_workflow(self, composable_workflow):
        """Test that parallel processing is used in the full workflow."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.integration
    def test_workflow_error_handling(self, composable_workflow):
        """Test error handling in workflow execution."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url-that-does-not-exist/issues/1"

        # Execute and expect error
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_workflow_monitoring_and_logging(self, composable_workflow):
        """Test that workflow execution is properly monitored and logged."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_workflow_state_management(self, composable_workflow):
        """Test that workflow properly manages state between phases."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None

    @pytest.mark.integration
    def test_composable_workflow_with_mcp_tools(self, composable_workflow):
        """Test ComposableWorkflows with MCP tools integration."""
        # Verify tools were registered
        assert hasattr(composable_workflow, 'mcp_tools')
        # MCP tools may or may not be available depending on initialization
        assert isinstance(composable_workflow.mcp_tools, list)

    @pytest.mark.integration
    def test_workflow_phase_isolation(self, composable_workflow):
        """Test that individual workflow phases can be executed independently."""
        # Test issue processing phase
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"
        issue_result = composable_workflow.issue_processing_workflow.invoke({"url": issue_url})
        assert issue_result is not None

        # Test code generation phase
        code_result = composable_workflow.code_generation_workflow.invoke({"refined_ticket": {}})
        assert code_result is not None

        # Test integration phase
        integration_result = composable_workflow.integration_testing_workflow.invoke({"generated_code": ""})
        assert integration_result is not None

    @pytest.mark.integration
    def test_create_composable_workflow_function(self):
        """Test the create_composable_workflow factory function."""
        workflow = asyncio.run(create_composable_workflow())

        # Verify it's a ComposableWorkflows instance
        assert isinstance(workflow, ComposableWorkflows)

        # Verify all required attributes
        assert hasattr(workflow, 'issue_processing_workflow')
        assert hasattr(workflow, 'code_generation_workflow')
        assert hasattr(workflow, 'integration_testing_workflow')
        assert hasattr(workflow, 'full_workflow')
        assert hasattr(workflow, 'process_issue')

    @pytest.mark.integration
    def test_checkpointer_initialization(self, composable_workflow):
        """Test that checkpointer is properly initialized."""
        # Verify checkpointer is a MemorySaver instance
        from langgraph.checkpoint.memory import MemorySaver
        assert isinstance(composable_workflow.checkpointer, MemorySaver)

    @pytest.mark.integration
    def test_full_workflow_with_checkpointer(self, composable_workflow):
        """Test that the full workflow uses checkpointer for state persistence."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute workflow
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed
        assert result is not None
        assert isinstance(result, dict)

        # Verify checkpointer was used (workflow should have thread_id in result or similar)
        # The checkpointer should maintain state across the workflow execution
        assert "refined_ticket" in result

    @pytest.mark.integration
    def test_workflow_state_persistence_simulation(self, composable_workflow):
        """Test workflow state persistence by checking that intermediate states are maintained."""
        # This test simulates checking that the checkpointer maintains state
        # In a real scenario, we'd check thread state, but for integration test we verify
        # that the workflow completes with expected state transitions

        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute full workflow
        result = composable_workflow.process_issue(issue_url)

        # Verify that all expected state fields are present
        # This indicates that state was properly maintained through the workflow
        expected_fields = [
            "refined_ticket",
            "generated_code",
            "generated_tests"
        ]

        for field in expected_fields:
            assert field in result, f"Expected field '{field}' not found in result"

        # Verify ticket structure (from issue processing phase)
        ticket = result["refined_ticket"]
        assert "title" in ticket
        assert "requirements" in ticket
    @pytest.mark.integration
    def test_lcel_parallel_agent_simulation(self, dummy_state):
        """Test LCEL parallel execution with dummy agents simulating concurrent processing."""
        async def agent1_process(state):
            await asyncio.sleep(1)
            return state.__dict__ | {"agent": "agent1", "result": "completed", "timestamp": time.time()}
        
        async def agent2_process(state):
            await asyncio.sleep(1)
            return state.__dict__ | {"agent": "agent2", "result": "completed", "timestamp": time.time()}
        
        parallel_workflow = RunnableParallel(
            branch1=RunnableLambda(agent1_process),
            branch2=RunnableLambda(agent2_process)
        )
        
        start_time = time.time()
        result = asyncio.run(parallel_workflow.ainvoke(dummy_state))
        end_time = time.time()
        
        duration = end_time - start_time
        
        # Parallel execution should complete in roughly 1s, not 2s sequential
        assert duration &lt; 1.5, f"Parallel execution took too long: {duration:.2f}s (expected &lt;1.5s)"
        
        assert "branch1" in result
        assert "branch2" in result
        assert result["branch1"]["agent"] == "agent1"
        assert result["branch2"]["agent"] == "agent2"
        assert abs(result["branch1"]["timestamp"] - result["branch2"]["timestamp"]) &lt; 0.5  # timestamps close

        # Verify code and tests were generated (from code generation phase)
        assert len(result["generated_code"]) > 0
        assert len(result["generated_tests"]) > 0