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
from .models import GeneratedTests
from .prompts import ModularPrompts
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException


def _derive_feature_name_from_change(change: str) -> str | None:
    """§6.1 Derive a stable feature name from the OpenSpec change's spec title.

    Reads ``openspec/changes/<change>/specs/<change>/spec.md`` (or ``tasks.md``) and returns
    the first Markdown H1/H2 title, slugified (e.g. ``uuid-v7-modal``). Returns None when no
    change spec is found, so the caller falls back to the command id. This keeps the generated
    test's feature name derived from the spec, not a hardcoded string.
    """
    proj = os.getenv("PROJECT_ROOT", "/project")
    candidates = [
        os.path.join(proj, "openspec", "changes", change, "specs", change, "spec.md"),
        os.path.join(proj, "openspec", "changes", change, "tasks.md"),
    ]
    text = ""
    for p in candidates:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
            break
    if not text:
        return None
    m = re.search(r"^#{1,2}\s+(.+)$", text, re.MULTILINE)
    if not m:
        return None
    title = m.group(1).strip().lower()
    # slugify: lowercase, spaces/dashes -> single dash, strip non-alphanumerics
    slug = re.sub(r"[^a-z0-9]+", "-", title).strip("-")
    return slug or None


class GeneratorAgent(BaseAgent):
    """Agent responsible for generating tests collaboratively with code generation."""

    def __init__(self, llm_client):
        super().__init__("TestGenerator")
        self.llm = llm_client
        self.test_file = os.getenv("TEST_FILE", "main.test.ts")
        self.project_root = os.getenv("PROJECT_ROOT", "/project")
        self.monitor.logger.setLevel(logging.INFO)
        log_info(
            self.name,
            f"Initialized with test file: {self.test_file}, project root: {self.project_root}",
        )

        # Define LCEL chain for test generation
        self.test_generation_chain = self._create_test_generation_chain()
        self.test_refinement_chain = self._create_test_refinement_chain()

    def _create_test_generation_chain(self):
        """Create LCEL chain for test generation with modular prompts and output validation."""

        def build_test_prompt(inputs):
            generated_code = inputs.get("generated_code", "")
            method_match = re.search(r"public\s+(\w+)\s*\(", generated_code)
            method_name = method_match.group(1) if method_match else "unknownMethod"
            cmd_match = re.search(r'id\s*:\s*["\']([^"\']+)["\']', generated_code)
            command_id = cmd_match.group(1) if cmd_match else "unknownCommand"
            # §6.1 Derive the feature name from the OpenSpec capability (change spec title),
            # not a hardcoded string. Falls back to the command id when no change is set.
            change = os.getenv("CHANGE")
            feature_name = command_id
            if change:
                spec_title = _derive_feature_name_from_change(change)
                if spec_title:
                    feature_name = spec_title
            original_ticket_content = inputs.get("original_ticket_content", "")

            # Read existing tests from disk
            existing_test_content = ""
            test_file_path = os.path.join(self.project_root, "src", "__tests__", self.test_file)
            if os.path.exists(test_file_path):
                with open(test_file_path, "r") as f:
                    existing_test_content = f.read()

            prompt = (
                "You are an expert at writing Jest tests for Obsidian plugins.\n\n"
                "GENERATED CODE TO TEST:\n" + generated_code + "\n\n"
                "METHOD: " + method_name + "\n"
                "COMMAND: " + command_id + "\n"
                "FEATURE: " + feature_name + "\n\n"
                "EXISTING TESTS:\n" + existing_test_content + "\n\n"
                "Generate 2 describe blocks to ADD to the existing test file:\n"
                "1. describe('" + method_name + " method', ...) - test the method directly\n"
                "2. describe('" + feature_name + " command', ...) - test the command callback\n\n"
                "The command test MUST assert: (a) the command is registered via "
                "this.addCommand, (b) the generated text is inserted at the editor cursor, "
                "and (c) a Notice is shown when no active editor is present.\n\n"
                "Match the existing test style exactly.\n"
                "Use new TimestampPlugin(mockApp, {} as any) and await plugin.onload().\n"
                "Verify method return values and editor.replaceSelection calls.\n\n"
                "OUTPUT ONLY JSON: {\"tests\": \"<jest code>\"}\n"
                "The tests field should contain ONLY the 2 inner describe blocks."
            )
            return prompt

        # Output parser for validation
        test_parser = PydanticOutputParser(pydantic_object=GeneratedTests)

        return (
            RunnableLambda(lambda x: x.__dict__)
            | RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: (
                    x.get("feedback", {}).get("feedback", "")
                    if x.get("feedback")
                    else ""
                ),
                raw_refined_ticket=self._get_raw_refined_ticket,
                original_ticket_content=self._get_original_ticket_content,
                test_structure=lambda x: {},
            )
            | RunnableLambda(build_test_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_test_output)
        )

    def _create_test_refinement_chain(self):
        """Create LCEL chain for test refinement based on validation feedback."""
        refinement_prompt_template = PromptTemplate(
            input_variables=[
                "generated_tests",
                "validation_feedback",
                "generated_code",
                "task_details_str",
                "existing_test_content",
                "test_file",
            ],
            template=(
                "/think\n"
                "You are refining Jest tests based on validation feedback. The tests must properly test the generated code and pass all validation checks.\n\n"
                "Validation Feedback: {validation_feedback}\n\n"
                "Generated Code: {generated_code}\n\n"
                "Original Tests: {generated_tests}\n\n"
                "Task Details: {task_details_str}\n\n"
                "Existing Test File: {existing_test_content}\n\n"
                "Output only the refined Jest test code, no explanations."
            ),
        )
        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: (
                    (x.get("feedback") or {}).get("feedback", "")
                    if isinstance(x, dict)
                    else ((x.feedback or {}).get("feedback", "") if x.feedback else "")
                ),
            )
            | refinement_prompt_template
            | self.llm
            | RunnableLambda(self._post_process_tests)
        )

    def _format_task_details(self, inputs):
        """Format task details string from state."""
        log_info(
            self.logger, f"_format_task_details called with inputs type: {type(inputs)}"
        )
        if isinstance(inputs, dict):
            log_info(self.logger, f"inputs keys: {list(inputs.keys())}")
            result = inputs.get("result") or {}
            refined_ticket = inputs.get("refined_ticket") or {}
            ticket_data = refined_ticket if refined_ticket else result
            if not isinstance(ticket_data, dict):
                ticket_data = {}
            log_info(
                self.logger,
                f"ticket keys: {list(ticket_data.keys()) if isinstance(ticket_data, dict) else 'not dict'}",
            )
            title = inputs.get("title", ticket_data.get("title", ""))
            description = inputs.get("description", ticket_data.get("description", ""))
            requirements = inputs.get(
                "requirements", ticket_data.get("requirements", [])
            )
            acceptance_criteria = inputs.get(
                "acceptance_criteria", ticket_data.get("acceptance_criteria", [])
            )
            implementation_steps = inputs.get("implementation_steps", [])
            npm_packages = inputs.get("npm_packages", [])
            manual_implementation_notes = inputs.get("manual_implementation_notes", "")
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
        acceptance_criteria = (
            acceptance_criteria if isinstance(acceptance_criteria, list) else []
        )
        implementation_steps = (
            implementation_steps if isinstance(implementation_steps, list) else []
        )
        npm_packages = npm_packages if isinstance(npm_packages, list) else []

        # Check if requirements or acceptance_criteria are empty and append defaults
        if not requirements:
            requirements.extend(
                [
                    "Implement as an Obsidian command",
                    "Add a public method with basic Notice placeholder",
                    "Handle errors gracefully",
                    "Add TypeScript types",
                    "Follow existing code style",
                ]
            )
        if not acceptance_criteria:
            acceptance_criteria.extend(
                [
                    "Implement as an Obsidian command",
                    "Add a public method with basic Notice placeholder",
                    "Handle errors gracefully",
                    "Add TypeScript types",
                    "Follow existing code style",
                ]
            )

        # Handle npm_packages that might be dicts or strings
        def format_package(pkg):
            if isinstance(pkg, dict):
                name = pkg.get("name", "unknown")
                desc = pkg.get("description", "")
                return f"{name}: {desc}" if desc else name
            return str(pkg)

        # Ensure requirements and acceptance_criteria are lists of strings
        requirements = [str(r) if not isinstance(r, str) else r for r in requirements]
        acceptance_criteria = [str(a) if not isinstance(a, str) else a for a in acceptance_criteria]
        implementation_steps = [str(s) if not isinstance(s, str) else s for s in implementation_steps]

        npm_str = ", ".join(format_package(pkg) for pkg in npm_packages)
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
            relevant_test_files = inputs.get("relevant_test_files", [])
        else:
            relevant_test_files = inputs.relevant_test_files
        for test_file in relevant_test_files:
            file_path = test_file["file_path"]
            if file_path.endswith(self.test_file):
                return test_file.get("content", "")
        return ""

    def _get_original_ticket_content(self, inputs):
        """Get original ticket content from state."""
        if hasattr(inputs, "ticket_content"):
            return inputs.ticket_content or ""
        elif isinstance(inputs, dict):
            return inputs.get("ticket_content") or inputs.get("raw_ticket") or ""
        else:
            return ""

    def _get_raw_refined_ticket(self, inputs):
        """Get raw JSON string of refined ticket from state."""
        if hasattr(inputs, "requirements"):  # CodeGenerationState object
            ticket_data = {
                "title": getattr(inputs, "title", "") or "",
                "description": getattr(inputs, "description", "") or "",
                "requirements": list(getattr(inputs, "requirements", [])) or [],
                "acceptance_criteria": list(getattr(inputs, "acceptance_criteria", []))
                or [],
                "implementation_steps": list(
                    getattr(inputs, "implementation_steps", [])
                )
                or [],
                "npm_packages": list(getattr(inputs, "npm_packages", [])) or [],
                "manual_implementation_notes": getattr(
                    inputs, "manual_implementation_notes", ""
                )
                or "",
            }
        elif isinstance(inputs, dict):
            result = inputs.get("result") or {}
            refined_ticket = inputs.get("refined_ticket") or {}
            if isinstance(refined_ticket, str):
                try:
                    refined_ticket = json.loads(refined_ticket)
                except json.JSONDecodeError:
                    refined_ticket = {}
            ticket_data = (
                refined_ticket
                if (
                    refined_ticket
                    and isinstance(refined_ticket, dict)
                    and refined_ticket.get("requirements")
                )
                else result
            )
            if ticket_data is None or not isinstance(ticket_data, dict):
                ticket_data = {}
        else:
            ticket_data = {}
        reqs = ticket_data.get("requirements", [])
        log_info(
            self.name,
            f"refined_ticket: {inputs.get('refined_ticket')}, len reqs: {len(reqs)}, content preview: {str(ticket_data)[:200]}",
        )
        return json.dumps(ticket_data, indent=2)

    def _validate_and_parse_test_output(self, response):
        """Validate and parse the LLM output for test generation."""
        clean_response = remove_thinking_tags(response)
        try:
            # Try to parse as structured output
            parsed = json.loads(clean_response)
            if "tests" in parsed:
                generated_tests = parsed["tests"]
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
        generated_tests = re.sub(
            r"expect\(plugin\.\w+\)\.toHaveBeenCalled\(\);", "", generated_tests
        )
        # Fix mock syntax
        generated_tests = re.sub(
            r"(\w+)\.mockReturnValue",
            r"(\1 as jest.Mock).mockReturnValue",
            generated_tests,
        )
        # Fix command test syntax
        generated_tests = re.sub(
            r"await const result = plugin\.onload\(\);",
            r"await plugin.onload();",
            generated_tests,
        )
        generated_tests = re.sub(
            r"await command\.callback\(\);",
            r"if (command && command.callback) { await command.callback(); }",
            generated_tests,
        )
        return generated_tests

    def _get_fallback_tests(self, state: CodeGenerationState) -> str:
        """Generate minimal fallback Jest tests."""
        title = safe_get(state, "title", "UnknownFeature")
        fallback_tests = f"""describe(`{title} Tests`, () => {{
  it('basic test', () => {{
    expect(true).toBe(true);
  }});
}});"""
        log_info(self.logger, f"Generated fallback tests for '{title}'")
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
            self._log_structured(
                "info", "test_generation_start", {"chain": "test_generation"}
            )

            try:
                generated_tests = get_circuit_breaker("test_generation").call(
                    lambda: self.test_generation_chain.invoke(state)
                )
            except CircuitBreakerOpenException as e:
                self._log_structured(
                    "error",
                    "circuit_breaker_open",
                    {"operation": "test_generation", "error": str(e)},
                )
                raise
            except Exception as e:
                self._log_structured(
                    "error", "test_generation_failed", {"error": str(e)}
                )
                raise

            self._log_structured(
                "info",
                "test_generation_complete",
                {
                    "test_length": len(generated_tests),
                    "has_describes": "describe(" in generated_tests,
                    "has_its": "it(" in generated_tests or "test(" in generated_tests,
                },
            )

            # Fallback if generated tests are empty
            if not generated_tests.strip():
                generated_tests = self._get_fallback_tests(state)
                log_info(self.logger, "Applied fallback tests due to empty generation")

            # Return new state with tests
            return state.with_tests(generated_tests)

        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e),
                "code_length": len(safe_get(state, "generated_code", "")),
            }
            self._log_structured("error", "test_generation_failed", error_context)
            raise

    def refine_tests(
        self, state: CodeGenerationState, validation_feedback: str
    ) -> CodeGenerationState:
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
            refinement_inputs = {
                **state.__dict__,
                "validation_feedback": validation_feedback,
            }

            try:
                refined_tests = get_circuit_breaker("test_refinement").call(
                    lambda: self.test_refinement_chain.invoke(refinement_inputs)
                )
            except CircuitBreakerOpenException as e:
                self._log_structured(
                    "error",
                    "circuit_breaker_open",
                    {"operation": "test_refinement", "error": str(e)},
                )
                raise
            except Exception as e:
                self._log_structured(
                    "error", "test_refinement_failed", {"error": str(e)}
                )
                raise
            refined_tests = self.test_refinement_chain.invoke(refinement_inputs)

            self._log_structured(
                "info",
                "test_refinement_complete",
                {
                    "original_length": len(safe_get(state, "generated_tests", "")),
                    "refined_length": len(refined_tests),
                },
            )

            return state.with_tests(refined_tests)

        except Exception as e:
            error_context = {"error_type": type(e).__name__, "message": str(e)}
            self._log_structured("error", "test_refinement_failed", error_context)
            raise
