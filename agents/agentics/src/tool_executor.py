from typing import List, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage

class ToolExecutor:
    """
    Executor for LangChain tools. Supports both single tool execution and batch execution from AIMessage tool_calls.
    """
    def __init__(self, tools: List[BaseTool]):
        self.tools = {tool.name: tool for tool in tools}

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        tool = self.tools[tool_name]
        return tool.invoke(tool_args)

    def execute(self, response: Any) -> Dict[str, str]:
        """
        Execute tool calls from AIMessage response. Returns dict {tool_name: result_str} for followup prompts.
        """
        if not hasattr(response, 'tool_calls') or not response.tool_calls:
            return {}
        results = {}
        for tool_call in response.tool_calls:
            tool_name = tool_call['name']
            args = tool_call['args']
            result = self.execute_tool(tool_name, args)
            results[tool_name] = str(result)
        return results

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())