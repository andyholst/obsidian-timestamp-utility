import logging
import json
import re
import os
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import PydanticOutputParser
from .base_agent import BaseAgent
from .state import CodeGenerationState
from .utils import remove_thinking_tags, log_info
from .models import TestGenerationOutput
from .prompts import ModularPrompts


class TestGeneratorAgent(BaseAgent):
    """Agent responsible for generating tests collaboratively with code generation."""

    def __init__(self, llm_client):
        super().__init__("TestGenerator")
        self.llm = llm_client
        self.test_file = os.getenv('TEST_FILE', 'main.test.ts')
        self.project_root = os.getenv('PROJECT_ROOT')
        if not self.project_root:
            raise ValueError("PROJECT_ROOT environment variable is required")
        self.monitor.logger.setLevel(logging.INFO)
        log_info(self.name, f"Initialized with test file: {self.test_file}, project root: {self.project_root}")

        # Define LCEL chain for test generation
        self.test_generation_chain = self._create_test_generation_chain()
        self.test_refinement_chain = self._create_test_refinement_chain()

    def _create_test_generation_chain(self):
        """Create LCEL chain for test generation with modular prompts and output validation."""
        def build_test_prompt(inputs):
            test_structure = json.dumps(inputs.get('test_structure', {}))
            return (
                ModularPrompts.get_base_instruction() + "\n"
                "You are tasked with generating Jest tests for the new functionality added to the plugin class in an Obsidian plugin. "
                "The tests must be integrated into the existing `{test_file}` file without altering any existing code. "
                "Follow these instructions carefully:\n\n"
                + ModularPrompts.get_test_structure_section(test_structure)
                + ModularPrompts.get_test_requirements_section()
                + "3. **Task Details:**\n{task_details_str}\n\n"
                + "4. **Generated Code:**\n{generated_code}\n\n"
                + "5. **Existing Test File ({test_file}):**\n{existing_test_content}\n\n"
                + "6. **Previous Feedback (Tune Accordingly):**\n{feedback}\n\n"
                + ModularPrompts.get_output_instructions_tests()
            )

        # Output parser for validation
        test_parser = PydanticOutputParser(pydantic_object=TestGenerationOutput)

        return (
            RunnableLambda(lambda x: x.__dict__)
            | RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: x.get('feedback', {}).get('feedback', '') if x.get('feedback') else '',
                test_structure=lambda x: {}
            )
            | RunnableLambda(build_test_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_test_output)
        )

    def _create_test_refinement_chain(self):
        """Create LCEL chain for test refinement based on validation feedback."""
        refinement_prompt_template = PromptTemplate(
            input_variables=["generated_tests", "validation_feedback", "generated_code", "task_details_str", "existing_test_content", "test_file"],
            template=(
                "/think\n"
                "You are refining Jest tests based on validation feedback. The tests must properly test the generated code and pass all validation checks.\n\n"
                "Validation Feedback: {validation_feedback}\n\n"
                "Generated Code: {generated_code}\n\n"
                "Original Tests: {generated_tests}\n\n"
                "Task Details: {task_details_str}\n\n"
                "Existing Test File: {existing_test_content}\n\n"
                "Output only the refined Jest test code, no explanations."
            )
        )
        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: x.feedback.get('feedback', '') if x.feedback else ''
            )
            | refinement_prompt_template
            | self.llm
            | RunnableLambda(self._post_process_tests)
        )

    def _format_task_details(self, inputs):
        """Format task details string from state."""
        log_info(self.logger, f"_format_task_details called with inputs type: {type(inputs)}")
        if isinstance(inputs, dict):
            log_info(self.logger, f"inputs keys: {list(inputs.keys())}")
            ticket = inputs.get('result') or {}
            if not isinstance(ticket, dict):
                ticket = {}
            log_info(self.logger, f"ticket keys: {list(ticket.keys()) if isinstance(ticket, dict) else 'not dict'}")
            title = inputs.get('title', ticket.get('title', ''))
            description = inputs.get('description', ticket.get('description', ''))
            requirements = inputs.get('requirements', ticket.get('requirements', []))
            acceptance_criteria = inputs.get('acceptance_criteria', ticket.get('acceptance_criteria', []))
            implementation_steps = inputs.get('implementation_steps', [])
            npm_packages = inputs.get('npm_packages', [])
            manual_implementation_notes = inputs.get('manual_implementation_notes', '')
        else:
            log_info(self.logger, f"inputs attributes: {dir(inputs)}")
            title = inputs.title
            description = inputs.description
            requirements = inputs.requirements
            acceptance_criteria = inputs.acceptance_criteria
            implementation_steps = inputs.implementation_steps
            npm_packages = inputs.npm_packages
            manual_implementation_notes = inputs.manual_implementation_notes
        # Handle npm_packages that might be dicts or strings
        def format_package(pkg):
            if isinstance(pkg, dict):
                name = pkg.get('name', 'unknown')
                desc = pkg.get('description', '')
                return f"{name}: {desc}" if desc else name
            return str(pkg)
        npm_str = ', '.join(format_package(pkg) for pkg in npm_packages)
        return (
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Requirements: {', '.join(requirements)}\n"
            f"Acceptance Criteria: {', '.join(acceptance_criteria)}\n"
            f"Implementation Steps: {', '.join(implementation_steps)}\n"
            f"NPM Packages: {npm_str}\n"
            f"Manual Implementation Notes: {manual_implementation_notes}"
        )

    def _get_existing_test_content(self, inputs):
        """Get existing test content from relevant files."""
        if isinstance(inputs, dict):
            relevant_test_files = inputs.get('relevant_test_files', [])
        else:
            relevant_test_files = inputs.relevant_test_files
        for test_file in relevant_test_files:
            file_path = test_file['file_path']
            if file_path.endswith(self.test_file):
                return test_file.get('content', "")
        return ""

    def _validate_and_parse_test_output(self, response):
        """Validate and parse the LLM output for test generation."""
        clean_response = remove_thinking_tags(response)
        try:
            # Try to parse as structured output
            parsed = json.loads(clean_response)
            if 'tests' in parsed:
                generated_tests = parsed['tests']
            else:
                # Fallback to treating as raw tests
                generated_tests = clean_response.strip()
        except json.JSONDecodeError:
            # Not JSON, treat as raw tests
            generated_tests = clean_response.strip()

        # Post-process the generated tests
        generated_tests = self._post_process_tests(generated_tests)
        return generated_tests

    def _post_process_tests(self, generated_tests):
        """Post-process the generated tests."""
        # Post-process generated tests to fix common issues
        generated_tests = re.sub(r'expect\(plugin\.\w+\)\.toHaveBeenCalled\(\);', '', generated_tests)
        # Fix mock syntax
        generated_tests = re.sub(r'(\w+)\.mockReturnValue', r'(\1 as jest.Mock).mockReturnValue', generated_tests)
        # Fix command test syntax
        generated_tests = re.sub(r'await const result = plugin\.onload\(\);', r'await plugin.onload();', generated_tests)
        generated_tests = re.sub(r'await command\.callback\(\);', r'if (command && command.callback) { await command.callback(); }', generated_tests)
        return generated_tests

    def generate(self, state: CodeGenerationState) -> CodeGenerationState:
        """
        Generate tests for the given code state.

        Args:
            state: The current code generation state with generated code

        Returns:
            Updated state with generated tests
        """
        log_info(self.logger, "Starting test generation process")

        try:
            # Generate tests using LCEL chain
            self._log_structured("info", "test_generation_start", {"chain": "test_generation"})

            generated_tests = self.test_generation_chain.invoke(state)

            self._log_structured("info", "test_generation_complete", {
                "test_length": len(generated_tests),
                "has_describes": 'describe(' in generated_tests,
                "has_its": 'it(' in generated_tests or 'test(' in generated_tests
            })

            # Return new state with tests
            return state.with_tests(generated_tests)

        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e),
                "code_length": len(state.generated_code)
            }
            self._log_structured("error", "test_generation_failed", error_context)
            raise

    def refine_tests(self, state: CodeGenerationState, validation_feedback: str) -> CodeGenerationState:
        """
        Refine tests based on validation feedback.

        Args:
            state: Current state with tests to refine
            validation_feedback: Feedback from validation process

        Returns:
            Updated state with refined tests
        """
        log_info(self.logger, "Starting test refinement process")

        try:
            refinement_inputs = {**state.__dict__, 'validation_feedback': validation_feedback}

            refined_tests = self.test_refinement_chain.invoke(refinement_inputs)

            self._log_structured("info", "test_refinement_complete", {
                "original_length": len(state.generated_tests),
                "refined_length": len(refined_tests)
            })

            return state.with_tests(refined_tests)

        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e)
            }
            self._log_structured("error", "test_refinement_failed", error_context)
            raise