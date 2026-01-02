"""
Tool-Integrated Code Generator Agent

This agent validates Obsidian API calls and dependencies before generating code,
implementing error recovery for API hallucinations and invalid imports.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from .tool_integrated_agent import ToolIntegratedAgent
from .api_validation_tools import APIValidationTools
from .state import State
from .monitoring import structured_log


class ToolIntegratedCodeGeneratorAgent(ToolIntegratedAgent):
    """
    Code generator agent with integrated API and dependency validation.

    Validates Obsidian API calls and npm dependencies before code generation
    to prevent hallucinations and invalid imports.
    """

    def __init__(self, llm: Runnable, name: str = "ToolIntegratedCodeGenerator"):
        # Initialize validation tools
        validation_tools = APIValidationTools()
        tools = [
            validation_tools.validate_obsidian_api,
            validation_tools.validate_npm_package
        ]

        super().__init__(llm, tools, name)
        self.logger = structured_log("tool_integrated_code_generator")

    def process_with_tools(self, state: State) -> State:
        """Process state with validation before code generation."""

        # Extract code requirements from state
        requirements = self._extract_requirements(state)

        # Validate APIs and dependencies before generation
        validation_results = self._validate_requirements(requirements)

        # Update state with validation results
        state = self._update_state_with_validation(state, validation_results)

        # Only proceed with generation if validation passes or we have suggestions
        if self._should_generate_code(validation_results):
            return super().process_with_tools(state)
        else:
            # Return state with validation errors for error recovery
            state['validation_errors'] = validation_results.get('errors', [])
            state['validation_suggestions'] = validation_results.get('suggestions', [])
            return state

    def _extract_requirements(self, state: State) -> Dict[str, Any]:
        """Extract API calls and dependencies from state."""
        requirements = {
            'api_calls': [],
            'npm_packages': []
        }

        # Extract from ticket content or refined ticket
        ticket_data = state.get('refined_ticket', state.get('ticket_content', {}))

        if isinstance(ticket_data, dict):
            # Extract npm packages
            npm_packages = ticket_data.get('npm_packages', [])
            if npm_packages:
                requirements['npm_packages'] = [pkg.get('name') for pkg in npm_packages if isinstance(pkg, dict)]

            # Extract potential API calls from requirements
            ticket_requirements = ticket_data.get('requirements', [])
            for req in ticket_requirements:
                if isinstance(req, str) and 'app.' in req:
                    # Extract API calls mentioned in requirements
                    requirements['api_calls'].extend(self._extract_api_calls_from_text(req))

        return requirements

    def _extract_api_calls_from_text(self, text: str) -> List[str]:
        """Extract potential API calls from text."""
        # Simple extraction - look for patterns like app.something.method
        import re
        api_pattern = r'app\.\w+\.\w+'
        matches = re.findall(api_pattern, text)
        return list(set(matches))  # Remove duplicates

    def _validate_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Validate APIs and packages using tools."""
        results = {
            'api_validation': [],
            'package_validation': [],
            'errors': [],
            'suggestions': []
        }

        # Validate API calls
        for api_call in requirements.get('api_calls', []):
            try:
                validation_result = self.tool_executor.execute_tool(
                    'validate_obsidian_api',
                    {'api_call': api_call}
                )
                results['api_validation'].append({
                    'api_call': api_call,
                    'result': validation_result
                })

                # Parse result and collect errors/suggestions
                if isinstance(validation_result, dict):
                    if not validation_result.get('is_valid', False):
                        results['errors'].extend(validation_result.get('errors', []))
                        results['suggestions'].extend(validation_result.get('suggestions', []))

            except Exception as e:
                self.logger.error("api_validation_failed", {"api_call": api_call, "error": str(e)})
                results['errors'].append(f"Failed to validate API call {api_call}: {str(e)}")

        # Validate npm packages
        for package in requirements.get('npm_packages', []):
            try:
                validation_result = self.tool_executor.execute_tool(
                    'validate_npm_package',
                    {'package_name': package}
                )
                results['package_validation'].append({
                    'package': package,
                    'result': validation_result
                })

                # Parse result and collect errors/suggestions
                if isinstance(validation_result, dict):
                    if not validation_result.get('is_valid', False):
                        results['errors'].extend(validation_result.get('errors', []))
                        results['suggestions'].extend(validation_result.get('suggestions', []))

            except Exception as e:
                self.logger.error("package_validation_failed", {"package": package, "error": str(e)})
                results['errors'].append(f"Failed to validate package {package}: {str(e)}")

        return results

    def _update_state_with_validation(self, state: State, validation_results: Dict[str, Any]) -> State:
        """Update state with validation results."""
        state['api_validation_results'] = validation_results.get('api_validation', [])
        state['package_validation_results'] = validation_results.get('package_validation', [])
        state['validation_errors'] = validation_results.get('errors', [])
        state['validation_suggestions'] = validation_results.get('suggestions', [])
        return state

    def _should_generate_code(self, validation_results: Dict[str, Any]) -> bool:
        """Determine if code generation should proceed."""
        errors = validation_results.get('errors', [])
        suggestions = validation_results.get('suggestions', [])

        # Proceed if no critical errors or if we have suggestions to fix them
        return len(errors) == 0 or len(suggestions) > 0

    def _create_tool_augmented_prompt(self, state: State, tool_context: Dict[str, Any]) -> str:
        """Create prompt with validation context."""
        base_prompt = super()._create_tool_augmented_prompt(state, tool_context)

        # Add validation-specific instructions
        validation_instructions = """

VALIDATION REQUIREMENTS:
- Use the validate_obsidian_api tool to check API calls before using them in code
- Use the validate_npm_package tool to verify npm packages before importing them
- If validation fails, use the suggestions provided to fix the code
- Generate code that only uses validated APIs and packages
- If no valid alternatives exist, suggest manual implementation approaches

"""

        return base_prompt + validation_instructions