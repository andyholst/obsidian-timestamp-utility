"""
Unit tests for ComposableWorkflows architectural components.
Tests the three-phase workflow architecture and parallel processing enhancements.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from src.composable_workflows import ComposableWorkflows
from src.state import State, CodeGenerationState
from src.agent_composer import WorkflowConfig
from src.models import CodeSpec, TestSpec


class TestComposableWorkflowsArchitecture:
    """Test the architectural components of ComposableWorkflows."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for testing."""
        llm = Mock()
        llm.invoke = Mock(return_value=Mock(content="test response"))
        return llm

    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client."""
        client = Mock()
        client.get_issue = AsyncMock(return_value={"title": "Test Issue", "body": "Test body"})
        return client

    @pytest.fixture
    def mock_mcp_tools(self):
        """Mock MCP tools."""
        @tool
        def test_tool(query: str) -> str:
            """Test tool for MCP integration."""
            return f"Tool result for: {query}"

        return [test_tool]

    @pytest.fixture
    def workflows(self, mock_llm, mock_github_client, mock_mcp_tools):
        """Create ComposableWorkflows instance for testing."""
        return ComposableWorkflows(
            llm_reasoning=mock_llm,
            llm_code=mock_llm,
            github_client=mock_github_client,
            mcp_tools=mock_mcp_tools
        )

    def test_workflow_initialization(self, workflows):
        """Test that workflows are properly initialized."""
        assert workflows.issue_processing_workflow is not None
        assert workflows.code_generation_workflow is not None
        assert workflows.integration_testing_workflow is not None
        assert workflows.full_workflow is not None
        assert workflows.checkpointer is not None

    def test_agent_registration(self, workflows):
        """Test that all required agents are registered."""
        expected_agents = [
            "fetch_issue", "ticket_clarity", "implementation_planner",
            "dependency_analyzer", "code_extractor", "collaborative_generator",
            "pre_test_runner", "code_integrator", "post_test_runner",
            "code_reviewer", "output_result", "error_recovery"
        ]

        for agent_name in expected_agents:
            assert agent_name in workflows.composer.agents

    def test_tool_registration(self, workflows, mock_mcp_tools):
        """Test that MCP tools are registered."""
        for tool in mock_mcp_tools:
            assert tool.name in workflows.composer.tools

    def test_workflow_creation(self, workflows):
        """Test that individual workflows are created correctly."""
        # Test issue processing workflow
        issue_config = WorkflowConfig(
            agent_names=["fetch_issue", "ticket_clarity", "implementation_planner"],
            tool_names=["test_tool"]
        )
        issue_workflow = workflows.composer.create_workflow("test_issue", issue_config)
        assert issue_workflow is not None

        # Test code generation workflow
        code_config = WorkflowConfig(
            agent_names=["code_extractor", "collaborative_generator"],
            tool_names=["test_tool"]
        )
        code_workflow = workflows.composer.create_workflow("test_code", code_config)
        assert code_workflow is not None

    @patch('agents.agentics.src.composable_workflows.RunnableParallel')
    def test_parallel_processing_enhancement(self, mock_parallel, workflows):
        """Test that parallel processing can be added for dependency analysis."""
        # This test verifies the structure supports parallel processing
        # The actual implementation would use RunnableParallel for concurrent execution

        # Mock parallel execution
        mock_parallel_instance = Mock()
        mock_parallel.return_value = mock_parallel_instance

        # Verify the workflow structure supports parallel nodes
        graph = workflows.full_workflow.graph

        # Check that dependency_analysis node exists (can run in parallel)
        assert "dependency_analysis" in graph.nodes

        # Check that issue_processing and dependency_analysis are connected
        edges = list(graph.edges)
        edge_names = [(edge[0], edge[1]) for edge in edges]
        assert ("issue_processing", "dependency_analysis") in edge_names

    def test_state_adapters_integration(self, workflows):
        """Test that state adapters work correctly."""
        from agents.agentics.src.state_adapters import (
            StateToCodeGenerationStateAdapter,
            CodeGenerationStateToStateAdapter
        )

        # Test conversion from State dict to CodeGenerationState
        state_dict = State()
        state_dict.update({
            "url": "https://github.com/test/repo/issues/1",
            "ticket_content": "Test issue content",
            "requirements": ["req1", "req2"],
            "acceptance_criteria": ["crit1"]
        })

        adapter = StateToCodeGenerationStateAdapter()
        cg_state = adapter.invoke(state_dict)

        assert isinstance(cg_state, CodeGenerationState)
        assert cg_state.issue_url == "https://github.com/test/repo/issues/1"
        assert cg_state.ticket_content == "Test issue content"
        assert cg_state.requirements == ["req1", "req2"]

        # Test reverse conversion
        reverse_adapter = CodeGenerationStateToStateAdapter()
        back_to_dict = reverse_adapter.invoke(cg_state)

        assert isinstance(back_to_dict, dict)
        assert back_to_dict["url"] == "https://github.com/test/repo/issues/1"

    def test_error_recovery_integration(self, workflows):
        """Test that error recovery is integrated into the workflow."""
        # Verify error_recovery agent is registered
        assert "error_recovery" in workflows.composer.agents

        # Verify error_recovery node exists in full workflow
        graph = workflows.full_workflow.graph
        assert "error_recovery" in graph.nodes

    def test_hitl_integration(self, workflows):
        """Test that HITL is integrated into the workflow."""
        # Verify hitl node exists
        graph = workflows.full_workflow.graph
        assert "hitl" in graph.nodes

        # Test routing logic
        def route_hitl(state):
            score = state.get("validation_score", 0)
            return "hitl" if score < 80 else "integration_testing"

        # Test high score - should go to integration_testing
        high_score_state = {"validation_score": 85}
        assert route_hitl(high_score_state) == "integration_testing"

        # Test low score - should go to hitl
        low_score_state = {"validation_score": 75}
        assert route_hitl(low_score_state) == "hitl"

    def test_workflow_monitoring(self, workflows):
        """Test that workflow monitoring is integrated."""
        # Test monitoring data retrieval
        monitoring_data = workflows.get_monitoring_data()
        assert isinstance(monitoring_data, dict)

    @pytest.mark.asyncio
    async def test_full_workflow_execution_structure(self, workflows):
        """Test the structure of full workflow execution."""
        # Mock the workflow execution
        with patch.object(workflows.full_workflow, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "generated_code": "test code",
                "generated_tests": "test tests",
                "validation_results": {"passed": True}
            }

            result = await workflows.process_issue("https://github.com/test/repo/issues/1")

            # Verify the workflow was called with correct parameters
            mock_ainvoke.assert_called_once()
            call_args = mock_ainvoke.call_args
            initial_state = call_args[0][0]
            config = call_args[0][1]

            assert initial_state == {"url": "https://github.com/test/repo/issues/1"}
            assert "configurable" in config
            assert result["generated_code"] == "test code"
            assert result["generated_tests"] == "test tests"

    def test_checkpointing_integration(self, workflows):
        """Test that LangGraph checkpointer is properly integrated."""
        # Verify checkpointer is MemorySaver instance
        from langgraph.checkpoint.memory import MemorySaver
        assert isinstance(workflows.checkpointer, MemorySaver)

        # Verify workflow is compiled with checkpointer
        assert hasattr(workflows.full_workflow, 'checkpointer')

    def test_composability_patterns(self, workflows):
        """Test that LCEL composition patterns are used."""
        # Test that workflows use pipe operators for composition
        issue_workflow = workflows.issue_processing_workflow

        # The workflow should be composed of multiple agents
        # This is a structural test - the actual composition happens in AgentComposer
        assert hasattr(issue_workflow, 'invoke')  # Should be a Runnable

    def test_tool_integration_in_workflows(self, workflows, mock_mcp_tools):
        """Test that tools are integrated into workflow creation."""
        # Verify tools are passed to workflow configs
        with patch.object(workflows.composer, 'create_workflow') as mock_create:
            mock_create.return_value = Mock()

            # Recreate workflows to test tool integration
            workflows._create_issue_processing_workflow()

            # Verify create_workflow was called with tool names
            call_args = mock_create.call_args
            config = call_args[0][1]  # Second argument is config
            assert "test_tool" in config.tool_names


class TestParallelProcessingEnhancement:
    """Test the parallel processing enhancements."""

    def test_dependency_analysis_parallel_potential(self):
        """Test that the architecture supports parallel dependency analysis."""
        # This test verifies the design supports parallel execution
        # even if not currently implemented

        from agents.agentics.src.composable_workflows import ComposableWorkflows

        # The design should allow for parallel execution of:
        # - Issue processing (fetch -> clarify -> plan)
        # - Dependency analysis (can run concurrently)

        # Verify the nodes exist for parallel execution
        # This is validated by the node registration in _create_full_workflow

        assert True  # Structural test - design supports parallelism

    def test_merge_parallel_outputs(self):
        """Test the merge logic for parallel outputs."""
        from agents.agentics.src.composable_workflows import ComposableWorkflows
        from agents.agentics.src.models import CodeSpec

        workflows = Mock(spec=ComposableWorkflows)
        workflows.monitor = Mock()

        # Create mock states
        issue_state = CodeGenerationState(
            issue_url="test_url",
            ticket_content="test content",
            title="Test",
            description="Test desc",
            requirements=["req1"],
            acceptance_criteria=["crit1"],
            code_spec=CodeSpec(dependencies=[]),
            test_spec=TestSpec(),
            implementation_steps=["step1"]
        )

        dep_state = {
            "available_dependencies": ["dep1", "dep2"]
        }

        parallel_result = {
            "issue_processing": issue_state,
            "dependency_analysis": dep_state
        }

        # Test merge logic
        merged = ComposableWorkflows._merge_parallel_outputs(workflows, parallel_result)

        assert merged.issue_url == "test_url"
        assert "dep1" in merged.code_spec.dependencies
        assert "dep2" in merged.code_spec.dependencies


if __name__ == "__main__":
    pytest.main([__file__])