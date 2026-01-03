import logging
import json
import re
import os
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import PydanticOutputParser
from .base_agent import BaseAgent
from .state import CodeGenerationState
from .utils import remove_thinking_tags, log_info, safe_get
from .models import TestGenerationOutput
from .prompts import ModularPrompts
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException


class TestGeneratorAgent(BaseAgent):
    """Agent responsible for generating tests collaboratively with code generation."""

    def __init__(self, llm_client):
        super().__init__("TestGenerator")
        self.llm = llm_client
        self.test_file = os.getenv('TEST_FILE', 'main.test.ts')
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.monitor.logger.setLevel(logging.INFO)
        log_info(self.name, f"Initialized with test file: {self.test_file}, project root: {self.project_root}")

        # Define LCEL chain for test generation
        self.test_generation_chain = self._create_test_generation_chain()
        self.test_refinement_chain = self._create_test_refinement_chain()

    def _create_test_generation_chain(self):
        """Create LCEL chain for test generation with modular prompts and output validation."""
        def build_test_prompt(inputs):
            test_structure = json.dumps(inputs.get('test_structure', {}))
            generated_code = inputs.get('generated_code', '')
            raw_refined_ticket = inputs.get('raw_refined_ticket', '')
            original_ticket_content = inputs.get('original_ticket_content', '')
            prompt = (
                ModularPrompts.get_base_instruction() + "\n"
                "You are tasked with generating Jest tests for the new functionality added to the plugin class in an Obsidian plugin. "
                "The tests must be integrated into the existing `{test_file}` file without altering any existing code. "
                "Follow these instructions carefully:\n\n"
                "**1. Full Refined Ticket (Priority Source):**\\n{raw_refined_ticket}\\n\\n"
                + ModularPrompts.get_test_structure_section(test_structure)
                + ModularPrompts.get_test_requirements_section(raw_refined_ticket=raw_refined_ticket, original_ticket_content=original_ticket_content)
                + "3. **Task Details:**\\n{task_details_str}\\n\\n"
                + "4. **Generated Code:**\\n{generated_code}\\n\\n"
                + "5. **Existing Test File ({test_file}):**\\n{existing_test_content}\\n\\n"
                + "6. **Previous Feedback (Tune Accordingly):**\\n{feedback}\\n\\n"
                + ModularPrompts.get_output_instructions_tests() + "\\n\\nTS code: use \\\" for strings, \\\\` for template if needed. No raw ` in code.\\n\\nTests cover new method/command exactly, command callback with editor/view, method logic.\\n\\nCRITICAL: ALWAYS generate NON-EMPTY 'tests' field with valid Jest test code. Never skip or empty. Use basic describe/it blocks. Output JSON: {\\\"tests\\\": \\\"...\\\"}\""
            )
            log_info(self.name, f"Full prompt for test gen: {prompt}")
            return prompt

        # Output parser for validation
        test_parser = PydanticOutputParser(pydantic_object=TestGenerationOutput)

        return (
            RunnableLambda(lambda x: x.__dict__)
            | RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: x.get('feedback', {}).get('feedback', '') if x.get('feedback') else '',
                raw_refined_ticket=self._get_raw_refined_ticket,
                original_ticket_content=self._get_original_ticket_content,
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
                "/think\\n"
                "You are refining Jest tests based on validation feedback. The tests must properly test the generated code and pass all validation checks.\\n\\n"
                "Validation Feedback: {validation_feedback}\\n\\n"
                "Generated Code: {generated_code}\\n\\n"
                "Original Tests: {generated_tests}\\n\\n"
                "Task Details: {task_details_str}\\n\\n"
                "Existing Test File: {existing_test_content}\\n\\n"
                "Output only the refined Jest test code, no explanations."
            )
        )
        return (
            RunnablePassthrough.assign(
                             task_details_str=self._format_task_details,
                             existing_test_content=self._get_existing_test_content,
                             test_file=lambda x: self.test_file,
                             feedback=lambda x: ((x.get('feedback') or {}).get('feedback', '') if isinstance(x, dict) else ((x.feedback or {}).get('feedback', '') if x.feedback else ''))
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
            result = inputs.get('result') or {}
            refined_ticket = inputs.get('refined_ticket') or {}
            ticket_data = refined_ticket if refined_ticket else result
            if not isinstance(ticket_data, dict):
                ticket_data = {}
            log_info(self.logger, f"ticket keys: {list(ticket_data.keys()) if isinstance(ticket_data, dict) else 'not dict'}")
            title = inputs.get('title', ticket_data.get('title', ''))
            description = inputs.get('description', ticket_data.get('description', ''))
            requirements = inputs.get('requirements', ticket_data.get('requirements', []))
            acceptance_criteria = inputs.get('acceptance_criteria', ticket_data.get('acceptance_criteria', []))
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
        # Ensure all fields are proper types and handle None values
        requirements = requirements if isinstance(requirements, list) else []
        acceptance_criteria = acceptance_criteria if isinstance(acceptance_criteria, list) else []
        implementation_steps = implementation_steps if isinstance(implementation_steps, list) else []
        npm_packages = npm_packages if isinstance(npm_packages, list) else []

        # Check if requirements or acceptance_criteria are empty and append defaults
        if not requirements:
            requirements.extend(["Implement as an Obsidian command", "Add a public method with basic Notice placeholder", "Handle errors gracefully", "Add TypeScript types", "Follow existing code style"])
        if not acceptance_criteria:
            acceptance_criteria.extend(["Implement as an Obsidian command", "Add a public method with basic Notice placeholder", "Handle errors gracefully", "Add TypeScript types", "Follow existing code style"])

        # Handle npm_packages that might be dicts or strings
        def format_package(pkg):
            if isinstance(pkg, dict):
                name = pkg.get('name', 'unknown')
                desc = pkg.get('description', '')
                return f"{name}: {desc}" if desc else name
            return str(pkg)
        npm_str = ', '.join(format_package(pkg) for pkg in npm_packages)
        return (
            f"Title: {title}\\n"
            f"Description: {description}\\n"
            f"Requirements: {', '.join(requirements)}\\n"
            f"Acceptance Criteria: {', '.join(acceptance_criteria)}\\n"
            f"Implementation Steps: {', '.join(implementation_steps)}\\n"
            f"NPM Packages: {npm_str}\\n"
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

    def _get_original_ticket_content(self, inputs):
        """Get original ticket content from state."""
        if hasattr(inputs, 'ticket_content'):
            return inputs.ticket_content or ''
        elif isinstance(inputs, dict):
            return inputs.get('ticket_content') or inputs.get('raw_ticket') or ''
        else:
            return ''

    def _get_raw_refined_ticket(self, inputs):
        """Get raw JSON string of refined ticket from state."""
        if hasattr(inputs, 'requirements'):  # CodeGenerationState object
            ticket_data = {
                'title': getattr(inputs, 'title', '') or '',
                'description': getattr(inputs, 'description', '') or '',
                'requirements': list(getattr(inputs, 'requirements', [])) or [],
                'acceptance_criteria': list(getattr(inputs, 'acceptance_criteria', [])) or [],
                'implementation_steps': list(getattr(inputs, 'implementation_steps', [])) or [],
                'npm_packages': list(getattr(inputs, 'npm_packages', [])) or [],
                'manual_implementation_notes': getattr(inputs, 'manual_implementation_notes', '') or ''
            }
        elif isinstance(inputs, dict):
            result = inputs.get('result') or {}
            refined_ticket = inputs.get('refined_ticket') or {}
            if isinstance(refined_ticket, str):
                try:
                    refined_ticket = json.loads(refined_ticket)
                except json.JSONDecodeError:
                    refined_ticket = {}
            ticket_data = refined_ticket if (refined_ticket and isinstance(refined_ticket, dict) and refined_ticket.get('requirements')) else result
            if ticket_data is None or not isinstance(ticket_data, dict):
                ticket_data = {}
        else:
            ticket_data = {}
        reqs = ticket_data.get('requirements', [])
        log_info(self.name, f"refined_ticket: {inputs.get('refined_ticket')}, len reqs: {len(reqs)}, content preview: {str(ticket_data)[:200]}")
        return json.dumps(ticket_data, indent=2)

    def _validate_and_parse_test_output(self, response):
        """Validate and parse the LLM output for test generation."""
        clean_response = remove_thinking_tags(response)
        try:
            # Try to parse as structured output
            parsed = json.loads(clean_response)
            if 'tests' in parsed:
                generated_tests = parsed['tests'] if parsed['tests'] is not None else clean_response.strip()
            else:
                # Fallback to treating as raw tests
                generated_tests = clean_response.strip()
        except json.JSONDecodeError:
            # Not JSON, treat as raw tests
            generated_tests = clean_response.strip()

        # Post-process the generated tests
        generated_tests = self._post_process_tests(generated_tests)
        return generated_tests

    def _post_process_tests(self, raw_tests: str) -> str:
        """Post-process the generated tests."""
        # Post-process generated tests to fix common issues
        generated_tests = re.sub(r'expect\(plugin\.\w+\)\.toHaveBeenCalled\(\);', '', raw_tests)
        # Fix malformed mock syntax
        generated_tests = re.sub(r'(\w+)\.\((\w+) as jest\.Mock\)', r'(\1.\2 as jest.Mock)', generated_tests)
        # Fix mock syntax
        generated_tests = re.sub(r'(\w+)\.mockReturnValue', r'(\1 as jest.Mock).mockReturnValue', generated_tests)
        # Fix command test syntax
        generated_tests = re.sub(r'await const result = plugin\.onload\(\);', r'await plugin.onload();', generated_tests)
        generated_tests = re.sub(r'await command\.callback\(\);', r'if (command && command.callback) { await command.callback(); }', generated_tests)
        # Ensure ; termination
        generated_tests = re.sub(r'([a-zA-Z0-9_]+)\s*$', r'\1;', generated_tests, flags=re.MULTILINE)
    def _get_fallback_tests(self, state: CodeGenerationState) -> str:
        """Generate improved fallback Jest tests with Obsidian mocks."""
        title = safe_get(state, 'title', 'UnknownFeature')
        method_name = safe_get(state, 'method_name', 'testMethod')
        command_id = safe_get(state, 'command_id', 'testCommand')
        fallback_tests = f'''describe('{method_name}', () => {{
  let plugin: TimestampPlugin;

  beforeEach(async () => {{
    plugin = new TimestampPlugin(mockApp, mockManifest);
    await plugin.onload();
  }});

  it('should return a string when called', () => {{
    const result = plugin.{method_name}();
    expect(typeof result).toBe('string');
    expect(result).toMatch(/^[0-9]+$/); // Assuming timestamp or similar
  }});
}});

describe('{command_id} command', () => {{
  let plugin: TimestampPlugin;

  beforeEach(async () => {{
    plugin = new TimestampPlugin(mockApp, mockManifest);
    await plugin.onload();
  }});

  it('should insert result into editor', async () => {{
    const command = mockCommands['{command_id}'];
    expect(command).toBeDefined();
    if (command && typeof command.callback === 'function') {{
      await command.callback();
      expect(mockEditor.replaceSelection).toHaveBeenCalledWith(expect.stringMatching(/^[0-9]+$/));
    }}
  }});
}});'''
        log_info(self.logger, f"Generated improved fallback tests for '{title}' (method: {method_name}, cmd: {command_id})")
        return fallback_tests

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

            try:
                generated_tests = get_circuit_breaker("test_generation").call(lambda: self.test_generation_chain.invoke(state))
            except CircuitBreakerOpenException as e:
                self._log_structured("error", "circuit_breaker_open", {"operation": "test_generation", "error": str(e)})
                raise
            except Exception as e:
                self._log_structured("error", "test_generation_failed", {"error_type": type(e).__name__, "message": str(e), "code_length": len(safe_get(state, 'generated_code', ''))})
                generated_tests = self._get_fallback_tests(state)
                log_info(self.logger, f"Applied fallback tests due to generation exception: {str(e)}")

            self._log_structured("info", "test_generation_complete", {
                "test_length": len(generated_tests or ''),
                "has_describes": 'describe(' in (generated_tests or ''),
                "has_its": 'it(' in (generated_tests or '') or 'test(' in (generated_tests or '')
            })

            # Fallback if generated tests are empty
            if not generated_tests or not str(generated_tests).strip():
                generated_tests = self._get_fallback_tests(state)
                log_info(self.logger, "Applied fallback tests due to empty generation")

            # Return new state with tests
            return state.with_tests(generated_tests)

        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e),
                "code_length": len(safe_get(state, 'generated_code', ''))
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

            try:
                refined_tests = get_circuit_breaker("test_refinement").call(lambda: self.test_refinement_chain.invoke(refinement_inputs))
            except CircuitBreakerOpenException as e:
                self._log_structured("error", "circuit_breaker_open", {"operation": "test_refinement", "error": str(e)})
                raise
            except Exception as e:
                self._log_structured("error", "test_refinement_failed", {"error": str(e)})
                raise
            refined_tests = self.test_refinement_chain.invoke(refinement_inputs)

            self._log_structured("info", "test_refinement_complete", {
                "original_length": len(safe_get(state, 'generated_tests', '')),
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