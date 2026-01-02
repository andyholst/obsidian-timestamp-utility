import json
import os
import logging
import re
import glob
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import read_file_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool, write_file_tool, execute_command_tool
from .state import State
from .utils import safe_json_dumps, log_info

class DependencyAnalyzerAgent(ToolIntegratedAgent):
    def __init__(self, llm_client=None):
        super().__init__(llm_client, [read_file_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool, write_file_tool], "DependencyAnalyzer")

        self.system_prompt = "Scan only files in /src/ and package.json; ignore node_modules and other directories."

    def process(self, state: State) -> State:
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting dependency analysis")
        try:
            project_root = state.get('project_root') or '/project'
            if not project_root:
                self.monitor.warning("No project_root, skipping dependency analysis")
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
            # JS dependency detection
            all_deps = set(packages_data.get('dependencies', {}).keys()) | set(packages_data.get('devDependencies', {}).keys())
            js_files = (glob.glob(os.path.join(project_root, 'src', '**', '*.ts'), recursive=True) +
                        glob.glob(os.path.join(project_root, 'src', '**', '*.js'), recursive=True) +
                        glob.glob(os.path.join(project_root, 'src', '**', '*.jsx'), recursive=True) +
                        glob.glob(os.path.join(project_root, 'src', '**', '*.tsx'), recursive=True))
            detected_deps = set()
            for file_path in js_files:
                try:
                    content = self.tool_executor.execute_tool('read_file_tool', {'file_path': file_path})
                    import_patterns = [
                        r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",  # import ... from 'pkg'
                        r"from\s+['\"]([^'\"]+)['\"]",  # from 'pkg'
                        r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",  # require('pkg')
                    ]
                    for pattern in import_patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            if isinstance(match, tuple):
                                dep = match[0]
                            else:
                                dep = match
                            dep = dep.split('/')[0]  # take base package
                            detected_deps.add(dep)
                            if dep.startswith('.') or dep.startswith('..') or '/' not in dep.split('/')[-1] or re.match(r'^\.{1,2}/', dep): continue  # Skip relative/local
                            if dep == 'obsidian': continue  # Skip 'obsidian' as it's a special runtime dep already handled
                except Exception as e:
                    log_info(self.name, f"Error reading {file_path}: {e}")
            missing_deps = detected_deps - all_deps
            proposed_js_deps = []
            for dep in missing_deps:
                try:
                    search_result = self.tool_executor.execute_tool('npm_search_tool', {'package_name': dep})
                    version = search_result.get('version', 'latest')
                    patch = {"op": "add", "path": f"/dependencies/{dep}", "value": f"^{version}"}
                    npm_cmd = f"npm i {dep} --save"
                    proposed_js_deps.append({"dep": dep, "patch": patch, "npm_cmd": npm_cmd})
                except Exception as e:
                    log_info(self.name, f"Error searching {dep}: {e}")
            state['proposed_js_deps'] = proposed_js_deps
            # Dependency analysis should ONLY propose deps in state['proposed_js_deps'] = proposed_js_deps WITHOUT modifying files or running npm. Later agents (pre_test_runner, code_integrator) handle installs.
            log_info(self.name, f"Available dependencies: {list(all_deps)}")

            state['available_dependencies'] = list(all_deps)
            log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
            return state
        except Exception as e:
            self.monitor.error(f"Error during dependency analysis: {str(e)}")
            raise
