import logging
from typing import Dict, Any, Optional
from datetime import datetime
from langchain_core.runnables import Runnable, RunnableConfig
from .base_agent import BaseAgent
from .state import CodeGenerationState
from .code_generator_agent import CodeGeneratorAgent
from .test_generator_agent import TestGeneratorAgent
from .utils import log_info
from .circuit_breaker import get_circuit_breaker
from .monitoring import structured_log


class CollaborativeGenerator(Runnable[CodeGenerationState, CodeGenerationState]):
    """
    Collaborative code and test generation system that coordinates between
    code and test generators with cross-validation and iterative refinement.
    """

    def __init__(self, llm):
        self.name = "CollaborativeGenerator"
        self.llm = llm
        self.llm_reasoning = llm  # Use single LLM for both
        self.llm_code = llm
        self.code_generator = CodeGeneratorAgent(self.llm_code)
        self.test_generator = TestGeneratorAgent(self.llm_code)
        self.circuit_breaker = get_circuit_breaker("collaborative_generation")
        self.max_refinement_iterations = 3
        self.monitor = structured_log(self.name)
        self.monitor.setLevel(logging.INFO)
        log_info(self.name, "Initialized CollaborativeGenerator with service manager")

    def _log_structured(self, level: str, event: str, data: Dict[str, Any]):
        """Structured logging for workflow component."""
        log_method = getattr(self.monitor, level.lower(), self.monitor.info)
        log_method(event, data)

    def invoke(self, input, config: Optional[RunnableConfig] = None) -> CodeGenerationState:
        if isinstance(input, dict):
            input = CodeGenerationState(**input)
        return self.generate_collaboratively(input)

    def generate_collaboratively(self, state: CodeGenerationState) -> CodeGenerationState:
        """Generate code and tests collaboratively with iterative refinement"""

        def _generate_impl():
            current_state = state
            validation_history = []

            for iteration in range(self.max_refinement_iterations):
                log_info(self.name, f"Iterative refinement iteration {iteration + 1}/{self.max_refinement_iterations}")

                # Phase 1: Generate initial code
                code_state = self.code_generator.generate(current_state)

                # Phase 2: Generate tests based on code
                test_state = self.test_generator.generate(code_state)

                # Combine states
                combined_state = self._combine_states(code_state, test_state)

                # Phase 3: Cross-validation
                validated_state = self.cross_validate(combined_state)

                # Accumulate validation history
                validation_result = validated_state.validation_results
                if validation_result:
                    validation_history.append({
                        'iteration': iteration + 1,
                        'passed': validation_result.success,
                        'score': validation_result.score,
                        'issues': validation_result.errors,
                        'timestamp': datetime.now().isoformat()
                    })

                validated_state = validated_state.with_validation_history(validation_history)

                # Check if validation passed
                if validation_result and validation_result.success:
                    self._log_structured("info", "validation_passed", {
                        "iteration": iteration + 1,
                        "score": validation_result.score
                    })
                    validated_state = validated_state.with_feedback({
                        'iteration_count': iteration + 1,
                        'validation_history': validation_history
                    })
                    return validated_state

                # If not passed, refine for next iteration
                current_state = self._refine_code_and_tests(validated_state, {
                    'passed': validation_result.success if validation_result else False,
                    'score': validation_result.score if validation_result else 0,
                    'issues': validation_result.errors if validation_result else []
                })

            # If max iterations reached, return last state
            self._log_structured("warning", "max_iterations_reached", {
                "final_iteration": self.max_refinement_iterations
            })
            current_state = current_state.with_feedback({
                'iteration_count': self.max_refinement_iterations,
                'validation_history': validation_history,
                'max_iterations_exceeded': True
            })
            return current_state

        try:
            return self.circuit_breaker.call(_generate_impl)
        except Exception as e:
            self.monitor.error("generate_collaboratively_failed", {"error": str(e)})
            raise

    def _generate_initial_code(self, state: CodeGenerationState) -> CodeGenerationState:
        """Generate initial code using the code generator agent."""
        log_info(self.name, "Phase 1: Generating initial code")
        try:
            code_state = self.code_generator.generate(state)
            self._log_structured("info", "initial_code_generated", {
                "code_length": len(code_state.generated_code),
                "method_name": code_state.method_name,
                "command_id": code_state.command_id
            })
            return code_state
        except Exception as e:
            self._log_structured("error", "initial_code_generation_failed", {"error": str(e)})
            raise

    def _generate_initial_tests(self, state: CodeGenerationState) -> CodeGenerationState:
        """Generate initial tests based on the generated code."""
        log_info(self.name, "Phase 2: Generating initial tests")
        try:
            test_state = self.test_generator.generate(state)
            self._log_structured("info", "initial_tests_generated", {
                "test_length": len(test_state.generated_tests)
            })
            return test_state
        except Exception as e:
            self._log_structured("error", "initial_test_generation_failed", {"error": str(e)})
            raise

    def _cross_validate_and_refine(self, state: CodeGenerationState) -> CodeGenerationState:
        """
        Perform cross-validation between code and tests, with iterative refinement.
        """
        log_info(self.name, "Phase 3: Cross-validation and refinement")

        current_state = state
        refinement_iteration = 0

        while refinement_iteration < self.max_refinement_iterations:
            log_info(self.name, f"Refinement iteration {refinement_iteration + 1}/{self.max_refinement_iterations}")

            # Perform cross-validation
            validation_result = self._cross_validate(current_state)

            if validation_result['passed']:
                self._log_structured("info", "cross_validation_passed", {
                    "iteration": refinement_iteration + 1,
                    "score": validation_result.get('score', 0)
                })
                return current_state.with_validation(validation_result)

            # If validation failed, perform refinement
            self._log_structured("warning", "cross_validation_failed", {
                "iteration": refinement_iteration + 1,
                "issues": validation_result.get('issues', [])
            })

            current_state = self._refine_code_and_tests(current_state, validation_result)
            refinement_iteration += 1

        # If we exhausted iterations, return the best we have
        self._log_structured("warning", "max_refinement_iterations_reached", {
            "final_iteration": refinement_iteration
        })
        return current_state.with_validation({"passed": False, "max_iterations_exceeded": True})

    def _cross_validate(self, state: CodeGenerationState) -> Dict[str, Any]:
        """
        Cross-validate code and tests to ensure they work together properly.

        Returns:
            Validation result with pass/fail status and feedback
        """
        log_info(self.name, "Performing cross-validation")

        try:
            # Basic validation checks
            issues = []

            # Check if code has methods that should be tested
            code_methods = self._extract_methods_from_code(state.generated_code)
            test_methods = self._extract_tested_methods_from_tests(state.generated_tests)

            # Check coverage - are all code methods tested?
            untested_methods = set(code_methods) - set(test_methods)
            if untested_methods:
                issues.append(f"Untested methods: {list(untested_methods)}")

            # Check if tests reference the correct method/command names
            if state.method_name and state.method_name not in state.generated_tests:
                issues.append(f"Tests do not reference method '{state.method_name}'")

            if state.command_id and state.command_id not in state.generated_tests:
                issues.append(f"Tests do not reference command ID '{state.command_id}'")

            # Check test structure
            if 'describe(' not in state.generated_tests:
                issues.append("Tests missing describe blocks")

            if 'it(' not in state.generated_tests and 'test(' not in state.generated_tests:
                issues.append("Tests missing test cases")

            # Calculate a simple score
            score = max(0, 100 - (len(issues) * 20))

            passed = len(issues) == 0

            result = {
                "passed": passed,
                "score": score,
                "issues": issues,
                "code_methods": code_methods,
                "test_methods": test_methods
            }

            self._log_structured("info", "cross_validation_result", {
                "passed": passed,
                "score": score,
                "issues_count": len(issues)
            })

            return result

        except Exception as e:
            self._log_structured("error", "cross_validation_error", {"error": str(e)})
            return {
                "passed": False,
                "score": 0,
                "issues": [f"Validation error: {str(e)}"]
            }

    def _refine_code_and_tests(self, state: CodeGenerationState, validation_result: Dict[str, Any]) -> CodeGenerationState:
        """
        Refine code and/or tests based on validation feedback.
        """
        log_info(self.name, "Performing refinement based on validation feedback")

        issues = validation_result.get('issues', [])

        # Create refinement feedback
        refinement_feedback = self._create_refinement_feedback(issues)

        try:
            # Try to refine tests first (usually easier)
            if any("test" in issue.lower() for issue in issues):
                refined_state = self.test_generator.refine_tests(state, refinement_feedback)
                # Re-validate using LLM-based cross_validate
                re_validated_state = self.cross_validate(refined_state)
                re_validation = re_validated_state.validation_results
                if re_validation and re_validation.success:
                    return re_validated_state
                # If still failing, continue to code refinement

            # If test refinement didn't work or code issues exist, we would refine code
            # For now, just update the validation status
            return state.with_validation(validation_result).with_feedback({"refinement_attempted": True, "issues": issues})

        except Exception as e:
            self._log_structured("error", "refinement_error", {"error": str(e)})
            return state.with_validation(validation_result).with_feedback({"refinement_failed": str(e)})

    def _extract_methods_from_code(self, code: str) -> list:
        """Extract method names from generated code."""
        import re
        method_pattern = r'(?:public|private|protected)?\s*(?:async)?\s*(\w+)\s*\('
        matches = re.findall(method_pattern, code)
        return [m for m in matches if m not in ['if', 'for', 'while', 'constructor']]

    def _extract_tested_methods_from_tests(self, tests: str) -> list:
        """Extract method names that are being tested."""
        import re
        # Look for method calls in test expectations
        method_pattern = r'\.(\w+)\(\)'
        matches = re.findall(method_pattern, tests)
        return list(set(matches))

    def _create_refinement_feedback(self, issues: list) -> str:
        """Create feedback string for refinement."""
        feedback_parts = []
        for issue in issues:
            if "untested methods" in issue.lower():
                feedback_parts.append("Add test cases for all public methods in the generated code.")
            elif "describe" in issue.lower():
                feedback_parts.append("Structure tests with proper describe blocks.")
            elif "test cases" in issue.lower():
                feedback_parts.append("Add specific test cases (it/test blocks) for the functionality.")
            elif "method" in issue.lower() and "not reference" in issue.lower():
                feedback_parts.append("Ensure tests properly reference the generated method and command ID.")
            else:
                feedback_parts.append(f"Fix: {issue}")

        return " ".join(feedback_parts)
        return " ".join(feedback_parts)

    def cross_validate(self, state: CodeGenerationState) -> CodeGenerationState:
        """
        Cross-validate code and tests to ensure they work together properly.

        Args:
            state: State containing generated code and tests

        Returns:
            Validated state with validation results and accumulated history
        """
        log_info(self.name, f"Performing cross-validation on code and tests - received {len([state]) if isinstance(state, CodeGenerationState) else 'multiple'} state(s)")
        # Debug log to validate arguments
        self._log_structured("info", "cross_validate_args", {
            "args_count": 1 if isinstance(state, CodeGenerationState) else "unexpected",
            "has_generated_code": hasattr(state, 'generated_code'),
            "has_generated_tests": hasattr(state, 'generated_tests')
        })

        try:
            # Create validation prompt
            validation_prompt = self._create_validation_prompt(state)

            # Use LLM reasoning for analysis
            llm_response = self.llm_reasoning.invoke(validation_prompt)

            # Parse validation results
            validation_result = self._parse_validation_response(llm_response)

            # Add validation to state
            validated_state = state.with_validation(validation_result)

            # Accumulate validation history
            current_history = state.validation_history or []
            new_entry = {
                'timestamp': datetime.now().isoformat(),
                'passed': validation_result.get('passed', False),
                'score': validation_result.get('score', 0),
                'issues': validation_result.get('issues', []),
                'recommendations': validation_result.get('recommendations', [])
            }
            updated_history = current_history + [new_entry]
            validated_state = validated_state.with_validation_history(updated_history)

            # Check if refinements are needed
            if not validation_result.get('passed', False):
                log_info(self.name, "Validation failed, attempting refinements")
                validated_state = self._attempt_refinements(validated_state, validation_result)

            self._log_structured("info", "cross_validation_completed", {
                "passed": validation_result.get('passed', False),
                "score": validation_result.get('score', 0),
                "issues_count": len(validation_result.get('issues', []))
            })

            return validated_state

        except Exception as e:
            self._log_structured("error", "cross_validation_failed", {"error": str(e)})
            # Return state with error validation
            error_result = {
                "passed": False,
                "score": 0,
                "issues": [f"Cross-validation error: {str(e)}"]
            }
            error_state = state.with_validation(error_result)
            current_history = state.validation_history or []
            error_entry = {
                'timestamp': datetime.now().isoformat(),
                'passed': False,
                'score': 0,
                'issues': [f"Cross-validation error: {str(e)}"],
                'recommendations': []
            }
            updated_history = current_history + [error_entry]
            return error_state.with_validation_history(updated_history)

    def _create_validation_prompt(self, state: CodeGenerationState) -> str:
        """Create prompt for LLM to validate code-test alignment."""
        return f"""
You are an expert software engineer validating the alignment between generated code and its corresponding tests.

Analyze the following generated TypeScript code and Jest tests to determine:
1. Test coverage - do the tests cover all important functionality in the code?
2. Code-test alignment - do the tests properly test the implemented features?
3. Test quality - are the tests well-structured and comprehensive?
4. Potential issues - any gaps or misalignments?

Generated Code:
{state.generated_code}

Generated Tests:
{state.generated_tests}

Additional Context:
- Method Name: {state.method_name or 'N/A'}
- Command ID: {state.command_id or 'N/A'}
- Requirements: {', '.join(state.requirements)}

Please respond with a JSON object containing:
{{
  "passed": boolean (true if validation passes, false otherwise),
  "score": number (0-100, overall quality score),
  "coverage_percentage": number (0-100, estimated test coverage),
  "alignment_score": number (0-100, how well tests align with code),
  "issues": array of strings (specific problems found),
  "recommendations": array of strings (suggestions for improvement),
  "test_quality": string ("excellent"|"good"|"fair"|"poor")
}}

Be thorough but practical. Focus on functional correctness and test adequacy rather than style issues.
"""

    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM validation response."""
        try:
            import json
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                return parsed
            else:
                # Fallback if no JSON found
                return {
                    "passed": False,
                    "score": 30,
                    "coverage_percentage": 50,
                    "alignment_score": 40,
                    "issues": ["Failed to parse validation response as JSON"],
                    "recommendations": ["Retry validation"],
                    "test_quality": "unknown"
                }
        except Exception as e:
            return {
                "passed": False,
                "score": 20,
                "coverage_percentage": 0,
                "alignment_score": 0,
                "issues": [f"Validation parsing error: {str(e)}"],
                "recommendations": ["Check LLM response format"],
                "test_quality": "unknown"
            }

    def _combine_states(self, code_state: CodeGenerationState, test_state: CodeGenerationState) -> CodeGenerationState:
        """Combine code and test states."""
        # Create new state with code from code_state, tests from test_state
        combined_state = CodeGenerationState(
            issue_url=code_state.issue_url,
            ticket_content=code_state.ticket_content,
            title=code_state.title,
            description=code_state.description,
            requirements=code_state.requirements,
            acceptance_criteria=code_state.acceptance_criteria,
            implementation_steps=code_state.implementation_steps,
            npm_packages=code_state.npm_packages,
            manual_implementation_notes=code_state.manual_implementation_notes,
            code_spec=code_state.code_spec,
            test_spec=test_state.test_spec,  # Use test spec from test_state
            generated_code=code_state.generated_code,
            generated_tests=test_state.generated_tests,
            validation_results=None,
            result=code_state.result,
            relevant_code_files=code_state.relevant_code_files,
            relevant_test_files=test_state.relevant_test_files,  # Use test files from test_state
            feedback=code_state.feedback,
            method_name=code_state.method_name,
            command_id=code_state.command_id,
            validation_history=code_state.validation_history  # Preserve history
        )
        return combined_state

    def _combine_states_with_validation(self, code_state: CodeGenerationState, test_state: CodeGenerationState, validation_result: Dict[str, Any]) -> CodeGenerationState:
        """Combine code and test states with validation results."""
        # Create new state with code from code_state, tests from test_state
        combined_state = CodeGenerationState(
            issue_url=code_state.issue_url,
            ticket_content=code_state.ticket_content,
            title=code_state.title,
            description=code_state.description,
            requirements=code_state.requirements,
            acceptance_criteria=code_state.acceptance_criteria,
            implementation_steps=code_state.implementation_steps,
            npm_packages=code_state.npm_packages,
            manual_implementation_notes=code_state.manual_implementation_notes,
            code_spec=code_state.code_spec,
            test_spec=test_state.test_spec,  # Use test spec from test_state
            generated_code=code_state.generated_code,
            generated_tests=test_state.generated_tests,
            validation_results=None,  # Will be set below
            result=code_state.result,
            relevant_code_files=code_state.relevant_code_files,
            relevant_test_files=test_state.relevant_test_files,  # Use test files from test_state
            feedback=code_state.feedback,
            method_name=code_state.method_name,
            command_id=code_state.command_id,
            validation_history=code_state.validation_history  # Preserve history
        )

        # Add validation results
        return combined_state.with_validation(validation_result)

    def _attempt_refinements(self, state: CodeGenerationState, validation_result: Dict[str, Any]) -> CodeGenerationState:
        """Attempt to refine code or tests based on validation feedback."""
        issues = validation_result.get('issues', [])
        recommendations = validation_result.get('recommendations', [])

        refinement_feedback = " ".join(issues + recommendations)

        try:
            # Try refining tests first (usually easier)
            log_info(self.name, "Attempting test refinement")
            refined_state = self.test_generator.refine_tests(state, refinement_feedback)
            # Re-validate using LLM-based cross_validate
            re_validated_state = self.cross_validate(refined_state)
            re_validation = re_validated_state.validation_results
            if re_validation and re_validation.success:
                return re_validated_state

            # If test refinement didn't work or code issues exist, try code refinement
            if any(keyword in refinement_feedback.lower() for keyword in ['code', 'method', 'function', 'implementation']):
                log_info(self.name, "Attempting code refinement")
                # For code refinement, we might need to regenerate code based on feedback
                # This is more complex, so for now just mark as attempted
                pass

            # Return state with refinement attempt noted
            return state.with_feedback({"refinement_attempted": True, "issues": issues, "recommendations": recommendations})

        except Exception as e:
            self._log_structured("error", "refinement_error", {"error": str(e)})
            return state.with_feedback({"refinement_failed": str(e)})
