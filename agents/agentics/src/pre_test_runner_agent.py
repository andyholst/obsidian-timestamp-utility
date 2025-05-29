import logging
import os
import re
import subprocess
from typing import Dict
import json

from .base_agent import BaseAgent
from .state import State

class PreTestRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("PreTestRunner")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.install_command = os.getenv('INSTALL_COMMAND', 'npm install')
        self.test_command = os.getenv('TEST_COMMAND', 'npm test')
        self.logger.setLevel(logging.INFO)
        self.logger.info(f"Initialized with project_root={self.project_root}, install_command={self.install_command}, test_command={self.test_command}")

    def strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting pre-test runner process")

        if self.install_command == 'npm install' and self.test_command == 'npm test':
            package_json_path = os.path.join(self.project_root, 'package.json')
            if not os.path.isfile(package_json_path):
                self.logger.error(f"package.json not found at {package_json_path}")
                raise RuntimeError("Install command failed")

        self.logger.info(f"Running install command: {self.install_command} in {self.project_root}")
        try:
            install_result = subprocess.run(
                self.install_command.split(),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"Install stdout: {install_result.stdout}")
            if install_result.stderr:
                self.logger.info(f"Install stderr: {install_result.stderr}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Install command failed: {e.stderr}")
            raise RuntimeError(f"Install command failed: {e.stderr}")

        self.logger.info(f"Running test command: {self.test_command} in {self.project_root}")
        try:
            test_result = subprocess.run(
                self.test_command.split(),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            combined_output = self.strip_ansi_codes(test_result.stdout + test_result.stderr)
            self.logger.info(f"Combined test output: {combined_output}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Test command failed: {e.stderr}")
            raise RuntimeError(f"Existing tests failed: {e.stderr}")

        tests_passed_match = re.search(r'Tests:.*?(\d+)\s*passed,\s*(\d+)\s*total', combined_output, re.DOTALL)
        coverage_match = re.search(r'All files\s*\|\s*(\d+\.\d+|\d+)', combined_output)

        tests_passed = int(tests_passed_match.group(1)) if tests_passed_match else 0
        tests_total = int(tests_passed_match.group(2)) if tests_passed_match else 0
        coverage_all_files = float(coverage_match.group(1)) if coverage_match else 0.0

        if tests_passed == 0 and tests_total > 0:
            self.logger.warning("No passing tests detected despite tests running")
        elif tests_total == 0:
            self.logger.warning("No tests detected; test command may not have executed correctly")

        state['existing_tests_passed'] = tests_passed
        state['existing_coverage_all_files'] = coverage_all_files
        self.logger.info(f"Extracted metrics: tests_passed={tests_passed}, coverage_all_files={coverage_all_files}")
        self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state
