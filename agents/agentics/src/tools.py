"""
LangChain tools for file operations used by agents.
"""

import logging
from typing import List, Dict, Any
from langchain_core.tools import tool, BaseTool
from .config import LOGGER_LEVEL
from .monitoring import structured_log


class ToolExecutor:
    """Manages tool execution with error handling and logging."""

    def __init__(self, tools: List[BaseTool]):
        self.tools = {tool.name: tool for tool in tools}
        self.logger = logging.getLogger("ToolExecutor")
        self.monitor = structured_log("ToolExecutor")
        self.monitor.setLevel(LOGGER_LEVEL)

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a tool with error handling."""
        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found"
            self.monitor.error(error_msg)
            raise ValueError(error_msg)

        tool = self.tools[tool_name]
        try:
            self.monitor.info(f"Executing tool: {tool_name} with input: {tool_input}")
            result = tool.invoke(tool_input)
            self.monitor.info(f"Tool {tool_name} executed successfully")
            return result
        except Exception as e:
            error_msg = f"Tool {tool_name} execution failed: {str(e)}"
            self.monitor.error(error_msg)
            raise

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())

    def execute(self, response: Any) -> Dict[str, Any]:
        """Execute tools based on LLM response containing tool calls."""
        results = {}
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get('name')
                tool_input = tool_call.get('args', {})
                try:
                    result = self.execute_tool(tool_name, tool_input)
                    results[tool_name] = result
                except Exception as e:
                    results[tool_name] = f"Error: {str(e)}"
        return results


@tool
def read_file_tool(file_path: str) -> str:
    """
    Read the content of a file from the project root.

    Args:
        file_path: Relative path to the file from project root

    Returns:
        File content as string, or empty string if file not found
    """
    import os
    project_root = os.getenv('PROJECT_ROOT', '/project')
    full_path = os.path.join(project_root, file_path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


@tool
def list_files_tool(directory: str = ".") -> str:
    """
    List files and directories in the specified directory.

    Args:
        directory: Directory path relative to project root (default: ".")

    Returns:
        Comma-separated list of files and directories
    """
    import os
    project_root = os.getenv('PROJECT_ROOT', '/project')
    full_path = os.path.join(project_root, directory)
    try:
        items = os.listdir(full_path)
        return ", ".join(items)
    except Exception as e:
        return f"Error listing directory {directory}: {str(e)}"


@tool
def check_file_exists_tool(file_path: str) -> bool:
    """
    Check if a file exists.

    Args:
        file_path: Relative path to the file from project root

    Returns:
        True if file exists, False otherwise
    """
    import os
    project_root = os.getenv('PROJECT_ROOT', '/project')
    full_path = os.path.join(project_root, file_path)
    return os.path.isfile(full_path)

@tool
def npm_search_tool(package_name: str, limit: int = 5) -> str:
    """
    Search for npm packages and return suggestions with descriptions.

    Args:
        package_name: Name or keyword to search for
        limit: Maximum number of results to return (default: 5)

    Returns:
        JSON string with package suggestions including name, description, and version
    """
    import subprocess
    import json
    try:
        # Use npm search command
        result = subprocess.run(
            ['npm', 'search', package_name, '--json'],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            try:
                packages = json.loads(result.stdout)
                if isinstance(packages, list):
                    # Limit results and format
                    limited_packages = packages[:limit]
                    formatted_results = []
                    for pkg in limited_packages:
                        formatted_results.append({
                            'name': pkg.get('name', ''),
                            'description': pkg.get('description', ''),
                            'version': pkg.get('version', ''),
                            'keywords': pkg.get('keywords', [])
                        })
                    return json.dumps(formatted_results, indent=2)
                else:
                    return json.dumps([packages], indent=2)
            except json.JSONDecodeError:
                return f"Raw search results for '{package_name}': {result.stdout[:500]}"
        else:
            return f"npm search failed: {result.stderr}"
    except Exception as e:
        return f"Error searching npm packages: {str(e)}"


@tool
def npm_install_tool(package_name: str, is_dev: bool = False, save_exact: bool = False) -> str:
    """
    Install an npm package.

    Args:
        package_name: Name of the package to install
        is_dev: Whether to install as dev dependency (default: False)
        save_exact: Whether to save exact version (default: False)

    Returns:
        Success message or error details
    """
    import subprocess
    try:
        cmd = ['npm', 'install']
        if is_dev:
            cmd.append('--save-dev')
        if save_exact:
            cmd.append('--save-exact')
        cmd.append(package_name)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return f"Successfully installed {package_name}"
        else:
            return f"Failed to install {package_name}: {result.stderr}"
    except Exception as e:
        return f"Error installing npm package: {str(e)}"


@tool
def npm_list_tool(depth: int = 0) -> str:
    """
    List installed npm packages.

    Args:
        depth: Depth of dependency tree to show (0 for top-level only, default: 0)

    Returns:
        JSON string with installed packages information
    """
    import subprocess
    import json
    try:
        cmd = ['npm', 'list', '--json']
        if depth > 0:
            cmd.extend(['--depth', str(depth)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            try:
                packages = json.loads(result.stdout)
                return json.dumps(packages, indent=2)
            except json.JSONDecodeError:
                return f"Raw package list: {result.stdout[:1000]}"
        else:
            return f"Failed to list packages: {result.stderr}"
    except Exception as e:
        return f"Error listing npm packages: {str(e)}"


# Export tools for use by agents
__all__ = ['ToolExecutor', 'read_file_tool', 'list_files_tool', 'check_file_exists_tool', 'npm_search_tool', 'npm_install_tool', 'npm_list_tool']
