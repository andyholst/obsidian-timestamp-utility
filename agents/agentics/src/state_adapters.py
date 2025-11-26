"""
State adapters for converting between legacy State dict and immutable CodeGenerationState.
Used to integrate existing agents with the new composable workflow architecture.
"""

from typing import Dict, Any, Optional
from langchain_core.runnables import Runnable
from .state import State, CodeGenerationState
from .models import CodeSpec, TestSpec, ValidationResults
from .monitoring import structured_log


class StateToCodeGenerationStateAdapter(Runnable[State, CodeGenerationState]):
    """Adapter to convert legacy State dict to CodeGenerationState."""

    def invoke(self, input: State, config=None) -> CodeGenerationState:
        # Extract values from State dict
        issue_url = input.get('url', '')
        ticket_content = input.get('ticket_content', '')
        refined_ticket = input.get('refined_ticket', {})

        # Build CodeGenerationState
        return CodeGenerationState(
            issue_url=issue_url,
            ticket_content=ticket_content,
            title=refined_ticket.get('title', ''),
            description=refined_ticket.get('description', ''),
            requirements=refined_ticket.get('requirements', []),
            acceptance_criteria=refined_ticket.get('acceptance_criteria', []),
            implementation_steps=refined_ticket.get('implementation_steps', []),
            npm_packages=refined_ticket.get('npm_packages', []),
            manual_implementation_notes=refined_ticket.get('manual_implementation_notes', ''),
            code_spec=CodeSpec(
                language="typescript",
                framework="obsidian",
                dependencies=[]
            ),
            test_spec=TestSpec(
                test_framework="jest",
                coverage_requirements=[]
            ),
            generated_code=input.get('generated_code'),
            generated_tests=input.get('generated_tests'),
            validation_results=None,
            result=input.get('result'),
            relevant_code_files=input.get('relevant_code_files', []),
            relevant_test_files=input.get('relevant_test_files', []),
            feedback=input.get('feedback'),
            method_name=input.get('method_name'),
            command_id=input.get('command_id'),
            existing_tests_passed=input.get('existing_tests_passed', 0)
        )


class CodeGenerationStateToStateAdapter(Runnable[CodeGenerationState, State]):
    """Adapter to convert CodeGenerationState back to legacy State dict."""

    def invoke(self, input: CodeGenerationState, config=None) -> State:
        # Convert back to State dict
        state: State = {
            'url': input.issue_url,
            'ticket_content': input.ticket_content,
            'refined_ticket': {
                'title': input.title,
                'description': input.description,
                'requirements': input.requirements,
                'acceptance_criteria': input.acceptance_criteria,
                'implementation_steps': input.implementation_steps,
                'npm_packages': input.npm_packages,
                'manual_implementation_notes': input.manual_implementation_notes
            },
            'generated_code': input.generated_code,
            'generated_tests': input.generated_tests,
            'result': input.result,
            'relevant_code_files': input.relevant_code_files,
            'relevant_test_files': input.relevant_test_files,
            'feedback': input.feedback,
            'method_name': input.method_name,
            'existing_tests_passed': input.existing_tests_passed,
            'command_id': input.command_id
        }

        # Add validation results if present
        if input.validation_results:
            state['validation_results'] = {
                'success': input.validation_results.success,
                'score': input.validation_results.score,
                'errors': input.validation_results.errors,
                'warnings': input.validation_results.warnings
            }
            state['validation_score'] = input.validation_results.score

        return state


class AgentAdapter(Runnable[CodeGenerationState, CodeGenerationState]):
    """Adapter to make legacy agents work with CodeGenerationState."""

    def __init__(self, legacy_agent: Runnable[State, State]):
        self.legacy_agent = legacy_agent
        self.to_legacy = CodeGenerationStateToStateAdapter()
        self.from_legacy = StateToCodeGenerationStateAdapter()

    def invoke(self, input: CodeGenerationState, config=None) -> CodeGenerationState:
        # Convert to legacy State
        legacy_state = self.to_legacy.invoke(input)

        # Process with legacy agent
        processed_state = self.legacy_agent.invoke(legacy_state)

        # Convert back to CodeGenerationState
        return self.from_legacy.invoke(processed_state)


class InitialStateAdapter(Runnable[Dict[str, Any], CodeGenerationState]):
    """Adapter to convert initial dict state to CodeGenerationState."""

    def __init__(self):
        self.monitor = structured_log("initial_state_adapter")

    def invoke(self, input: Dict[str, Any], config=None) -> CodeGenerationState:
        if not isinstance(input, dict):
            self.monitor.error("InitialStateAdapter received non-dict input", {"input_type": type(input)})
            raise TypeError(f"Expected dict, got {type(input)}")
        return CodeGenerationState(
            issue_url=input.get('url', ''),
            ticket_content='',
            title='',
            description='',
            requirements=[],
            acceptance_criteria=[],
            implementation_steps=[],
            npm_packages=[],
            manual_implementation_notes='',
            code_spec=CodeSpec(
                language="typescript",
                framework="obsidian",
                dependencies=[]
            ),
            test_spec=TestSpec(
                test_framework="jest",
                coverage_requirements=[]
            ),
            generated_code=None,
            generated_tests=None,
            validation_results=None,
            result=None,
            relevant_code_files=[],
            relevant_test_files=[],
            feedback=None,
            method_name=None,
            command_id=None
        )


class FinalStateAdapter(Runnable[CodeGenerationState, Dict[str, Any]]):
    """Adapter to convert final CodeGenerationState back to dict for external interface."""

    def invoke(self, input: CodeGenerationState, config=None) -> Dict[str, Any]:
        result = {
            'url': input.issue_url,
            'ticket_content': input.ticket_content,
            'refined_ticket': {
                'title': input.title,
                'description': input.description,
                'requirements': input.requirements,
                'acceptance_criteria': input.acceptance_criteria,
                'implementation_steps': input.implementation_steps,
                'npm_packages': input.npm_packages,
                'manual_implementation_notes': input.manual_implementation_notes
            },
            'generated_code': input.generated_code,
            'generated_tests': input.generated_tests,
            'result': input.result,
            'relevant_code_files': input.relevant_code_files,
            'relevant_test_files': input.relevant_test_files,
            'feedback': input.feedback,
            'existing_tests_passed': input.existing_tests_passed,
            'method_name': input.method_name,
            'command_id': input.command_id
        }

        if input.validation_results:
            result['validation_results'] = {
                'success': input.validation_results.success,
                'errors': input.validation_results.errors,
                'warnings': input.validation_results.warnings
            }

        return result