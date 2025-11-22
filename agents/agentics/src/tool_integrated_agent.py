import logging
from typing import List, Dict, Any, Optional
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from .base_agent import BaseAgent
from .state import State
from .config import LOGGER_LEVEL
from .tools import ToolExecutor


class ToolIntegratedAgent(BaseAgent):
    """
    Agent with integrated tool support following LangChain patterns.
    """

    def __init__(self, llm: Runnable, tools: List[BaseTool]):
        super().__init__("ToolIntegratedAgent")  # BaseAgent requires name
        self.llm = llm
        self.tools = tools
        self.tool_executor = ToolExecutor(tools)

    def process_with_tools(self, state: State) -> State:
        """Process state with tool integration."""

        # Create tool-augmented prompt
        tool_context = self._gather_tool_context(state)

        # Use LLM with tool context
        response = self.llm.invoke(
            self._create_tool_augmented_prompt(state, tool_context)
        )

        # Execute tools if needed
        if self._needs_tool_execution(response):
            tool_results = self.tool_executor.execute(response)
            response = self.llm.invoke(
                self._create_followup_prompt(response, tool_results)
            )

        return self._update_state_with_response(state, response)

    def _gather_tool_context(self, state: State) -> Dict[str, Any]:
        """Gather tool context from state."""
        return {
            "available_tools": [tool.name for tool in self.tools],
            "tool_descriptions": {tool.name: tool.description for tool in self.tools}
        }

    def _create_tool_augmented_prompt(self, state: State, tool_context: Dict[str, Any]) -> str:
        """Create a tool-augmented prompt."""
        base_prompt = f"Process the following state: {state}"

        if not self.tools:
            return base_prompt

        tool_section = "\n\nAvailable Tools:\n"
        for tool_name, description in tool_context["tool_descriptions"].items():
            tool_section += f"- {tool_name}: {description}\n"

        tool_section += "\nWhen you need to use a tool, respond with a tool call."

        return base_prompt + tool_section

    def _create_followup_prompt(self, response: Any, tool_results: Dict[str, Any]) -> str:
        """Create a followup prompt with tool results."""
        prompt = f"Previous response: {response}\n\nTool results:\n"
        for tool_name, result in tool_results.items():
            prompt += f"- {tool_name}: {result}\n"
        prompt += "\nContinue processing based on the tool results."
        return prompt

    def _needs_tool_execution(self, response: Any) -> bool:
        """Determine if tools need to be executed based on response."""
        return hasattr(response, 'tool_calls') and response.tool_calls

    def _update_state_with_response(self, state: State, response: Any) -> State:
        """Update state with the final response."""
        state['tool_integrated_response'] = response.content if hasattr(response, 'content') else str(response)
        return state