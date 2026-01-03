import logging
import re
from typing import Dict, Any, Optional
from langchain_core.runnables import Runnable
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import execute_command_tool
from .utils import log_info
from .prompts import ModularPrompts


class NpmBuildTestAgent(ToolIntegratedAgent):
    def __init__(self, llm_client: Runnable):
        super().__init__(llm_client, [execute_command_tool], "NpmBuildTestAgent")
        self.monitor.info("NpmBuildTestAgent initialized")

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run npm build and test commands, parse errors, propose fixes if needed."""
        log_info(self.name, "Starting npm build and test execution")

        # Run the npm commands
        command = "cd ../../../.. && npm ci && npm run build-package && npm test"
        try:
            result = execute_command_tool.invoke({"command": command})
            log_info(self.name, f"NPM command output: {result}")

            # Parse the output for errors
            errors = self._parse_errors(result)

            if errors:
                log_info(self.name, f"Found {len(errors)} errors, proposing fixes")
                # Propose fixes using LLM
                fixes = self._propose_fixes(state, errors)
                # Update state with fixes
                state = self._apply_fixes(state, fixes)
                # Add error summary for error_recovery_agent
                state['error_summary'] = {
                    'npm_errors': errors,
                    'proposed_fixes': fixes,
                    'build_output': result
                }
            else:
                log_info(self.name, "No errors found, proceeding")
                state['error_summary'] = None

        except Exception as e:
            log_info(self.name, f"Error running npm commands: {str(e)}")
            state['error_summary'] = {
                'npm_errors': [{'type': 'execution_error', 'message': str(e)}],
                'proposed_fixes': [],
                'build_output': str(e)
            }

        return state

    def _parse_errors(self, output: str) -> list:
        """Parse npm build and test output for TypeScript compilation errors and Jest test failures."""
        errors = []

        # Parse TypeScript compilation errors (from build-package, likely tsc)
        # Look for lines like: src/main.ts(10,5): error TS1234: Some error
        ts_error_pattern = r'(\w+\.ts)\((\d+),(\d+)\):\s*error\s*(\w+):\s*(.+)'
        for match in re.finditer(ts_error_pattern, output, re.MULTILINE):
            file, line, col, code, message = match.groups()
            errors.append({
                'type': 'typescript',
                'file': file,
                'line': int(line),
                'column': int(col),
                'code': code,
                'message': message.strip()
            })

        # Parse Jest test failures
        # Look for "FAIL" sections
        fail_pattern = r'FAIL\s+(.+)\n(.+?)(?=\n\nPASS|\n\nFAIL|\n\nTest Suites|\Z)'
        for match in re.finditer(fail_pattern, output, re.DOTALL):
            test_file = match.group(1).strip()
            failure_details = match.group(2).strip()
            errors.append({
                'type': 'jest',
                'file': test_file,
                'details': failure_details
            })

        # Also check for general npm errors
        if 'npm ERR!' in output:
            errors.append({
                'type': 'npm',
                'message': 'NPM command failed',
                'output': output
            })

        return errors

    def _propose_fixes(self, state: Dict[str, Any], errors: list) -> Dict[str, Any]:
        """Use LLM to propose fixes for the errors."""
        prompt = ModularPrompts.get_npm_build_test_fix_prompt().format(
            generated_code=state.get('generated_code', ''),
            generated_tests=state.get('generated_tests', ''),
            errors=errors
        )
        try:
            response = self.llm.invoke(prompt)
            # Parse JSON response
            import json
            clean_response = response.content if hasattr(response, 'content') else str(response)
            fixes = json.loads(clean_response.strip())
            return fixes
        except Exception as e:
            log_info(self.name, f"Error proposing fixes: {str(e)}")
            return {
                "code_fixes": state.get('generated_code', ''),
                "test_fixes": state.get('generated_tests', ''),
                "explanation": "Failed to generate fixes"
            }

    def _apply_fixes(self, state: Dict[str, Any], fixes: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the proposed fixes to the state."""
        if 'code_fixes' in fixes:
            state['generated_code'] = fixes['code_fixes']
        if 'test_fixes' in fixes:
            state['generated_tests'] = fixes['test_fixes']
        return state
