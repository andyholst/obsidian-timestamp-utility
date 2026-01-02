import logging
import os
import re
import subprocess
from typing import Dict
import json
import time
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base_agent import BaseAgent
from .state import State
from .utils import safe_json_dumps, log_info
from .tools import ToolExecutor, typescript_typecheck_tool
from .exceptions import CompileError

class PreTestRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("PreTestRunner")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.install_command = os.getenv('INSTALL_COMMAND', 'npm install')
        self.test_command = os.getenv('TEST_COMMAND', 'npm test')
        self.monitor.logger.setLevel(logging.INFO)
        self.monitor.info(f"Initialized with project_root={self.project_root}, install_command={self.install_command}, test_command={self.test_command}")
        self.tools = []
        self.tools.append(typescript_typecheck_tool)
        self.tool_executor = ToolExecutor(self.tools)

    def strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def process(self, state: State) -> State:
        self.monitor.info(f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        self.monitor.info("Starting pre-test runner process")

        # Debug logging for permissions and paths
        log_info(self.name, f"PROJECT_ROOT: {self.project_root}")
        log_info(self.name, f"Current working directory: {os.getcwd()}")
        log_info(self.name, f"Current user: {os.getuid() if hasattr(os, 'getuid') else 'unknown'}")
        log_info(self.name, f"Install command: {self.install_command}")
        log_info(self.name, f"Test command: {self.test_command}")
        self.monitor.info("About to check npm install conditions")

        if self.install_command == 'npm install' and self.test_command == 'npm test':
            package_json_path = os.path.join(self.project_root, 'package.json')
            self.monitor.info(f"package_json_path: {package_json_path}")
            exists = os.path.isfile(package_json_path)
            self.monitor.info(f"package.json exists: {exists}")
            log_info(self.name, f"Checking for package.json at: {package_json_path}")
            if not exists:
                self.monitor.warning(f"package.json not found at {package_json_path}, skipping install/test and setting default metrics")
                state['existing_tests_passed'] = 0
                state['existing_coverage_all_files'] = 0.0
                self.monitor.info(f"Extracted default metrics: tests_passed=0, coverage_all_files=0.0")
                self.monitor.info(f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
                return state

        log_info(self.name, f"Running install command: {self.install_command} in {self.project_root}")
        import shutil
        node_modules_path = os.path.join(self.project_root, 'node_modules')
        log_info(self.name, f"Node modules path: {node_modules_path}")
        log_info(self.name, f"Node modules exists: {os.path.exists(node_modules_path)}")

        # Check permissions before attempting to remove
        if os.path.exists(node_modules_path):
            try:
                test_file = os.path.join(node_modules_path, 'test_write.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                log_info(self.name, "Write permissions confirmed for node_modules")
            except (OSError, PermissionError) as e:
                log_info(self.name, f"No write permissions for node_modules: {e}")
                # Try to fix permissions, but don't fail if it doesn't work
                try:
                    result = os.system(f'chmod -R 777 {node_modules_path}')
                    if result == 0:
                        log_info(self.name, "Successfully fixed permissions with chmod")
                    else:
                        log_info(self.name, f"chmod command failed with exit code {result}, continuing anyway")
                except Exception as chmod_e:
                    log_info(self.name, f"Failed to fix permissions: {chmod_e}, continuing anyway")

        shutil.rmtree(node_modules_path, ignore_errors=True)
        log_info(self.name, f"Removed node_modules directory (if existed)")
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(subprocess.CalledProcessError))
        def run_install():
            # Ensure project directory has proper permissions
            try:
                os.chmod(self.project_root, 0o755)
                log_info(self.name, f"Set project directory permissions to 755")
            except Exception as perm_e:
                log_info(self.name, f"Could not set project directory permissions: {perm_e}")

            # Ensure PATH includes /usr/bin for git
            original_path = os.environ.get('PATH', '')
            os.environ['PATH'] = '/usr/bin:' + original_path
            log_info(self.name, f"Updated PATH to include /usr/bin: {os.environ['PATH']}")

            # Check if git is available
            git_available = False
            try:
                subprocess.run(['git', '--version'], capture_output=True, check=True)
                git_available = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                git_available = False

            # Try npm install like in tool.yaml
            install_cmd = self.install_command.split()
            if install_cmd[0] == 'npm' and len(install_cmd) >= 2 and install_cmd[1] == 'install':
                install_cmd.extend(['--loglevel=silly'])

            log_info(self.name, f"Running install command: {' '.join(install_cmd)}")
            install_result = subprocess.run(
                install_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            log_info(self.name, f"Install command completed successfully")
            log_info(self.name, f"Install stdout length: {len(install_result.stdout)}")
            if install_result.stderr:
                log_info(self.name, f"Install stderr length: {len(install_result.stderr)}")
            return install_result

        try:
            run_install()
        except subprocess.CalledProcessError as e:
            self.monitor.error(f"Install command failed with return code {e.returncode}")
            self.monitor.error(f"Install stderr: {e.stderr}")
            raise RuntimeError(f"Install command failed: {e.stderr}")

        self.monitor.info(f"Running TypeScript typecheck in {self.project_root}")
        tsc_result = self.tool_executor.execute_tool('typescript_typecheck_tool', {'cwd': self.project_root})
        if 'error' in tsc_result.lower():
            raise CompileError(f"tsc failed: {tsc_result}")
        self.monitor.info("TypeScript typecheck passed.")
        self.monitor.info("tsc execution completed, proceeding to npm test")
        log_info(self.name, f"Running test command: {self.test_command} in {self.project_root}")
        combined_output = ""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                log_info(self.name, f"Running test command (attempt {attempt + 1}/{max_retries}): {self.test_command}")
                test_result = subprocess.run(
                    self.test_command.split(),
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    check=True
                )
                combined_output = self.strip_ansi_codes(test_result.stdout + test_result.stderr)
                log_info(self.name, f"Test command completed successfully")
                log_info(self.name, f"Combined test output length: {len(combined_output)}")
                break  # Success, exit retry loop
            except subprocess.CalledProcessError as e:
                stdout = e.stdout or ''
                stderr = e.stderr or ''
                combined_output = self.strip_ansi_codes(stdout + stderr)
                self.monitor.error(f"Test command failed on attempt {attempt + 1}/{max_retries} with return code {e.returncode}")
                self.monitor.error(f"Test stdout: {stdout}")
                self.monitor.error(f"Test stderr: {stderr}")
                self.monitor.error(f"Test combined output: {combined_output}")
                if attempt < max_retries - 1:
                    wait_time = min(1 * (2 ** attempt), 10)  # Exponential backoff
                    self.monitor.info(f"Retrying test command in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Final failure - log to file but continue gracefully for existing metrics
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_file = os.path.join(self.project_root, 'results', f"test_failure_pre_{timestamp}.log")
                    os.makedirs(os.path.dirname(log_file), exist_ok=True)
                    with open(log_file, 'w') as f:
                        f.write(combined_output)
                    self.monitor.warning(f"npm test failed after {max_retries} attempts (rc={e.returncode}). Log saved to {log_file}. Using parsed metrics from output.")

        log_info(self.name, "Parsing test output for metrics")
        tests_passed_match = re.search(r'Tests:.*?(\d+)\s*passed,\s*(\d+)\s*total', combined_output, re.DOTALL)
        coverage_match = re.search(r'All files\s*\|\s*(\d+\.\d+|\d+)', combined_output)

        tests_passed = int(tests_passed_match.group(1)) if tests_passed_match else 0
        tests_total = int(tests_passed_match.group(2)) if tests_passed_match else 0
        coverage_all_files = float(coverage_match.group(1)) if coverage_match else 0.0

        log_info(self.name, f"Parsed tests_passed: {tests_passed}, tests_total: {tests_total}, coverage: {coverage_all_files}")

        if tests_passed == 0 and tests_total > 0:
            self.monitor.warning("No passing tests detected despite tests running")
        elif tests_total == 0:
            self.monitor.warning("No tests detected; test command may not have executed correctly")

        state['existing_tests_passed'] = tests_passed
        state['existing_coverage_all_files'] = coverage_all_files
        self.monitor.info(f"Extracted metrics: tests_passed={tests_passed}, coverage_all_files={coverage_all_files}")
        self.monitor.info(f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        return state
