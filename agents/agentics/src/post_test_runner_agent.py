import logging
import os
import re
from typing import Dict, List
import json
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_core.runnables import Runnable

from .tools import check_file_exists_tool, write_file_tool, npm_install_tool, npm_run_tool
from .tool_integrated_agent import ToolIntegratedAgent
from .state import State
from .utils import safe_json_dumps, log_info

class PostTestRunnerAgent(ToolIntegratedAgent):
    def __init__(self, llm: Runnable):
        super().__init__(llm, [npm_install_tool, npm_run_tool, check_file_exists_tool, write_file_tool], name="PostTestRunner")
        self.project_root = os.getenv('PROJECT_ROOT')
        if not self.project_root:
            raise ValueError("PROJECT_ROOT environment variable is required")
        self.install_command = os.getenv('INSTALL_COMMAND', 'npm install')
        self.test_command = os.getenv('TEST_COMMAND', 'npm test')
        self.monitor.logger.setLevel(logging.INFO)
        self.monitor.info(f"Initialized with project_root={self.project_root}, install_command={self.install_command}, test_command={self.test_command}")

    def strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def process(self, state: State) -> State:
        self.monitor.info(f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        self.monitor.info("Starting post-test runner process")
        log_info(self.name, f"Using project_root: {self.project_root}")
        log_info(self.name, f"existing_tests_passed from state: {state.get('existing_tests_passed', 0)}")

        if self.install_command == 'npm install' and self.test_command == 'npm test':
            package_json_path = os.path.join(self.project_root, 'package.json')
            log_info(self.name, f"Checking for package.json at: {package_json_path}")
            exists = self.tool_executor.execute_tool('check_file_exists_tool', {'file_path': package_json_path})
            if not exists:
                self.monitor.error(f"package.json not found at {package_json_path}")
                raise RuntimeError("Install command failed")

        log_info(self.name, f"Running install command: {self.install_command} in {self.project_root}")
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
        def run_install():
            result = self.tool_executor.execute_tool('npm_install_tool', {'package_name': '', 'is_dev': False, 'save_exact': False})
            if not result.startswith("Successfully"):
                raise RuntimeError(f"Install failed: {result}")
            log_info(self.name, f"Install command completed successfully: {result}")
            return result

        try:
            run_install()
        except Exception as e:
            self.monitor.error(f"Install command failed: {str(e)}")
            raise RuntimeError(f"Install command failed: {str(e)}")

        log_info(self.name, f"Running test command: {self.test_command} in {self.project_root}")
        combined_output = ""
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
        def run_test():
            result = self.tool_executor.execute_tool('npm_run_tool', {'script': 'test', 'args': ''})
            if result.startswith("npm run test failed:"):
                raise RuntimeError(f"Test failed: {result}")
            return self.strip_ansi_codes(result)

        try:
            combined_output = run_test()
            log_info(self.name, f"Test command completed successfully")
            log_info(self.name, f"Combined test output length: {len(combined_output)}")
        except Exception as e:
            combined_output = self.strip_ansi_codes(str(e))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.project_root, f"test_failure_post_{timestamp}.log")
            with open(log_file, 'w') as f:
                f.write(combined_output)
            self.monitor.error(f"Test command failed: {str(e)}")
            self.monitor.error(f"Test command failed. Full output logged to {log_file}: {combined_output[:500]}...")
            raise RuntimeError(f"Post-integration tests failed. See {log_file} for details.")

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

        # Compare with pre-integration results
        existing_tests_passed = state.get('existing_tests_passed', 0)
        existing_coverage = state.get('existing_coverage_all_files', 0.0)

        coverage_improvement = coverage_all_files - existing_coverage
        tests_improvement = tests_passed - existing_tests_passed

        log_info(self.name, f"Comparing with pre-integration: existing_tests={existing_tests_passed}, existing_coverage={existing_coverage}")
        log_info(self.name, f"Improvement calculated: coverage +{coverage_improvement:.2f}%, tests +{tests_improvement}")

        state['post_integration_tests_passed'] = tests_passed
        state['post_integration_coverage_all_files'] = coverage_all_files
        state['coverage_improvement'] = coverage_improvement
        state['tests_improvement'] = tests_improvement

        self.monitor.info(f"Post-integration metrics: tests_passed={tests_passed}, coverage_all_files={coverage_all_files}")
        self.monitor.info(f"Improvement: coverage +{coverage_improvement:.2f}%, tests +{tests_improvement}")
        self.monitor.info(f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        return state
