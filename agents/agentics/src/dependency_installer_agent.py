import logging
import os
import json
from typing import Dict, List, Any
from .base_agent import BaseAgent
from .state import CodeGenerationState
from .tools import npm_install_tool, read_file_tool, write_file_tool, check_file_exists_tool
from .tool_executor import ToolExecutor
from .utils import log_info
from .monitoring import structured_log

logger = logging.getLogger(__name__)

class DependencyInstallerAgent(BaseAgent):
    def __init__(self):
        super().__init__("DependencyInstaller")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.tools = [npm_install_tool, read_file_tool, write_file_tool, check_file_exists_tool]
        self.tool_executor = ToolExecutor(self.tools)
        self.monitor = structured_log(self.name)
        self.monitor.info("Initialized", {"project_root": self.project_root})

    def process(self, state: CodeGenerationState) -> CodeGenerationState:
        self.monitor.info("Starting dependency installation")
        log_info(self.name, f"Project root: {self.project_root}")

        npm_packages = getattr(state, 'npm_packages', []) or state.get('npm_packages', [])
        if not npm_packages:
            npm_packages = state.get('refined_ticket', {}).get('npm_packages', [])
            self.monitor.info(f"Using refined_ticket.npm_packages ({len(npm_packages)} pkgs): {npm_packages}")
        if not npm_packages:
            return state

        pkgs = []
        for pkg in npm_packages:
            if isinstance(pkg, dict) and 'name' in pkg:
                pkgs.append(pkg['name'])
            elif isinstance(pkg, str):
                pkgs.append(pkg)
            else:
                self.monitor.warning("invalid_package_format", {"pkg": pkg})

        if not pkgs:
            self.monitor.info("No valid packages to install")
            return state

        self.monitor.info("packages_to_process", {"pkgs": pkgs})

        # Update package.json
        package_json_path = os.path.join(self.project_root, 'package.json')
        if self.tool_executor.execute_tool('check_file_exists_tool', {'file_path': package_json_path}):
            package_json_str = self.tool_executor.execute_tool('read_file_tool', {'file_path': package_json_path})
            try:
                package_json = json.loads(package_json_str)
                dependencies = package_json.setdefault('dependencies', {})
                added = []
                for pkg_name in pkgs:
                    if pkg_name not in dependencies:
                        dependencies[pkg_name] = '*'
                        added.append(pkg_name)
                if added:
                    package_json['dependencies'] = dependencies
                    new_package_json_str = json.dumps(package_json, indent=2)
                    self.tool_executor.execute_tool('write_file_tool', {
                        'file_path': package_json_path,
                        'content': new_package_json_str
                    })
                    self.monitor.info("package_json_updated", {"added": added})
            except json.JSONDecodeError as e:
                self.monitor.warning("package_json_parse_failed", {"error": str(e)})
            except Exception as e:
                self.monitor.warning("package_json_update_failed", {"error": str(e)})
        else:
            self.monitor.warning("no_package_json", {})

        # Install packages
        installed = []
        for pkg_name in pkgs:
            try:
                self.tool_executor.execute_tool('npm_install_tool', {
                    'package_name': pkg_name,
                    'is_dev': False,
                    'save_exact': True,
                    'cwd': self.project_root
                })
                installed.append(pkg_name)
                log_info(self.name, f"Installed {pkg_name}")
            except Exception as e:
                self.monitor.warning("install_failed", {"pkg": pkg_name, "error": str(e)})
                log_info(self.name, f"Failed to install {pkg_name}: {str(e)}")

        state['installed_deps'] = installed
        self.monitor.info("installation_complete", {
            "total": len(pkgs),
            "installed": len(installed),
            "pkgs": installed
        })
        log_info(self.name, f"Installed {len(installed)}/{len(pkgs)} packages: {installed}")
        return state