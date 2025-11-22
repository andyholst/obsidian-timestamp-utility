import pytest
import os
from unittest.mock import MagicMock, patch
from langchain.schema.runnable import Runnable
from langchain.tools import Tool

# Set required environment variables for imports
os.environ.setdefault('PROJECT_ROOT', '/tmp')
os.environ.setdefault('GITHUB_TOKEN', 'dummy')

from src.agent_composer import AgentComposer, WorkflowConfig


class TestAgentComposer:
    """Unit tests for AgentComposer class."""

    @pytest.fixture
    def composer(self):
        """Fixture to create a fresh AgentComposer instance."""
        return AgentComposer()

    @pytest.fixture
    def mock_agent(self):
        """Fixture to create a mock Runnable agent."""
        mock = MagicMock(spec=Runnable)
        mock.__or__ = MagicMock(return_value=mock)  # Mock the pipe operator
        return mock

    @pytest.fixture
    def mock_tool(self):
        """Fixture to create a mock Tool."""
        return MagicMock(spec=Tool)

    def test_init(self, composer):
        """Test AgentComposer initialization."""
        assert composer.agents == {}
        assert composer.tools == {}
        assert composer.workflows == {}
        assert composer.monitor is not None

    def test_register_agent_success(self, composer, mock_agent):
        """Test successful agent registration."""
        agent_name = "test_agent"

        composer.register_agent(agent_name, mock_agent)

        assert agent_name in composer.agents
        assert composer.agents[agent_name] is mock_agent

    def test_register_agent_overwrite(self, composer, mock_agent):
        """Test agent registration overwrites existing agent."""
        agent_name = "test_agent"
        mock_agent2 = MagicMock(spec=Runnable)

        composer.register_agent(agent_name, mock_agent)
        composer.register_agent(agent_name, mock_agent2)

        assert composer.agents[agent_name] is mock_agent2

    def test_register_tool_success(self, composer, mock_tool):
        """Test successful tool registration."""
        tool_name = "test_tool"

        composer.register_tool(tool_name, mock_tool)

        assert tool_name in composer.tools
        assert composer.tools[tool_name] is mock_tool

    def test_register_tool_overwrite(self, composer, mock_tool):
        """Test tool registration overwrites existing tool."""
        tool_name = "test_tool"
        mock_tool2 = MagicMock(spec=Tool)

        composer.register_tool(tool_name, mock_tool)
        composer.register_tool(tool_name, mock_tool2)

        assert composer.tools[tool_name] is mock_tool2

    def test_create_workflow_single_agent(self, composer, mock_agent):
        """Test workflow creation with single agent."""
        agent_name = "test_agent"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[agent_name], tool_names=[])

        composer.register_agent(agent_name, mock_agent)
        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        assert composer.workflows[workflow_name] is workflow
        assert workflow is mock_agent

    def test_create_workflow_multiple_agents(self, composer, mock_agent):
        """Test workflow creation with multiple agents using LCEL composition."""
        agent1_name = "agent1"
        agent2_name = "agent2"
        agent3_name = "agent3"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[agent1_name, agent2_name, agent3_name], tool_names=[])

        mock_agent1 = MagicMock(spec=Runnable)
        mock_agent2 = MagicMock(spec=Runnable)
        mock_agent3 = MagicMock(spec=Runnable)

        # Set up the pipe chain: agent1 | agent2 | agent3
        mock_agent1.__or__ = MagicMock(return_value=mock_agent2)
        mock_agent2.__or__ = MagicMock(return_value=mock_agent3)

        composer.register_agent(agent1_name, mock_agent1)
        composer.register_agent(agent2_name, mock_agent2)
        composer.register_agent(agent3_name, mock_agent3)

        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        assert composer.workflows[workflow_name] is workflow
        # Verify the pipe operations were called correctly
        mock_agent1.__or__.assert_called_once_with(mock_agent2)
        mock_agent2.__or__.assert_called_once_with(mock_agent3)

    def test_create_workflow_with_tools(self, composer, mock_agent, mock_tool):
        """Test workflow creation with tools (tools are retrieved but not directly used in composition)."""
        agent_name = "test_agent"
        tool_name = "test_tool"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[agent_name], tool_names=[tool_name])

        composer.register_agent(agent_name, mock_agent)
        composer.register_tool(tool_name, mock_tool)

        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        assert composer.workflows[workflow_name] is workflow

    def test_create_workflow_no_agents_raises_error(self, composer):
        """Test workflow creation fails when no agents are specified."""
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[], tool_names=[])

        with pytest.raises(ValueError, match="No valid agents found for workflow"):
            composer.create_workflow(workflow_name, config)

    def test_create_workflow_invalid_agent_names(self, composer, mock_agent):
        """Test workflow creation with only invalid agent names."""
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=["invalid_agent1", "invalid_agent2"], tool_names=[])

        with pytest.raises(ValueError, match="No valid agents found for workflow"):
            composer.create_workflow(workflow_name, config)

    def test_create_workflow_partial_invalid_agents(self, composer, mock_agent):
        """Test workflow creation with some invalid agent names."""
        valid_agent_name = "valid_agent"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=["invalid_agent1", valid_agent_name, "invalid_agent2"], tool_names=[])

        composer.register_agent(valid_agent_name, mock_agent)

        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        assert composer.workflows[workflow_name] is mock_agent

    def test_create_workflow_empty_config(self, composer):
        """Test workflow creation with empty configuration."""
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[], tool_names=[])

        with pytest.raises(ValueError, match="No valid agents found for workflow"):
            composer.create_workflow(workflow_name, config)

    def test_create_workflow_duplicate_agent_names(self, composer, mock_agent):
        """Test workflow creation with duplicate agent names in config."""
        agent_name = "test_agent"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[agent_name, agent_name], tool_names=[])

        composer.register_agent(agent_name, mock_agent)

        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        # Should handle duplicates gracefully (agents list will have duplicates)
        assert len([a for a in config.agent_names if a in composer.agents]) == 2

    def test_create_workflow_invalid_tool_names_ignored(self, composer, mock_agent, mock_tool):
        """Test workflow creation ignores invalid tool names."""
        agent_name = "test_agent"
        valid_tool_name = "valid_tool"
        workflow_name = "test_workflow"
        config = WorkflowConfig(agent_names=[agent_name], tool_names=[valid_tool_name, "invalid_tool"])

        composer.register_agent(agent_name, mock_agent)
        composer.register_tool(valid_tool_name, mock_tool)

        workflow = composer.create_workflow(workflow_name, config)

        assert workflow_name in composer.workflows
        # Should succeed even with invalid tool names

    def test_create_workflow_overwrite_existing(self, composer, mock_agent):
        """Test workflow creation overwrites existing workflow."""
        agent_name = "test_agent"
        workflow_name = "test_workflow"
        config1 = WorkflowConfig(agent_names=[agent_name], tool_names=[])
        config2 = WorkflowConfig(agent_names=[agent_name], tool_names=[])

        mock_agent2 = MagicMock(spec=Runnable)

        composer.register_agent(agent_name, mock_agent)
        workflow1 = composer.create_workflow(workflow_name, config1)

        composer.register_agent(agent_name, mock_agent2)  # Change agent
        workflow2 = composer.create_workflow(workflow_name, config2)

        assert composer.workflows[workflow_name] is workflow2
        assert workflow1 is not workflow2