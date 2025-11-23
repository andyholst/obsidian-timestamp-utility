from typing import Dict, List
from dataclasses import dataclass
from langchain.schema.runnable import Runnable
from langchain.tools import Tool
from .monitoring import structured_log, track_workflow_progress


@dataclass
class WorkflowConfig:
    """Configuration for creating a composable workflow."""
    agent_names: List[str]
    tool_names: List[str]


class AgentComposer:
    """Composable agent system following LangChain patterns."""

    def __init__(self):
        self.agents: Dict[str, Runnable] = {}
        self.tools: Dict[str, Tool] = {}
        self.workflows: Dict[str, Runnable] = {}
        self.monitor = structured_log("agent_composer")

    def register_agent(self, name: str, agent: Runnable) -> None:
        """Register an agent in the composition system."""
        self.agents[name] = agent
        self.monitor.info("agent_registered", {"agent_name": name})

    def register_tool(self, name: str, tool: Tool) -> None:
        """Register a tool for agent use."""
        self.tools[name] = tool
        self.monitor.info("tool_registered", {"tool_name": name})

    def create_workflow(self, name: str, config: WorkflowConfig) -> Runnable:
        """Create a composable workflow from agents and tools using LCEL composition patterns."""
        # Retrieve agents and tools from registry
        agents = [self.agents[agent_name] for agent_name in config.agent_names if agent_name in self.agents]
        tools = [self.tools[tool_name] for tool_name in config.tool_names if tool_name in self.tools]

        if not agents:
            self.monitor.error("workflow_creation_failed", {
                "workflow_name": name,
                "reason": "No valid agents found",
                "requested_agents": config.agent_names
            })
            raise ValueError(f"No valid agents found for workflow '{name}'. Check agent names in config.")

        # For simplicity, create a sequential chain of agents
        # In practice, tools might need to be bound to agents individually
        workflow = agents[0]
        for agent in agents[1:]:
            workflow = workflow | agent  # LCEL composition using pipe operator

        self.workflows[name] = workflow

        self.monitor.info("workflow_created", {
            "workflow_name": name,
            "agent_count": len(agents),
            "tool_count": len(tools),
            "agents": config.agent_names,
            "tools": config.tool_names
        })

        return workflow