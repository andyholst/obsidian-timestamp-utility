import subprocess
import re
import logging
import json

from .base_agent import BaseAgent
from .state import State

class PreTestRunnerAgent(BaseAgent):
    def __init__(self, project_root="/project"):
        super().__init__("PreTestRunner")
        self.project_root = project_root
        self.logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def strip_ansi_codes(self, text):
        """Remove ANSI escape sequences (e.g., color codes) from the text."""
        self.logger.info("Stripping ANSI codes from text")
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned_text = ansi_escape.sub('', text)
        self.logger.info(f"Text after stripping ANSI codes: {cleaned_text}")
        return cleaned_text

    def process(self, state: State) -> State:
        """
        Execute existing TypeScript tests, verify they pass, and extract test metrics.
        """
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting pre-test runner process")
        try:
            # Run npm install to ensure dependencies are available
            self.logger.info("Running npm install")
            install_result = subprocess.run(
                ["npm", "install", "--loglevel=silly"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            self.logger.info(f"npm install stdout: {install_result.stdout}")
            self.logger.info(f"npm install stderr: {install_result.stderr}")
            if install_result.returncode != 0:
                self.logger.error(f"npm install failed: {install_result.stderr}")
                raise RuntimeError("npm install failed")

            # Run npm test
            self.logger.info("Running npm test")
            test_result = subprocess.run(
                ["npm", "test"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            self.logger.info(f"npm test stdout: {test_result.stdout}")
            self.logger.info(f"npm test stderr: {test_result.stderr}")
            if test_result.returncode != 0:
                self.logger.error(f"Existing tests failed: {test_result.stderr}")
                raise RuntimeError("Existing tests failed. Please fix the tests before proceeding.")

            output = self.strip_ansi_codes(test_result.stdout + test_result.stderr)
            self.logger.info(f"Full test output: {output}")

            tests_passed = None
            coverage = None

            self.logger.info("Parsing test output for metrics")
            passed_patterns = [
                r'Tests:\s*(\d+)\s+passed',
                r'(\d+)\s+passing',
                r'passed:\s*(\d+)',
                r'(\d+)\s+tests?\s+passed',
                r'successful:\s*(\d+)',
                r'(\d+)\s+passed',
                r'Tests:\s*\d+\s+failed,\s*(\d+)\s+passed',
            ]
            for pattern in passed_patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    tests_passed = int(match.group(1))
                    self.logger.info(f"Matched pattern '{pattern}' with {tests_passed} tests passed")
                    break

            if tests_passed is None:
                self.logger.info("No regex pattern matched; falling back to line-by-line scan")
                for line in output.splitlines():
                    match = re.search(r'(\d+)\s+passed|passing', line, re.IGNORECASE)
                    if match:
                        tests_passed = int(match.group(1))
                        self.logger.info(f"Fallback found {tests_passed} tests passed in line: {line}")
                        break

            if tests_passed is None:
                self.logger.warning("Could not find number of passing tests; defaulting to 0")
                tests_passed = 0

            self.logger.info("Parsing coverage from test output")
            coverage_match = re.search(
                r'All files\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)',
                output
            )
            if coverage_match:
                coverage = float(coverage_match.group(4))
                self.logger.info(f"Parsed coverage: {coverage}%")
            else:
                self.logger.warning("Could not parse coverage; defaulting to 0.0")
                coverage = 0.0

            state["existing_tests_passed"] = tests_passed
            state["existing_coverage_all_files"] = coverage
            self.logger.info(f"Updated state with tests passed: {tests_passed}, coverage: {coverage}%")
            self.logger.info("Pre-test runner process completed successfully")
            self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state

        except Exception as e:
            self.logger.error(f"Pre-Test Runner failed: {str(e)}")
            raise