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
    Search for npm packages and return version info.

    Args:
        package_name: Name of the package to search for

    Returns:
        Dict with 'version' key
    """
    from functools import lru_cache
    import requests
    import json

    @lru_cache(maxsize=128)
    def _search(package_name: str) -> dict:
        try:
            url = f"https://registry.npmjs.org/-/v1/search?text={package_name}&size=1"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'objects' in data and data['objects']:
                    version = data['objects'][0]['package']['version']
                    return json.dumps([{'name': package_name, 'version': version}])
        except Exception as e:
            pass
        return json.dumps([])

    return _search(package_name)


@tool
def npm_install_tool(package_name: str = "", is_dev: bool = False, save_exact: bool = False, cwd: str = "") -> str:
    """
    Install an npm package or all dependencies if no package specified.

    Args:
        package_name: Name of the package to install (empty string to install all dependencies)
        is_dev: Whether to install as dev dependency (default: False)
        save_exact: Whether to save exact version (default: False)
        cwd: Working directory to run the command in (default: project root)

    Returns:
        Success message or error details
    """
    import subprocess
    import os
    try:
        cmd = ['npm', 'install']
        if is_dev:
            cmd.append('--save-dev')
        if save_exact:
            cmd.append('--save-exact')
        if package_name:
            cmd.append(package_name)

        # Set working directory - default to project root if not provided
        project_root = os.getenv('PROJECT_ROOT', '/project')
        cwd_path = cwd if cwd else project_root

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd_path)

        if result.returncode == 0:
            if package_name:
                return f"Successfully installed {package_name}"
            else:
                return "Successfully installed all dependencies"
        else:
            if package_name:
                return f"Failed to install {package_name}: {result.stderr}"
            else:
                return f"Failed to install dependencies: {result.stderr}"
    except Exception as e:
        return f"Error installing npm package: {str(e)}"


@tool
def npm_list_tool(depth: int = 0, cwd: str = "") -> str:
    """
    List installed npm packages.

    Args:
        depth: Depth of dependency tree to show (0 for top-level only, default: 0)

    Returns:
        JSON string with installed packages information
    """
    import os
    import subprocess
    import json
    try:
        cmd = ['npm', 'list', '--json']
        if depth > 0:
            cmd.extend(['--depth', str(depth)])

        project_root = os.getenv('PROJECT_ROOT', '/project')
        cwd_path = cwd if cwd else project_root
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd_path)

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
@tool
def write_file_tool(file_path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        file_path: Relative path to the file from project root
        content: Content to write to the file

    Returns:
        Success message or error details
    """
    import os
    from .monitoring import structured_log
    monitor = structured_log("write_file_tool")
    project_root = os.getenv('PROJECT_ROOT', '/project')
    full_path = os.path.join(project_root, file_path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        monitor.info("File written successfully")
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        monitor.error(f"Error writing to file {file_path}: {str(e)}")
        return f"Error writing to file {file_path}: {str(e)}"


@tool
def npm_run_tool(script: str, args: str = "", cwd: str = "") -> str:
    """
    Run an npm script.

    Args:
        script: The npm script to run (e.g., 'test', 'build')
        args: Additional arguments for the script
        cwd: Working directory to run the command in (default: project root)

    Returns:
        Output of the npm run command or error details
    """
    import subprocess
    import os
    try:
        cmd = ['npm', 'run', script]
        if args:
            cmd.extend(args.split())

        # Set working directory - default to project root if not provided
        project_root = os.getenv('PROJECT_ROOT', '/project')
        cwd_path = cwd if cwd else project_root

        # Add logging to validate cwd
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"npm_run_tool: Running in cwd: {cwd_path}, cmd: {cmd}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=cwd_path)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"npm run {script} failed: {result.stderr}"
    except Exception as e:
        return f"Error running npm script {script}: {str(e)}"


@tool
def typescript_typecheck_tool(cwd: str = "") -> str:
    """
    Perform TypeScript typecheck using `npx tsc --noEmit`.
    Args:
        cwd: Working directory to run the command in (default: project root).
    
    Returns:
        "TypeScript typecheck passed." if successful.
    
    Raises:
        CompileError if there are TypeScript errors.
    """
    import os
    import subprocess
    import logging
    from .exceptions import CompileError
    
    project_root = os.getenv('PROJECT_ROOT', '/project')
    cwd_path = cwd if cwd else project_root
    
    cmd = ['npx', 'tsc', '--noEmit']
    logger = logging.getLogger(__name__)
    logger.info(f"typescript_typecheck_tool: Running in cwd: {cwd_path}, cmd: {cmd}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd_path)
    if result.returncode == 0:
        return "TypeScript typecheck passed."
    else:
        logger.warning(f"tsc stdout: {result.stdout[:1000]}")
        logger.warning(f"tsc stderr: {result.stderr[:1000]}")
        raise CompileError(f"TypeScript errors:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}")

@tool
def execute_command_tool(command: str, cwd: str = "") -> str:
    """
    Execute a CLI command.

    Args:
        command: The command to execute
        cwd: Working directory to run the command in (default: project root)

    Returns:
        Output of the command or error details
    """
    import subprocess
    import os
    try:
        project_root = os.getenv('PROJECT_ROOT', '/project')
        cwd_path = cwd if cwd else project_root
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd_path)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Command failed: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Export tools for use by agents
__all__ = ['ToolExecutor', 'read_file_tool', 'list_files_tool', 'check_file_exists_tool', 'npm_search_tool', 'npm_install_tool', 'npm_list_tool', 'write_file_tool', 'npm_run_tool', 'typescript_typecheck_tool', 'execute_command_tool']


