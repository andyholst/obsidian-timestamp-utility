# pre_test_runner_agent.py
import logging
import os
import re
import subprocess
from .base_agent import BaseAgent
from .state import State

class PreTestRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("PreTestRunner")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.install_command = os.getenv('INSTALL_COMMAND', 'npm install')
        self.test_command = os.getenv('TEST_COMMAND', 'npm test')
        self.logger.setLevel(logging.INFO)

    def strip_ansi_codes(self, text: str) -> str:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def process(self, state: State) -> State:
        try:
            subprocess.run(self.install_command.split(), cwd=self.project_root, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Install failed: {e.stderr}")

        try:
            test_result = subprocess.run(self.test_command.split(), cwd=self.project_root, capture_output=True, text=True, check=True)
            combined_output = self.strip_ansi_codes(test_result.stdout + test_result.stderr)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Tests failed: {e.stderr}")

        tests_passed_match = re.search(r'Tests:.*?(\d+)\s*passed,\s*(\d+)\s*total', combined_output, re.DOTALL)
        coverage_match = re.search(r'All files\s*\|\s*(\d+\.\d+|\d+)', combined_output)

        tests_passed = int(tests_passed_match.group(1)) if tests_passed_match else 0
        state['existing_tests_passed'] = tests_passed
        state['existing_coverage_all_files'] = float(coverage_match.group(1)) if coverage_match else 0.0
        return state
