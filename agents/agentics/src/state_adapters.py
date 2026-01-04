"""
State adapters for converting between legacy State dict and immutable CodeGenerationState.
Used to integrate existing agents with the new composable workflow architecture.
"""

from typing import Dict, Any, Optional
from dataclasses import asdict
from langchain_core.runnables import Runnable
from .state import State, CodeGenerationState
from .models import CodeSpec, TestSpec, ValidationResults
from .monitoring import structured_log


class StateToCodeGenerationStateAdapter(Runnable[State, CodeGenerationState]):
    """Adapter to convert legacy State dict to CodeGenerationState."""

    def invoke(self, input: State, config=None) -> CodeGenerationState:
        if isinstance(input, CodeGenerationState):
            return input
        # Extract values from State dict
        issue_url = input.get('issue_url') or input.get('url', '')
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
            existing_tests_passed=input.get('existing_tests_passed', 0),
            test_errors=input.get('test_errors', []),
            test_log_path=input.get('test_log_path'),
            recovery_confidence=input.get('recovery_confidence', 100.0),
            recovery_explanation=input.get('recovery_explanation')
        )


class CodeGenerationStateToStateAdapter(Runnable[CodeGenerationState, State]):
    """Adapter to convert CodeGenerationState back to legacy State dict."""

    def _safe_getattr(self, obj: Any, attr: str, default: Any = None) -> Any:
        return getattr(obj, attr, default)

    def invoke(self, input: CodeGenerationState, config=None) -> State:
        # Convert back to State dict
        state: State = {
            'url': self._safe_getattr(input, 'issue_url', ''),
            'ticket_content': self._safe_getattr(input, 'ticket_content', ''),
            'refined_ticket': {
                'title': self._safe_getattr(input, 'title', ''),
                'description': self._safe_getattr(input, 'description', ''),
                'requirements': self._safe_getattr(input, 'requirements', []),
                'acceptance_criteria': self._safe_getattr(input, 'acceptance_criteria', []),
                'implementation_steps': self._safe_getattr(input, 'implementation_steps', []),
                'npm_packages': self._safe_getattr(input, 'npm_packages', []),
                'manual_implementation_notes': self._safe_getattr(input, 'manual_implementation_notes', '')
            },
            'generated_code': self._safe_getattr(input, 'generated_code'),
            'generated_tests': self._safe_getattr(input, 'generated_tests'),
            'result': self._safe_getattr(input, 'result'),
            'relevant_code_files': self._safe_getattr(input, 'relevant_code_files', []),
            'relevant_test_files': self._safe_getattr(input, 'relevant_test_files', []),
            'feedback': self._safe_getattr(input, 'feedback'),
            'method_name': self._safe_getattr(input, 'method_name'),
            'existing_tests_passed': self._safe_getattr(input, 'existing_tests_passed', 0),
            'command_id': self._safe_getattr(input, 'command_id'),
            'test_errors': self._safe_getattr(input, 'test_errors', []),
            'test_log_path': self._safe_getattr(input, 'test_log_path'),
            'recovery_attempt': self._safe_getattr(input, 'recovery_attempt', 0),
            'recovery_confidence': self._safe_getattr(input, 'recovery_confidence', 100.0),
            'recovery_explanation': self._safe_getattr(input, 'recovery_explanation')
        }

        # Add validation results if present
        vr = self._safe_getattr(input, 'validation_results')
        if vr:
            state['validation_results'] = {
                'success': self._safe_getattr(vr, 'success', False),
                'score': self._safe_getattr(vr, 'score', 0),
                'errors': self._safe_getattr(vr, 'errors', []),
                'warnings': self._safe_getattr(vr, 'warnings', [])
            }
            state['validation_score'] = self._safe_getattr(vr, 'score', 0)

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
        if isinstance(input, CodeGenerationState):
            return input
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

    def _safe_getattr(self, obj: Any, attr: str, default: Any = None) -> Any:
        return getattr(obj, attr, default)

    def invoke(self, input: CodeGenerationState, config=None) -> Dict[str, Any]:
        result = {
            'url': self._safe_getattr(input, 'issue_url', ''),
            'ticket_content': self._safe_getattr(input, 'ticket_content', ''),
            'refined_ticket': {
                'title': self._safe_getattr(input, 'title', ''),
                'description': self._safe_getattr(input, 'description', ''),
                'requirements': self._safe_getattr(input, 'requirements', []),
                'acceptance_criteria': self._safe_getattr(input, 'acceptance_criteria', []),
                'implementation_steps': self._safe_getattr(input, 'implementation_steps', []),
                'npm_packages': self._safe_getattr(input, 'npm_packages', []),
                'manual_implementation_notes': self._safe_getattr(input, 'manual_implementation_notes', '')
            },
            'generated_code': self._safe_getattr(input, 'generated_code'),
            'generated_tests': self._safe_getattr(input, 'generated_tests', None),
            'result': self._safe_getattr(input, 'result'),
            'relevant_code_files': self._safe_getattr(input, 'relevant_code_files', []),
            'relevant_test_files': self._safe_getattr(input, 'relevant_test_files', []),
            'feedback': self._safe_getattr(input, 'feedback'),
            'existing_tests_passed': self._safe_getattr(input, 'existing_tests_passed', 0),
            'method_name': self._safe_getattr(input, 'method_name'),
            'command_id': self._safe_getattr(input, 'command_id'),
            'test_errors': self._safe_getattr(input, 'test_errors', []),
            'test_log_path': self._safe_getattr(input, 'test_log_path'),
            'recovery_attempt': self._safe_getattr(input, 'recovery_attempt', 0),
            'recovery_confidence': self._safe_getattr(input, 'recovery_confidence', 100.0),
            'recovery_explanation': self._safe_getattr(input, 'recovery_explanation')
        }

        vr = self._safe_getattr(input, 'validation_results')
        if vr:
            result['validation_results'] = {
                'success': getattr(vr, 'success', False),
                'errors': getattr(vr, 'errors', []),
                'warnings': getattr(vr, 'warnings', [])
            }

        return result


class IntegrationInputAdapter(Runnable[Dict[str, Any], CodeGenerationState]):
    """Adapter for integration testing phase: partial dict -> full CodeGenerationState with defaults."""

    def invoke(self, input: Any, config=None) -> CodeGenerationState:
        # Defaults for all fields
        defaults = {
            'issue_url': '',
            'ticket_content': '',
            'title': '',
            'description': '',
            'requirements': [],
            'acceptance_criteria': [],
            'implementation_steps': [],
            'npm_packages': [],
            'manual_implementation_notes': '',
            'code_spec': CodeSpec(
                language="typescript",
                framework="obsidian",
                dependencies=[]
            ),
            'test_spec': TestSpec(
                test_framework="jest",
                coverage_requirements=[]
            ),
            'generated_code': None,
            'generated_tests': None,
            'validation_results': None,
            'result': None,
            'relevant_code_files': [],
            'relevant_test_files': [],
            'feedback': None,
            'method_name': None,
            'command_id': None,
            'existing_tests_passed': 0,
            'test_errors': [],
            'test_log_path': None,
            'recovery_confidence': 100.0,
            'recovery_explanation': None,
        }
        input_dict = asdict(input) if hasattr(type(input), '__dataclass_fields__') else dict(input)
        state_dict = {**defaults, **input_dict}
        return CodeGenerationState(**state_dict)