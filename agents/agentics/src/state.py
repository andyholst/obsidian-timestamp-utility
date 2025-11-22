from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .models import CodeSpec, TestSpec, ValidationResults

class State(TypedDict, total=False):
    url: str
    ticket_content: str
    refined_ticket: dict
    result: dict
    generated_code: str
    generated_tests: str
    existing_tests_passed: int
    existing_coverage_all_files: float
    relevant_code_files: List[Dict[str, str]]
    relevant_test_files: List[Dict[str, str]]
    available_dependencies: List[str]
    post_integration_tests_passed: int
    post_integration_coverage_all_files: float
    coverage_improvement: float
    tests_improvement: int
    feedback_metrics: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    memory: Dict[str, Any]
    feedback: Dict[str, Any]

@dataclass(frozen=True)
class CodeGenerationState:
    """Immutable state for code generation workflow"""
    issue_url: str
    ticket_content: str
    title: str
    description: str
    requirements: List[str]
    acceptance_criteria: List[str]
    code_spec: CodeSpec
    test_spec: TestSpec
    implementation_steps: List[str] = field(default_factory=list)
    npm_packages: List[str] = field(default_factory=list)
    manual_implementation_notes: str = ""
    generated_code: Optional[str] = None
    generated_tests: Optional[str] = None
    validation_results: Optional[ValidationResults] = None
    result: Optional[Dict[str, Any]] = None
    relevant_code_files: List[Dict[str, str]] = field(default_factory=list)
    relevant_test_files: List[Dict[str, str]] = field(default_factory=list)
    feedback: Optional[Dict[str, Any]] = None
    method_name: Optional[str] = None
    command_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    existing_tests_passed: int = 0

    def with_code(self, code: str, method_name: Optional[str] = None, command_id: Optional[str] = None) -> 'CodeGenerationState':
        """Return new state with generated code"""
        return CodeGenerationState(
            **{k: v for k, v in self.__dict__.items() if k not in ['generated_code', 'method_name', 'command_id']},
            generated_code=code,
            method_name=method_name,
            command_id=command_id
        )

    def with_tests(self, tests: str) -> 'CodeGenerationState':
        """Return new state with generated tests"""
        return CodeGenerationState(
            **{k: v for k, v in self.__dict__.items() if k != 'generated_tests'},
            generated_tests=tests
        )

    def with_validation_results(self, results: ValidationResults) -> 'CodeGenerationState':
        """Return new state with validation results"""
        return CodeGenerationState(
            **{k: v for k, v in self.__dict__.items() if k != 'validation_results'},
            validation_results=results
        )

    def with_validation(self, validation_result: Dict[str, Any]) -> 'CodeGenerationState':
        """Return new state with validation result"""
        results = ValidationResults(
            success=validation_result.get('passed', False),
            errors=validation_result.get('issues', []),
            warnings=[]
        )
        return self.with_validation_results(results)

    def with_feedback(self, feedback: Dict[str, Any]) -> 'CodeGenerationState':
        """Return new state with feedback"""
        return CodeGenerationState(
            **{k: v for k, v in self.__dict__.items() if k != 'feedback'},
            feedback=feedback
        )

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return a copy of the history"""
        return self.history.copy()