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
            state['build_errors'] = errors

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
        """Parse npm build and test output for TypeScript compilation errors, rollup errors, and Jest test failures."""
        errors = []

        # TS/tsc
        ts_pattern = r'^(.*?):(\d+):(\d+) - (error TS\d+: .*?)(?=\n(?:\s*[a-zA-Z]|$))'
        # Rollup
        rollup_pattern = r'[!>]\\s*(src[/\\\\](.*?)\\.ts):(\\d+):(\\d+)\\s*(error TS\\d+:\\s*(.*?))'
        # Jest FAIL
        jest_fail_pattern = r'FAIL\\s+(.+?)\\n(.*?)(?=\\n\\nFAIL|\\n\\nTest Suites|\\Z)'

        for pat, typ in [(ts_pattern, 'ts'), (rollup_pattern, 'rollup'), (jest_fail_pattern, 'jest')]:
            for match in re.finditer(pat, output, re.MULTILINE | re.DOTALL):
                if typ == 'ts':
                    f, l, c, m = match.groups()
                    errors.append({'type': typ, 'file': f, 'line': int(l), 'col': int(c), 'msg': m.strip()})
                elif typ == 'rollup':
                    f, _, l, c, _, m = match.groups()
                    errors.append({'type': typ, 'file': f, 'line': int(l), 'col': int(c), 'msg': m.strip()})
                elif typ == 'jest':
                    f, m = match.groups()
                    errors.append({'type': typ, 'file': f, 'msg': m.strip()})

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
        prompt = ModularPrompts.get_ts_build_fix_prompt().format(
            errors=errors,
            generated_code=state.get('generated_code', ''),
            generated_tests=state.get('generated_tests', '')
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
