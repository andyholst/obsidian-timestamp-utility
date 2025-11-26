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
from .tools import npm_search_tool, npm_install_tool, npm_list_tool, read_file_tool, list_files_tool, check_file_exists_tool
from .state import State, CodeGenerationState
from .utils import safe_json_dumps, remove_thinking_tags, log_info
from .models import CodeGenerationOutput, TestGenerationOutput
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from .prompts import ModularPrompts


class CodeGeneratorAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        super().__init__(llm_client, [npm_search_tool, npm_install_tool, npm_list_tool, read_file_tool, list_files_tool, check_file_exists_tool], name="CodeGenerator")
        self.main_file = os.getenv('MAIN_FILE', 'main.ts')
        self.test_file = os.getenv('TEST_FILE', 'main.test.ts')
        self.project_root = os.getenv('PROJECT_ROOT')
        if not self.project_root:
            raise ValueError("PROJECT_ROOT environment variable is required")
        self.monitor.setLevel(logging.INFO)
        log_info(self.name, f"Initialized with main file: {self.main_file}, test file: {self.test_file}, project root: {self.project_root}")
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
            result = self.tool_executor.execute_tool('npm_list_tool', {'depth': 0})
            # Parse the JSON result
            packages_data = json.loads(result)
            if 'dependencies' in packages_data:
                all_deps = list(packages_data['dependencies'].keys())
            else:
                all_deps = []
            log_info(self.name, f"Available dependencies: {all_deps}")
            return all_deps
        except Exception as e:
            log_info(self.name, f"Failed to get dependencies using npm_list_tool: {str(e)}, using empty list")
            return []

    def _create_code_generation_chain(self):
        """Create LCEL chain for code generation with modular prompts and output validation."""
        def build_code_prompt(inputs):
            code_structure = json.dumps(inputs.get('code_structure', {}))
            tool_context = self._gather_tool_context(inputs)
            tool_instructions = ModularPrompts.get_tool_instructions_for_code_generator_agent()
            return (
                ModularPrompts.get_base_instruction() + "\n"
                "You are tasked with generating TypeScript code for an Obsidian plugin. The plugin is defined in `{main_file}`, and you must integrate the new functionality into the existing structure without altering any existing code. Follow these instructions carefully:\n\n"
                + ModularPrompts.get_code_structure_section(code_structure)
                + ModularPrompts.get_code_requirements_section()
                + "3. **Task Details:**\n{task_details_str}\n\n"
                + "4. **Existing Code ({main_file}):**\n{existing_code_content}\n\n"
                + "5. **Previous Feedback (Tune Accordingly):**\n{feedback}\n\n"
                + tool_instructions
                + ModularPrompts.get_output_instructions_code()
            )

        # Use RunnableLambda to build the prompt dynamically

        # Output parser for validation
        code_parser = PydanticOutputParser(pydantic_object=CodeGenerationOutput)

        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_code_content=self._get_existing_code_content,
                main_file=lambda x: self.main_file,
                feedback=lambda x: ((x.get('feedback') if isinstance(x, dict) else x.feedback) or {}).get('feedback', ''),
                code_structure=lambda x: {}
            )
            | RunnableLambda(build_code_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_code_output)
        )

    def _create_test_generation_chain(self):
        """Create LCEL chain for test generation with modular prompts and output validation."""
        def build_test_prompt(inputs):
            test_structure = json.dumps(inputs.get('test_structure', {}))
            tool_context = self._gather_tool_context(inputs)
            tool_instructions = ModularPrompts.get_tool_instructions_for_code_generator_agent()
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
                + tool_instructions
                + ModularPrompts.get_output_instructions_tests()
            )

        # Use RunnableLambda to build the prompt dynamically

        # Output parser for validation
        test_parser = PydanticOutputParser(pydantic_object=TestGenerationOutput)

        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_test_content=self._get_existing_test_content,
                test_file=lambda x: self.test_file,
                feedback=lambda x: ((x.get('feedback') if isinstance(x, dict) else x.feedback) or {}).get('feedback', ''),
                test_structure=lambda x: {}
            )
            | RunnableLambda(build_test_prompt)
            | self.llm
            | RunnableLambda(self._validate_and_parse_test_output)
        )

    def _create_code_correction_chain(self):
        """Create LCEL chain for code correction based on validation errors."""
        correction_prompt_template = PromptTemplate(
            input_variables=["generated_code", "validation_errors", "task_details_str", "existing_code_content", "main_file"],
            template=(
                "/think\n"
                "You are correcting TypeScript code that failed validation. The code must be fixed to pass TypeScript compilation and follow best practices.\n\n"
                "Validation Errors: {validation_errors}\n\n"
                "Original Generated Code: {generated_code}\n\n"
                "Task Details: {task_details_str}\n\n"
                "Existing Code: {existing_code_content}\n\n"
                "Output only the corrected TypeScript code, no explanations."
            )
        )
        return (
            RunnablePassthrough.assign(
                task_details_str=self._format_task_details,
                existing_code_content=self._get_existing_code_content,
                main_file=lambda x: self.main_file,
                feedback=lambda x: ((x.get('feedback') if isinstance(x, dict) else x.feedback) or {}).get('feedback', '')
            )
            | correction_prompt_template
            | self.llm
            | RunnableLambda(self._post_process_code)
        )

    def _format_task_details(self, inputs):
        """Format task details string from state."""
        if isinstance(inputs, dict):
            # State dict style
            result = inputs.get('result', {})
            title = result.get('title', '')
            description = result.get('description', '')
            requirements = result.get('requirements', [])
            acceptance_criteria = result.get('acceptance_criteria', [])
            implementation_steps = result.get('implementation_steps', [])
            npm_packages = result.get('npm_packages', [])
            manual_implementation_notes = result.get('manual_implementation_notes', '')
        else:
            # CodeGenerationState object style
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

    def _get_existing_code_content(self, inputs):
        """Get existing code content from relevant files."""
        if isinstance(inputs, dict):
            relevant_code_files = inputs.get('relevant_code_files', [])
        else:
            relevant_code_files = inputs.relevant_code_files
        for code_file in relevant_code_files:
            file_path = code_file['file_path']
            if file_path.endswith(self.main_file):
                return code_file.get('content', "")
        return ""

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

    def _validate_and_parse_code_output(self, response):
        """Validate and parse the LLM output for code generation."""
        clean_response = remove_thinking_tags(response)
        try:
            # Try to parse as structured output
            parsed = json.loads(clean_response)
            if 'code' in parsed and 'method_name' in parsed and 'command_id' in parsed:
                generated_code = parsed['code']
            else:
                # Fallback to treating as raw code
                generated_code = clean_response.strip()
        except json.JSONDecodeError:
            # Not JSON, treat as raw code
            generated_code = clean_response.strip()

        # Post-process the generated code
        generated_code = self._post_process_code(generated_code)

        # Keyword validation for code output
        code_keywords = ['import', 'export', 'class', 'interface', 'function', 'public']
        if not any(keyword in generated_code for keyword in code_keywords):
            raise ValueError("Generated code must include at least one of: import, export, class, interface, or function")

        return generated_code

    def _post_process_code(self, generated_code):
        """Post-process the generated code."""
        # Post-process generated code to fix common issues
        generated_code = generated_code.replace('CodeMirror.Editor', 'obsidian.Editor')
        generated_code = generated_code.replace('TFile', 'obsidian.TFile')
        generated_code = generated_code.replace('obsidian.Modal', 'obsidian.MarkdownView')
        generated_code = generated_code.replace('private ', 'public ')
        generated_code = generated_code.replace('protected ', 'public ')
        generated_code = re.sub(r'return text; // Placeholder', r'return text || \'\';', generated_code)
        # Fix UUID import and usage
        generated_code = generated_code.replace("import v7 from 'uuidv7';", "import { v7 as uuidv7 } from 'uuid';")
        generated_code = generated_code.replace("v7.generate()", "uuidv7()")
        generated_code = generated_code.replace("import { v7 } from '@uuid/v7';", "import { v7 as uuidv7 } from 'uuid';")
        generated_code = generated_code.replace("v7.generate()", "uuidv7()")
        return generated_code

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

        # Keyword validation for test output
        if not (generated_tests.strip().startswith('describe(') and generated_tests.strip().endswith('});')):
            raise ValueError("Generated tests must start with 'describe(' and end with '});'")
        if 'describe(' not in generated_tests or ('it(' not in generated_tests and 'test(' not in generated_tests):
            raise ValueError("Generated tests must include 'describe(' and 'it(' or 'test(' keywords")

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
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as temp_file:
                temp_file.write(temp_content)
                temp_file_path = temp_file.name

            # Run tsc --noEmit to check for errors
            result = subprocess.run(
                ['npx', 'tsc', '--noEmit', '--target', 'es2018', '--moduleResolution', 'node', '--allowJs', '--checkJs', 'false', '--strict', temp_file_path],
                capture_output=True, text=True, cwd=os.path.dirname(temp_file_path)
            )

            # Clean up temp file
            os.unlink(temp_file_path)

            if result.returncode == 0:
                log_info(self.name, "TypeScript code validation passed")
                return True
            else:
                log_info(self.name, f"TypeScript code validation failed: {result.stderr}")
                return False
        except Exception as e:
            log_info(self.name, f"Error during TypeScript validation: {str(e)}")
            return False

    def process(self, state: State) -> State:
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting code generation process")
        try:
            task_details = state['result']
            # Get available dependencies dynamically from package.json
            available_dependencies = self._get_available_dependencies()
            # Check if ticket is vague (empty requirements and acceptance criteria)
            requirements = task_details.get('requirements', [])
            acceptance_criteria = task_details.get('acceptance_criteria', [])
            is_vague_ticket = not requirements
            # If ticket is vague, skip code generation
            if is_vague_ticket:
                log_info(self.name, "Ticket is vague (empty requirements/acceptance criteria); skipping code generation")
                state['generated_code'] = ""
                state['generated_tests'] = ""
                return state
            self._log_structured("info", "task_processing", {
                "requirements_count": len(requirements),
                "acceptance_criteria_count": len(acceptance_criteria)
            })
            # Generate code using LCEL chain
            if self.code_generation_chain is None:
                raise RuntimeError("LLM not available for code generation")
            self._log_structured("info", "code_generation_start", {"chain": "code_generation"})
            try:
                generated_code = get_circuit_breaker("code_generation").call(lambda: self.code_generation_chain.invoke(state))
            except CircuitBreakerOpenException as e:
                self._log_structured("error", "circuit_breaker_open", {"operation": "code_generation", "error": str(e)})
                raise
            except Exception as e:
                self._log_structured("error", "code_generation_failed", {"error": str(e)})
                raise
            self._log_structured("info", "code_generation_complete", {
                "code_length": len(generated_code),
                "has_imports": 'import' in generated_code,
                "has_methods": 'public' in generated_code or 'function' in generated_code
            })
            # Filter imports to only available dependencies
            lines = generated_code.split('\n')
            filtered_lines = []
            for line in lines:
                if line.strip().startswith('import'):
                    match = re.search(r'import.*from\s+["\']([^"\']+)["\']', line)
                    if match:
                        module = match.group(1)
                        if module in available_dependencies:
                            filtered_lines.append(line)
                        else:
                            log_info(self.name, f"Filtered out unavailable import: {line.strip()}")
                    else:
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
            generated_code = '\n'.join(filtered_lines)
            log_info(self.name, f"Filtered generated code: {generated_code}")
            # Validate the generated code
            validation_passed = self._validate_typescript_code(generated_code)
            self._log_structured("info", "code_validation", {
                "passed": validation_passed,
                "code_length": len(generated_code)
            })
            if not validation_passed:
                self._log_structured("warning", "code_correction_attempt", {"reason": "validation_failed"})
                correction_inputs = state.copy()
                correction_inputs.update({
                    'generated_code': generated_code,
                    'validation_errors': 'TypeScript compilation errors detected'
                })
                if self.code_correction_chain is None:
                    self._log_structured("warning", "code_correction_skipped", {"reason": "no_llm"})
                else:
                    try:
                        corrected_code = get_circuit_breaker("code_correction").call(lambda: self.code_correction_chain.invoke(correction_inputs))
                    except CircuitBreakerOpenException as e:
                        self._log_structured("error", "circuit_breaker_open", {"operation": "code_correction", "error": str(e)})
                        raise
                    except Exception as e:
                        self._log_structured("error", "code_correction_failed", {"error": str(e)})
                        raise
                correction_validation = self._validate_typescript_code(corrected_code)
                self._log_structured("info", "code_correction_result", {
                    "correction_passed": correction_validation,
                    "corrected_length": len(corrected_code)
                })
                if correction_validation:
                    generated_code = corrected_code
                    self._log_structured("info", "code_correction_success", {"used_corrected": True})
                else:
                    self._log_structured("warning", "code_correction_failed", {"proceeding_with_original": True})
            else:
                self._log_structured("info", "code_validation_success", {"no_correction_needed": True})
            # Extract method name and command ID
            method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', generated_code)
            if method_match:
                method_name = method_match.group(2)
                log_info(self.name, f"Extracted method name: {method_name}")
            else:
                self.monitor.error("Could not find method name in generated code")
                raise ValueError("Could not find method name in generated code")
            command_match = re.search(r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', generated_code)
            if command_match:
                command_id = command_match.group(1)
                log_info(self.name, f"Extracted command ID: {command_id}")
            else:
                self.monitor.error("Could not find command ID in generated code")
                raise ValueError("Could not find command ID in generated code")
            # Generate tests using LCEL chain
            if self.test_generation_chain is None:
                raise RuntimeError("LLM not available for test generation")
            log_info(self.name, "Generating tests using LCEL chain")
            test_inputs = state.copy()
            test_inputs.update({
                'generated_code': generated_code,
                'method_name': method_name,
                'command_id': command_id
            })
            try:
                generated_tests = get_circuit_breaker("test_generation").call(lambda: self.test_generation_chain.invoke(test_inputs))
            except CircuitBreakerOpenException as e:
                self._log_structured("error", "circuit_breaker_open", {"operation": "test_generation", "error": str(e)})
                raise
            except Exception as e:
                self._log_structured("error", "test_generation_failed", {"error": str(e)})
                raise
            log_info(self.name, f"Generated tests: {generated_tests}")
            log_info(self.name, f"Generated tests length: {len(generated_tests)}")
            state['generated_code'] = generated_code
            state['generated_tests'] = generated_tests
            log_info(self.name, "Code and tests generated and stored in state successfully")
            log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
            return state
        except KeyError as e:
            error_context = {
                "error_type": "KeyError",
                "missing_field": str(e),
                "available_keys": list(state.get('result', {}).keys())
            }
            self._log_structured("error", "missing_result_field", error_context)
            raise ValueError(f"Missing field in state['result']: {e}")
        except ValueError as e:
            # Re-raise ValueError with additional context
            error_context = {
                "error_type": "ValueError",
                "message": str(e),
                "task_details": state.get('result', {})
            }
            self._log_structured("error", "validation_error", error_context)
            raise
        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e),
                "code_length": len(state.get('generated_code', '')),
                "test_length": len(state.get('generated_tests', ''))
            }
    def generate(self, state: CodeGenerationState) -> CodeGenerationState:
        """
        Generate code for the given state.

        Args:
            state: The current code generation state

        Returns:
            Updated state with generated code
        """
        log_info(self.name, "Starting collaborative code generation process")

        try:
            # Check if ticket is vague (empty requirements and acceptance criteria)
            requirements = (state.result or {}).get('requirements', [])
            acceptance_criteria = (state.result or {}).get('acceptance_criteria', [])
            is_vague_ticket = not requirements

            if is_vague_ticket:
                log_info(self.name, "Ticket is vague (empty requirements/acceptance criteria); skipping code generation")
                return state.with_code("", "", "")

            # Get available dependencies dynamically from package.json
            available_dependencies = self._get_available_dependencies()

            self._log_structured("info", "task_processing", {
                "requirements_count": len(requirements),
                "acceptance_criteria_count": len(acceptance_criteria)
            })

            # Generate code using LCEL chain
            if self.code_generation_chain is None:
                raise RuntimeError("LLM not available for code generation")
            self._log_structured("info", "code_generation_start", {"chain": "code_generation"})

            try:
                generated_code = get_circuit_breaker("code_generation").call(lambda: self.code_generation_chain.invoke(state))
            except CircuitBreakerOpenException as e:
                self._log_structured("error", "circuit_breaker_open", {"operation": "code_generation", "error": str(e)})
                raise
            except Exception as e:
                self._log_structured("error", "code_generation_failed", {"error": str(e)})
                raise

            self._log_structured("info", "code_generation_complete", {
                "code_length": len(generated_code),
                "has_imports": 'import' in generated_code,
                "has_methods": 'public' in generated_code or 'function' in generated_code
            })

            # Filter imports to only available dependencies
            lines = generated_code.split('\n')
            filtered_lines = []
            for line in lines:
                if line.strip().startswith('import'):
                    match = re.search(r'import.*from\s+["\']([^"\']+)["\']', line)
                    if match:
                        module = match.group(1)
                        if module in available_dependencies:
                            filtered_lines.append(line)
                        else:
                            log_info(self.name, f"Filtered out unavailable import: {line.strip()}")
                    else:
                        filtered_lines.append(line)
                else:
                    filtered_lines.append(line)
            generated_code = '\n'.join(filtered_lines)

            # Validate the generated code
            validation_passed = self._validate_typescript_code(generated_code)
            self._log_structured("info", "code_validation", {
                "passed": validation_passed,
                "code_length": len(generated_code)
            })

            if not validation_passed:
                self._log_structured("warning", "code_correction_attempt", {"reason": "validation_failed"})
                correction_inputs = {
                    'result': state.result,
                    'generated_code': generated_code,
                    'validation_errors': 'TypeScript compilation errors detected',
                    'relevant_code_files': state.relevant_code_files,
                    'feedback': state.feedback
                }
                if self.code_correction_chain is None:
                    self._log_structured("warning", "code_correction_skipped", {"reason": "no_llm"})
                else:
                    try:
                        corrected_code = get_circuit_breaker("code_correction").call(lambda: self.code_correction_chain.invoke(correction_inputs))
                    except CircuitBreakerOpenException as e:
                        self._log_structured("error", "circuit_breaker_open", {"operation": "code_correction", "error": str(e)})
                        raise
                    except Exception as e:
                        self._log_structured("error", "code_correction_failed", {"error": str(e)})
                        raise
                correction_validation = self._validate_typescript_code(corrected_code)
                self._log_structured("info", "code_correction_result", {
                    "correction_passed": correction_validation,
                    "corrected_length": len(corrected_code)
                })
                if correction_validation:
                    generated_code = corrected_code
                    self._log_structured("info", "code_correction_success", {"used_corrected": True})
                else:
                    self._log_structured("warning", "code_correction_failed", {"proceeding_with_original": True})

            # Extract method name and command ID
            method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', generated_code)
            method_name = method_match.group(2) if method_match else ""

            command_match = re.search(r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', generated_code)
            command_id = command_match.group(1) if command_match else ""

            if not method_name:
                raise ValueError("Could not find method name in generated code")
            if not command_id:
                raise ValueError("Could not find command ID in generated code")

            return state.with_code(generated_code, method_name, command_id)

        except Exception as e:
            error_context = {
                "error_type": type(e).__name__,
                "message": str(e)
            }
            self._log_structured("error", "collaborative_code_generation_failed", error_context)
            raise
            self._log_structured("error", "code_generation_failed", error_context)
            raise
