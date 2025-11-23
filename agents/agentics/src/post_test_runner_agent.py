import logging
import os
import re
import subprocess
from typing import Dict
import json
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base_agent import BaseAgent
from .state import State
from .utils import safe_json_dumps, log_info

class PostTestRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("PostTestRunner")
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

        if self.install_command == 'npm install' and self.test_command == 'npm test':
            package_json_path = os.path.join(self.project_root, 'package.json')
            log_info(self.name, f"Checking for package.json at: {package_json_path}")
            if not os.path.isfile(package_json_path):
                self.monitor.error(f"package.json not found at {package_json_path}")
                raise RuntimeError("Install command failed")

        log_info(self.name, f"Running install command: {self.install_command} in {self.project_root}")
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(subprocess.CalledProcessError))
        def run_install():
            install_result = subprocess.run(
                self.install_command.split(),
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

        log_info(self.name, f"Running test command: {self.test_command} in {self.project_root}")
        combined_output = ""
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(subprocess.CalledProcessError))
        def run_test():
            test_result = subprocess.run(
                self.test_command.split(),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return self.strip_ansi_codes(test_result.stdout + test_result.stderr)

        try:
            combined_output = run_test()
            log_info(self.name, f"Test command completed successfully")
            log_info(self.name, f"Combined test output length: {len(combined_output)}")
        except subprocess.CalledProcessError as e:
            combined_output = self.strip_ansi_codes((e.stdout or '') + (e.stderr or ''))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.project_root, f"test_failure_post_{timestamp}.log")
            with open(log_file, 'w') as f:
                f.write(combined_output)
            self.monitor.error(f"Test command failed with return code {e.returncode}")
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
