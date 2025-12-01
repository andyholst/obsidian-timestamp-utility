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
        """Create a composable workflow from agents and tools using advanced LCEL composition patterns."""
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

        # Bind tools to agents that support tool binding (advanced LCEL pattern)
        bound_agents = []
        for agent in agents:
            if hasattr(agent, 'bind_tools') and tools:
                # Bind tools to LangChain agents that support it
                bound_agents.append(agent.bind_tools(tools))
            else:
                # Use agent as-is (e.g., ToolIntegratedAgent already has tools integrated)
                bound_agents.append(agent)

        # Create sequential chain using LCEL pipe operator for composability
        workflow = bound_agents[0]
        for agent in bound_agents[1:]:
            workflow = workflow | agent  # LCEL composition

        self.workflows[name] = workflow

        self.monitor.info("workflow_created", {
            "workflow_name": name,
            "agent_count": len(agents),
            "tool_count": len(tools),
            "agents": config.agent_names,
            "tools": config.tool_names,
            "tool_binding_applied": any(hasattr(agent, 'bind_tools') for agent in agents)
        })

        return workflow