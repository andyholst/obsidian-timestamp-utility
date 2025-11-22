import json
import os
import logging
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import read_file_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool
from .state import State
from .utils import safe_json_dumps, log_info

class DependencyAnalyzerAgent(ToolIntegratedAgent):
    def __init__(self, llm_client=None):
        super().__init__(llm_client, [read_file_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool])

    def process(self, state: State) -> State:
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting dependency analysis")
        try:
            project_root = state.get('project_root')
            if not project_root:
                self.monitor.warning("No project_root in state, skipping dependency analysis")
                state['available_dependencies'] = []
                return state

            package_json_path = os.path.join(project_root, 'package.json')
            exists = self.tool_executor.execute_tool('check_file_exists_tool', {'file_path': package_json_path})
            if not exists:
                self.monitor.warning(f"package.json not found, skipping dependency analysis")
                state['available_dependencies'] = []
                return state

            # Read package.json content
            content = self.tool_executor.execute_tool('read_file_tool', {'file_path': package_json_path})
            packages_data = json.loads(content)
            if 'devDependencies' in packages_data:
                available_dependencies = list(packages_data['devDependencies'].keys())
            else:
                available_dependencies = []
            log_info(self.name, f"Available dependencies: {available_dependencies}")

            state['available_dependencies'] = available_dependencies
            log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
            return state
        except Exception as e:
            self.monitor.error(f"Error during dependency analysis: {str(e)}")
            raise
