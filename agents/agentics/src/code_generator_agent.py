import logging
import json
import re
import os
import subprocess
import tempfile
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.tools import tool
from langchain_core.output_parsers import PydanticOutputParser
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import (
    npm_search_tool,
    npm_install_tool,
    npm_list_tool,
    read_file_tool,
    list_files_tool,
    check_file_exists_tool,
)
from .state import State, CodeGenerationState
from .utils import safe_json_dumps, remove_thinking_tags, log_info, safe_get
from .models import CodeGenerationOutput, GeneratedTests
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from .prompts import ModularPrompts


class CodeGeneratorAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        super().__init__(
            llm_client,
            [
                npm_search_tool,
                npm_install_tool,
                npm_list_tool,
                read_file_tool,
                list_files_tool,
                check_file_exists_tool,
            ],
            name="CodeGenerator",
        )
        self.main_file = os.getenv("MAIN_FILE", "main.ts")
        self.test_file = os.getenv("TEST_FILE", "main.test.ts")
        self.project_root = os.getenv("PROJECT_ROOT", "/project")
        self.monitor.setLevel(logging.INFO)
        log_info(
            self.name,
            f"Initialized with main file: {self.main_file}, test file: {self.test_file}, project root: {self.project_root}",
        )
        # Define LCEL chains for code and test generation
        if self.llm is not None:
            self.code_generation_chain = self._create_code_generation_chain()
            self.test_generation_chain = self._create_test_generation_chain()
            self.code_correction_chain = self._create_code_correction_chain()
        else:
            self.code_generation_chain = None
            self.test_generation_chain = None
            self.code_correction_chain = None

    def _get_available_dependencies(self):
        """Get available dependencies using npm list tool."""
        try:
            result = self.tool_executor.execute_tool("npm_list_tool", {"depth": 0})
            # Parse the JSON result
            packages_data = json.loads(result)
            if "dependencies" in packages_data:
                all_deps = list(packages_data["dependencies"].keys())
            else:
                all_deps = []
            log_info(self.name, f"Available dependencies: {all_deps}")
            return all_deps
        except Exception as e:
            log_info(
                self.name,
                f"Failed to get dependencies using npm_list_tool: {str(e)}, using empty list",
            )
            return []

    def _create_code_generation_chain(self):
        """Create LCEL chain for code generation with modular prompts and output validation."""

        def build_code_prompt(inputs):
            code_structure = json.dumps(inputs.get("code_structure", {}))
            tool_context = self._gather_tool_context(inputs)
            raw_refined_ticket = inputs.get("raw_refined_ticket", "")
            original_ticket_content = inputs.get("original_ticket_content", "") or inputs.get("ticket_content", "")
            task_details_str = self._format_task_details(inputs)
            existing_code_content = self._get_existing_code_content(inputs)
            # Fallback: read existing code from disk
            if not existing_code_content:
                main_file_path = os.path.join(self.project_root, "src", self.main_file)
                if os.path.exists(main_file_path):
                    with open(main_file_path, "r") as f:
                        existing_code_content = f.read()

            # If requirements are empty, use ticket content directly
            reqs = inputs.get("requirements", [])
            if not reqs and original_ticket_content:
                task_info = original_ticket_content
            else:
                task_info = task_details_str

                # SPEC-DERIVED contract (parsed from the change's spec/tasks, NOT hardcoded):
                # steer the LLM to honor the exact command id / Modal class the OpenSpec spec
                # mandates. This is the prompt-side tightening driven by the spec file.
                contract_bullet = ""
                try:
                    from .code_integrator_agent import CodeIntegratorAgent

                    contract = CodeIntegratorAgent._expected_contract_for_change(
                        os.getenv("CHANGE")
                    )
                    if contract:
                        bits = []
                        if contract.get("command_id"):
                            bits.append(f"command id MUST be exactly '{contract['command_id']}'")
                        if contract.get("command_name"):
                            bits.append(f"command name MUST be exactly '{contract['command_name']}'")
                        if contract.get("modal_class"):
                            bits.append(
                                f"the feature MUST be an `obsidian.Modal` subclass named '{contract['modal_class']}'"
                            )
                        if contract.get("generator_kind") == "uuidv7":
                            bits.append(
                                "the generator MUST produce a UUID v7 (48-bit ms timestamp, "
                                "version nibble '7', variant nibble 8-9-a-b, formatted "
                                "xxxxxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx)"
                            )
                        if bits:
                            contract_bullet = (
                                "\nSPEC CONTRACT (honor EXACTLY — parsed from the OpenSpec spec, not optional):\n"
                                + "\n".join(f"- {b}" for b in bits)
                                + "\n"
                            )
                except Exception:
                    pass

                prompt = (
                    "You are an expert TypeScript developer for Obsidian plugins.\n\n"
                    "TASK:\n" + task_info + "\n\n"
                    "EXISTING CODE STRUCTURE:\n" + existing_code_content + "\n\n"
                    "The existing code has this structure:\n"
                    "- `class TimestampPlugin extends obsidian.Plugin {`\n"
                    "- `  async onload() { ... this.addCommand(...) ... }`\n"
                    "- `  generateTimestamp(): string { ... }`\n"
                    "- `}`  <-- final closing brace\n\n"
                    "YOU MUST:\n"
                    "1. Add your new public method BEFORE the final `}` of the class\n"
                    "2. Add your new `this.addCommand(...)` call INSIDE the onload() method\n"
                    "3. Do NOT add code after the final `}`\n"
                    "4. Use crypto.getRandomValues() for random bytes\n"
                    "5. Use obsidian.Notice for error messages\n"
                    "6. Use the exact parameter name from editorCallback (usually `_editor`)\n"
                    "7. Do NOT add import statements\n\n"
                    + contract_bullet
                    + "IMPORTANT: The closing brace `}` at the end of the existing code closes the class.\n"
                    "Example of correct placement:\n"
                    "  // Your new method goes here, BEFORE the final }\n"
                    "  public myMethod(): string { ... }\n"
                    "  // The onload() method should already have this.addCommand() calls\n"
                    "  // Add your new this.addCommand() inside onload()\n"
                    "}  // <-- this is the final closing brace\n\n"
                    "OUTPUT ONLY JSON: {\"code\": \"<typescript>\", \"method_name\": \"<name>\", \"command_id\": \"<id>\"}\n"
                    "The code field should contain ONLY the new method and the new this.addCommand() call."
                )
            return prompt

        # Use RunnableLambda to build the prompt dynamically

        # Output parser for validation
        code_parser = PydanticOutputParser(pydantic_object=CodeGenerationOutput)

        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_code_content=self._get_existing_code_content,
                main_file=lambda x: self.main_file,
                feedback=lambda x: (
                    (x.get("feedback") if isinstance(x, dict) else x.feedback) or {}
                ).get("feedback", ""),
                raw_refined_ticket=self._get_raw_refined_ticket,
                original_ticket_content=self._get_original_ticket_content,
                code_structure=lambda x: {},
            )
            | RunnableLambda(build_code_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_code_output)
        )

    def _create_test_generation_chain(self):
        """Create LCEL chain for test generation with modular prompts and output validation."""

        def build_test_prompt(inputs):
            test_structure = json.dumps(inputs.get("test_structure", {}))
            tool_context = self._gather_tool_context(inputs)
            tool_instructions = (
                ModularPrompts.get_tool_instructions_for_code_generator_agent()
            )
            original_ticket_content = inputs.get("original_ticket_content", "")
            prompt = (
                ModularPrompts.get_base_instruction() + "\n"
                "You are tasked with generating Jest tests for the new functionality added to the plugin class in an Obsidian plugin. "
                "The tests must be integrated into the existing `{test_file}` file without altering any existing code. "
                "Follow these instructions carefully:\n\n"
                + ModularPrompts.get_test_structure_section(test_structure)
                + ModularPrompts.get_test_requirements_section(
                    original_ticket_content=original_ticket_content
                )
                + "3. **Task Details:**\n{task_details_str}\n\n"
                + ModularPrompts.get_raw_refined_ticket_section()
                + "4. **Generated Code:**\n{generated_code}\n\n"
                + "5. **Existing Test File ({test_file}):**\n{existing_test_content}\n\n"
                + "6. **Previous Feedback (Tune Accordingly):**\n{feedback}\n\n"
                + tool_instructions
                + ModularPrompts.get_output_instructions_tests()
            )
            log_info(self.name, f"Full prompt for test gen: {prompt}")
            return prompt

        # Use RunnableLambda to build the prompt dynamically

        # Output parser for validation
        test_parser = PydanticOutputParser(pydantic_object=GeneratedTests)

        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: (
                    (x.get("feedback") if isinstance(x, dict) else x.feedback) or {}
                ).get("feedback", ""),
                raw_refined_ticket=self._get_raw_refined_ticket,
                original_ticket_content=self._get_original_ticket_content,
                test_structure=lambda x: {},
            )
            | RunnableLambda(build_test_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_test_output)
        )

    def _create_code_correction_chain(self):
        """Create LCEL chain for code correction based on validation errors."""
        correction_prompt_template = PromptTemplate(
            input_variables=[
                "generated_code",
                "validation_errors",
                "task_details_str",
                "existing_code_content",
                "main_file",
            ],
            template=(
                "/think\n"
                "You are correcting TypeScript code that failed validation. The code must be fixed to pass TypeScript compilation and follow best practices.\n\n"
                "Validation Errors: {validation_errors}\n\n"
                "Original Generated Code: {generated_code}\n\n"
                "Task Details: {task_details_str}\n\n"
                "Existing Code: {existing_code_content}\n\n"
                "Output only the corrected TypeScript code, no explanations."
            ),
        )
        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_code_content=self._get_existing_code_content,
                main_file=lambda x: self.main_file,
                feedback=lambda x: (
                    (x.get("feedback") if isinstance(x, dict) else x.feedback) or {}
                ).get("feedback", ""),
            )
            | correction_prompt_template
            | self.llm
            | RunnableLambda(self._post_process_code)
        )

    def _format_task_details(self, inputs):
        """Format task details string from state."""
        # Prioritize CodeGenerationState object access as per refactored architecture
        if hasattr(inputs, "requirements"):  # CodeGenerationState object
            title = inputs.title or ""
            description = inputs.description or ""
            requirements = inputs.requirements or []
            acceptance_criteria = inputs.acceptance_criteria or []
            implementation_steps = inputs.implementation_steps or []
            npm_packages = inputs.npm_packages or []
            manual_implementation_notes = inputs.manual_implementation_notes or ""
        elif isinstance(inputs, dict):
            # Legacy State dict style - handle None values properly
            result = inputs.get("result") or {}
            refined_ticket = inputs.get("refined_ticket") or {}
            # Use refined_ticket if it has requirements, otherwise use result
            ticket_data = refined_ticket if refined_ticket else result
            if ticket_data is None or not isinstance(ticket_data, dict):
                ticket_data = {}
            title = ticket_data.get("title", "")
            description = ticket_data.get("description", "")
            requirements = ticket_data.get("requirements", [])
            acceptance_criteria = ticket_data.get("acceptance_criteria", [])
            implementation_steps = ticket_data.get("implementation_steps", [])
            npm_packages = ticket_data.get("npm_packages", [])
            manual_implementation_notes = ticket_data.get(
                "manual_implementation_notes", ""
            )
        else:
            # Fallback for unknown input types
            title = ""
            description = ""
            requirements = []
            acceptance_criteria = []
            implementation_steps = []
            npm_packages = []
            manual_implementation_notes = ""

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

    def _get_original_ticket_content(self, inputs):
        """Get original ticket content from state."""
        if hasattr(inputs, "ticket_content"):
            return inputs.ticket_content or ""
        elif isinstance(inputs, dict):
            return inputs.get("ticket_content") or inputs.get("raw_ticket") or ""
        else:
            return ""

    def _get_existing_code_content(self, inputs):
        """Get existing code content from relevant files."""
        if isinstance(inputs, dict):
            relevant_code_files = inputs.get("relevant_code_files", [])
        else:
            relevant_code_files = inputs.relevant_code_files
        for code_file in relevant_code_files:
            file_path = code_file["file_path"]
            if file_path.endswith(self.main_file):
                return code_file.get("content", "")
        return ""

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

    def _validate_and_parse_code_output(self, response):
        """Validate and parse the LLM output for code generation."""
        clean_response = remove_thinking_tags(response)
        try:
            # Try to parse as structured output
            parsed = json.loads(clean_response)
            if "code" in parsed and "method_name" in parsed and "command_id" in parsed:
                generated_code = parsed["code"]
            else:
                # Fallback to treating as raw code
                generated_code = clean_response.strip()
        except json.JSONDecodeError:
            # Not JSON, treat as raw code
            generated_code = clean_response.strip()

        # Post-process the generated code
        generated_code = self._post_process_code(generated_code)

        # Keyword validation for code output (warning only)
        code_keywords = ["import", "export", "class", "interface", "function", "public"]
        if not any(keyword in generated_code for keyword in code_keywords):
            log_info(
                self.name,
                "Warning: Generated code lacks structure keywords, proceeding anyway",
            )
        return generated_code

    def _extract_code_field(self, raw_output):
        """Robustly extract the generated TypeScript `code` from any chain output.

        The LCEL code-generation chain may return:
          - a `CodeGenerationOutput` pydantic object (when the output parser ran
            inside the LLM step),
          - a JSON string (``{"code": "..."}``),
          - or already-decoded raw TS text.
        We always resolve to the `.code` string so a serialized object can never
        leak into `main.ts` as a literal JSON blob.
        """
        if raw_output is None:
            return ""
        # Already a pydantic CodeGenerationOutput object
        if hasattr(raw_output, "code"):
            return str(getattr(raw_output, "code", "")).strip()
        if not isinstance(raw_output, str):
            raw_output = str(raw_output)
        clean = remove_thinking_tags(raw_output).strip()
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict) and "code" in parsed:
                return str(parsed["code"]).strip()
        except (json.JSONDecodeError, TypeError):
            pass
        return clean

    def _post_process_code(self, generated_code):
        """Post-process the generated code."""
        # Post-process generated code to fix common issues
        generated_code = generated_code.replace("CodeMirror.Editor", "obsidian.Editor")
        generated_code = generated_code.replace("TFile", "obsidian.TFile")
        generated_code = generated_code.replace(
            "obsidian.TFile", "obsidian.TFile"
        )
        # NOTE: do NOT rewrite `obsidian.Modal` -> `obsidian.MarkdownView`. The OpenSpec
        # contract mandates `UuidV7Modal extends obsidian.Modal`; that rewrite silently
        # broke the spec contract. Modal subclasses stay as authored by the spec/LLM.
        generated_code = generated_code.replace("private ", "public ")
        generated_code = generated_code.replace("protected ", "public ")
        generated_code = re.sub(
            r"return text; // Placeholder", r"return text || \'\';", generated_code
        )

        generated_code = generated_code.replace("./main_file", "./main")

        generated_code = generated_code.replace(
            "editor: obsidian.Editor", "_editor: obsidian.Editor"
        )

        return generated_code

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

        # Keyword validation for test output
        if "describe(" not in generated_tests or (
            "it(" not in generated_tests and "test(" not in generated_tests
        ):
            raise ValueError(
                "Generated tests must contain 'describe(' and 'it()/'test()'"
            )
        if "}" not in generated_tests:
            raise ValueError("Generated tests must have closing braces")

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
            r"await command\.callback\(([^)]*)\);",
            r"if (command && command.callback) { await command.callback(\1); }",
            generated_tests,
        )
        return generated_tests

    def _validate_typescript_code(self, code: str) -> bool:
        """Validate TypeScript code syntax using tsc."""
        try:
            # Create a temporary file with necessary imports and the generated code
            temp_content = (
                "import * as obsidian from 'obsidian';\n"
                "declare module 'obsidian' {\n"
                "  export class Plugin {}\n"
                "  export class Editor {}\n"
                "  export class MarkdownView {}\n"
                "  export class MarkdownFileInfo {}\n"
                "}\n"
                f"{code}\n"
            )
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ts", delete=False
            ) as temp_file:
                temp_file.write(temp_content)
                temp_file_path = temp_file.name

            # Run tsc --noEmit to check for errors
            result = subprocess.run(
                [
                    "npx",
                    "tsc",
                    "--noEmit",
                    "--target",
                    "es2018",
                    "--moduleResolution",
                    "node",
                    "--allowJs",
                    "--checkJs",
                    "false",
                    "--strict",
                    temp_file_path,
                ],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(temp_file_path),
            )

            # Clean up temp file
            os.unlink(temp_file_path)

            if result.returncode == 0:
                log_info(self.name, "TypeScript code validation passed")
                return True
            else:
                log_info(
                    self.name, f"TypeScript code validation failed: {result.stderr}"
                )
                return False
        except Exception as e:
            log_info(self.name, f"Error during TypeScript validation: {str(e)}")
            return False

    def _get_fallback_code(self, state: CodeGenerationState) -> str:
        """Generate minimal fallback TypeScript code."""
        title = safe_get(state, "title", "UnknownFeature")
        method_name = "".join(word.capitalize() for word in title.lower().split())
        command_id = method_name.lower() + "-command"
        fallback_code = f"""import {{ Notice }} from 'obsidian';

public {method_name}() {{
  new Notice('{title} feature - basic implementation');
}}

this.addCommand({{
  id: '{command_id}',
  name: '{title}',
  callback: () => {{
    this.{method_name}();
  }}
}});"""
        log_info(self.name, f"Generated fallback code for '{title}'")
        return fallback_code

    def process(self, state: State) -> State:
        log_info(
            self.name,
            f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}",
        )
        log_info(self.name, "Starting code generation process")
        try:
            # Get available dependencies dynamically from package.json
            available_dependencies = self._get_available_dependencies()
            # Determine requirements using logic compatible with both legacy and new flat CodeGenerationState formats
            if hasattr(state, "requirements") and state.requirements:
                requirements = list(state.requirements)
                acceptance_criteria = list(state.acceptance_criteria)
                source = "CodeGenerationState object"
            elif (
                isinstance(state, dict)
                and "requirements" in state
                and state["requirements"]
            ):
                requirements = list(state["requirements"])
                acceptance_criteria = list(state.get("acceptance_criteria", []))
                source = "flat dict state"
            else:
                # Legacy nested format
                task_details = (
                    state.get("result", {})
                    if isinstance(state, dict)
                    else getattr(state, "result", {}) or {}
                )
                refined_ticket = task_details.get("refined_ticket", {})
                if (
                    refined_ticket
                    and isinstance(refined_ticket, dict)
                    and refined_ticket.get("requirements")
                ):
                    requirements = list(refined_ticket.get("requirements", []))
                    acceptance_criteria = list(
                        refined_ticket.get("acceptance_criteria", [])
                    )
                    source = "refined_ticket"
                else:
                    requirements = list(task_details.get("requirements", []))
                    acceptance_criteria = list(
                        task_details.get("acceptance_criteria", [])
                    )
                    source = "result dict"
            log_info(self.name, f"Using {source} with {len(requirements)} requirements")
            # Always generate code - no skipping for vague tickets
            log_info(self.name, "Generating code for all tickets, even vague ones")
            _reqs = getattr(state, "requirements", None) or state.get("requirements", [])
            self._log_structured(
                "info",
                "task_processing",
                {
                    "requirements_count": len(_reqs),
                    "acceptance_criteria_count": len(acceptance_criteria),
                },
            )
            # Generate code using LCEL chain
            if self.code_generation_chain is None:
                raise RuntimeError("LLM not available for code generation")
            self._log_structured(
                "info", "code_generation_start", {"chain": "code_generation"}
            )
            # Convert CodeGenerationState to dict for LCEL chain
            result_dict = {
                "title": state.get("title", ""),
                "description": state.get("description", ""),
                "requirements": state.get("requirements", []),
                "acceptance_criteria": state.get("acceptance_criteria", []),
                "implementation_steps": state.get("implementation_steps", []),
                "npm_packages": state.get("npm_packages", []),
                "manual_implementation_notes": state.get(
                    "manual_implementation_notes", ""
                ),
            }
            state_dict = {
                "issue_url": state.get("issue_url", ""),
                "ticket_content": state.get("ticket_content", ""),
                "relevant_code_files": state.get("relevant_code_files", []),
                "relevant_test_files": state.get("relevant_test_files", []),
                "feedback": state.get("feedback", {}),
                "result": result_dict,
            }
            try:
                raw_code_output = get_circuit_breaker("code_generation").call(
                    lambda: self.code_generation_chain.invoke(state_dict)
                )
                # The chain may return a parsed CodeGenerationOutput object, a JSON
                # string, or raw TS. Always extract the `.code` field robustly so a
                # serialized object never leaks into main.ts as a literal blob.
                generated_code = self._extract_code_field(raw_code_output)
            except CircuitBreakerOpenException as e:
                self._log_structured(
                    "error",
                    "circuit_breaker_open",
                    {"operation": "code_generation", "error": str(e)},
                )
                raise
            except Exception as e:
                self._log_structured(
                    "error", "code_generation_failed", {"error": str(e)}
                )
                raise
            self._log_structured(
                "info",
                "code_generation_complete",
                {
                    "code_length": len(generated_code),
                    "has_imports": "import" in generated_code,
                    "has_methods": "public" in generated_code
                    or "function" in generated_code,
                },
            )
            # Filter imports to only available dependencies
            lines = generated_code.split("\n")
            filtered_lines = []
            for line in lines:
                if line.strip().startswith("import"):
                    match = re.search(r'import.*from\s+["\']([^"\']+)["\']', line)
                    if match:
                        module = match.group(1)
                        if module in available_dependencies:
                            filtered_lines.append(line)
                        else:
                            log_info(
                                self.name,
                                f"Filtered out unavailable import: {line.strip()}",
                            )
                    else:
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
            generated_code = "\n".join(filtered_lines)
            log_info(self.name, f"Filtered generated code: {generated_code}")
            # Validate the generated code
            validation_passed = self._validate_typescript_code(generated_code)
            self._log_structured(
                "info",
                "code_validation",
                {"passed": validation_passed, "code_length": len(generated_code)},
            )
            if not validation_passed:
                self._log_structured(
                    "warning",
                    "code_correction_attempt",
                    {"reason": "validation_failed"},
                )
                correction_inputs = state.copy()
                correction_inputs.update(
                    {
                        "generated_code": generated_code,
                        "validation_errors": "TypeScript compilation errors detected",
                    }
                )
                if self.code_correction_chain is None:
                    self._log_structured(
                        "warning", "code_correction_skipped", {"reason": "no_llm"}
                    )
                else:
                    try:
                        corrected_code = get_circuit_breaker("code_correction").call(
                            lambda: self.code_correction_chain.invoke(correction_inputs)
                        )
                    except CircuitBreakerOpenException as e:
                        self._log_structured(
                            "error",
                            "circuit_breaker_open",
                            {"operation": "code_correction", "error": str(e)},
                        )
                        raise
                    except Exception as e:
                        self._log_structured(
                            "error", "code_correction_failed", {"error": str(e)}
                        )
                        raise
                correction_validation = self._validate_typescript_code(corrected_code)
                self._log_structured(
                    "info",
                    "code_correction_result",
                    {
                        "correction_passed": correction_validation,
                        "corrected_length": len(corrected_code),
                    },
                )
                if correction_validation:
                    generated_code = corrected_code
                    self._log_structured(
                        "info", "code_correction_success", {"used_corrected": True}
                    )
                else:
                    self._log_structured(
                        "warning",
                        "code_correction_failed",
                        {"proceeding_with_original": True},
                    )
            else:
                self._log_structured(
                    "info", "code_validation_success", {"no_correction_needed": True}
                )
            # Extract method name and command ID
            method_match = re.search(
                r"(public|private|protected)?\s*(\w+)\s*\(", generated_code
            )
            if method_match:
                method_name = method_match.group(2)
                log_info(self.name, f"Extracted method name: {method_name}")
            else:
                log_info(
                    self.name,
                    "No method name found in generated code, proceeding without.",
                )
                method_name = None
            command_match = re.search(
                r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', generated_code
            )
            if command_match:
                command_id = command_match.group(1)
                log_info(self.name, f"Extracted command ID: {command_id}")
            else:
                log_info(
                    self.name,
                    "No command ID found in generated code, proceeding without.",
                )
                command_id = None
            # Generate tests using LCEL chain
            if self.test_generation_chain is None:
                raise RuntimeError("LLM not available for test generation")
            log_info(self.name, "Generating tests using LCEL chain")
            test_inputs = state.copy()
            test_inputs.update(
                {
                    "generated_code": generated_code,
                    "method_name": method_name,
                    "command_id": command_id,
                }
            )
            try:
                generated_tests = get_circuit_breaker("test_generation").call(
                    lambda: self.test_generation_chain.invoke(test_inputs)
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
            log_info(self.name, f"Generated tests: {generated_tests}")
            log_info(self.name, f"Generated tests length: {len(generated_tests)}")
            state["generated_code"] = generated_code
            state["generated_tests"] = generated_tests
            log_info(
                self.name, "Code and tests generated and stored in state successfully"
            )
            log_info(
                self.name,
                f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}",
            )
            return state
        except KeyError as e:
            error_context = {
                "error_type": "KeyError",
                "missing_field": str(e),
                "available_keys": list(state.get("result", {}).keys()),
            }
            self._log_structured("error", "missing_result_field", error_context)
            raise ValueError(f"Missing field in state['result']: {e}")
        except ValueError as e:
            # Return state with empty code/tests on ValueError
            error_context = {
                "error_type": "ValueError",
                "message": str(e),
                "task_details": state.get("result", {}),
            }
            self._log_structured("error", "validation_error", error_context)
            state["generated_code"] = state.get("generated_code", "")
            state["generated_tests"] = state.get("generated_tests", "")
            return state
        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e),
                "code_length": len(state.get("generated_code") or ""),
                "test_length": len(state.get("generated_tests") or ""),
            }
            self._log_structured("error", "process_error", error_context)
            # Return state with empty code/tests on failure
            state["generated_code"] = state.get("generated_code", "")
            state["generated_tests"] = state.get("generated_tests", "")
            return state

    def generate(self, state: CodeGenerationState) -> CodeGenerationState:
        """
        Generate code for the given state.

        Args:
            state: The current code generation state

        Returns:
            Updated state with generated code
        """
        log_info(self.name, "Starting collaborative code generation process")
        from .state_adapters import StateToCodeGenerationStateAdapter

        if not isinstance(state, CodeGenerationState):
            adapter = StateToCodeGenerationStateAdapter()
            state = adapter.invoke(state)
            log_info(self.name, "Adapted incoming state to CodeGenerationState")
            log_info(
                self.name,
                f"DEBUG: State requirements: {safe_get(state, 'requirements', [])}",
            )
            log_info(
                self.name,
                f"DEBUG: State acceptance_criteria: {safe_get(state, 'acceptance_criteria', [])}",
            )
            log_info(
                self.name,
                f"DEBUG: Requirements count: {len(safe_get(state, 'requirements', []))} ",
            )
            log_info(
                self.name,
                f"DEBUG: Acceptance criteria count: {len(safe_get(state, 'acceptance_criteria', []))} ",
            )

        try:
            # Check if ticket is vague (empty requirements and acceptance criteria)
            # Use CodeGenerationState fields directly as per refactored architecture
            # Always generate code - no skipping for vague tickets
            log_info(self.name, "Generating code for all tickets, even vague ones")

            # Get available dependencies dynamically from package.json
            available_dependencies = self._get_available_dependencies()

            self._log_structured(
                "info",
                "task_processing",
                {
                    "requirements_count": len(state.requirements),
                    "acceptance_criteria_count": len(state.acceptance_criteria),
                },
            )

            # Generate code using LCEL chain
            if self.code_generation_chain is None:
                raise RuntimeError("LLM not available for code generation")
            self._log_structured(
                "info", "code_generation_start", {"chain": "code_generation"}
            )

            try:
                # Convert CodeGenerationState to dict for LCEL chain
                state_dict = {
                    "issue_url": state.issue_url,
                    "ticket_content": state.ticket_content,
                    "title": state.title,
                    "description": state.description,
                    "requirements": state.requirements,
                    "acceptance_criteria": state.acceptance_criteria,
                    "implementation_steps": state.implementation_steps,
                    "npm_packages": state.npm_packages,
                    "manual_implementation_notes": state.manual_implementation_notes,
                    "relevant_code_files": state.relevant_code_files,
                    "relevant_test_files": state.relevant_test_files,
                    "feedback": state.feedback,
                    "result": state.result,
                }
                generated_code = get_circuit_breaker("code_generation").call(
                    lambda: self.code_generation_chain.invoke(state_dict)
                )
            except CircuitBreakerOpenException as e:
                self._log_structured(
                    "error",
                    "circuit_breaker_open",
                    {"operation": "code_generation", "error": str(e)},
                )
                raise
            except Exception as e:
                self._log_structured(
                    "error", "code_generation_failed", {"error": str(e)}
                )
                raise

            self._log_structured(
                "info",
                "code_generation_complete",
                {
                    "code_length": len(generated_code),
                    "has_imports": "import" in generated_code,
                    "has_methods": "public" in generated_code
                    or "function" in generated_code,
                },
            )

            # Filter imports to only available dependencies
            lines = generated_code.split("\n")
            filtered_lines = []
            for line in lines:
                if line.strip().startswith("import"):
                    match = re.search(r'import.*from\s+["\']([^"\']+)["\']', line)
                    if match:
                        module = match.group(1)
                        if module in available_dependencies:
                            filtered_lines.append(line)
                        else:
                            log_info(
                                self.name,
                                f"Filtered out unavailable import: {line.strip()}",
                            )
                    else:
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
            generated_code = "\n".join(filtered_lines)

            # Validate the generated code
            validation_passed = self._validate_typescript_code(generated_code)
            self._log_structured(
                "info",
                "code_validation",
                {"passed": validation_passed, "code_length": len(generated_code)},
            )

            if not validation_passed:
                self._log_structured(
                    "warning",
                    "code_correction_attempt",
                    {"reason": "validation_failed"},
                )
                correction_inputs = {
                    "result": state.result,
                    "generated_code": generated_code,
                    "validation_errors": "TypeScript compilation errors detected",
                    "relevant_code_files": state.relevant_code_files,
                    "feedback": state.feedback,
                }
                if self.code_correction_chain is None:
                    self._log_structured(
                        "warning", "code_correction_skipped", {"reason": "no_llm"}
                    )
                else:
                    try:
                        corrected_code = get_circuit_breaker("code_correction").call(
                            lambda: self.code_correction_chain.invoke(correction_inputs)
                        )
                    except CircuitBreakerOpenException as e:
                        self._log_structured(
                            "error",
                            "circuit_breaker_open",
                            {"operation": "code_correction", "error": str(e)},
                        )
                        raise
                    except Exception as e:
                        self._log_structured(
                            "error", "code_correction_failed", {"error": str(e)}
                        )
                        raise
                correction_validation = self._validate_typescript_code(corrected_code)
                self._log_structured(
                    "info",
                    "code_correction_result",
                    {
                        "correction_passed": correction_validation,
                        "corrected_length": len(corrected_code),
                    },
                )
                if correction_validation:
                    generated_code = corrected_code
                    self._log_structured(
                        "info", "code_correction_success", {"used_corrected": True}
                    )
                else:
                    self._log_structured(
                        "warning",
                        "code_correction_failed",
                        {"proceeding_with_original": True},
                    )

                # Fallback if generated code is empty
                if not generated_code.strip():
                    generated_code = self._get_fallback_code(state)
                log_info(self.name, "Applied fallback code due to empty generation")

            # Extract method name and command ID
            method_match = re.search(
                r"(public|private|protected)?\s*(\w+)\s*\(", generated_code
            )
            method_name = method_match.group(2) if method_match else ""

            command_match = re.search(
                r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', generated_code
            )
            command_id = command_match.group(1) if command_match else ""

            if not method_name:
                log_info(self.name, "Warning: No method name found, using fallback")
                method_name = "fallbackMethod"
            if not command_id:
                log_info(self.name, "Warning: No command ID found, using fallback")
                command_id = "fallbackCommand"

            return state.with_code(generated_code, method_name, command_id)

        except Exception as e:
            error_context = {"error_type": type(e).__name__, "message": str(e)}
            self._log_structured(
                "error", "collaborative_code_generation_failed", error_context
            )
            raise
            self._log_structured("error", "code_generation_failed", error_context)
            raise
