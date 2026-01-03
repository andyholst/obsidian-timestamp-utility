import os
import logging
import re
import json
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import read_file_tool, check_file_exists_tool, write_file_tool, npm_install_tool
from .state import State
from .utils import safe_json_dumps, remove_thinking_tags, log_info
from .prompts import ModularPrompts

class CodeIntegratorAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        super().__init__(llm_client, [read_file_tool, check_file_exists_tool, write_file_tool], "CodeIntegrator")
        # Configurable project root and file extensions
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.code_ext = os.getenv('CODE_FILE_EXTENSION', '.ts')
        self.test_ext = os.getenv('TEST_FILE_EXTENSION', '.test.ts')
        self.llm = llm_client
        self.monitor.info("agent_initialized", data={"project_root": self.project_root, "code_ext": self.code_ext, "test_ext": self.test_ext})

    def process(self, state: State) -> State:
        """
        Integrate generated code and tests into project files based on relevant code and test files.
        Updates existing files if present, otherwise creates new ones under src/ and src/__tests__/.
        """
        self.monitor.info(f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}", extra={'agent': self.name})
        self.monitor.info("Starting code integration process", extra={'agent': self.name})
        try:
            # Handle proposed JS dependencies first
            proposed_js_deps = state.get('proposed_js_deps', [])
            installed_deps = []
            if proposed_js_deps:
                self.monitor.info(f"Found {len(proposed_js_deps)} proposed JS deps: {proposed_js_deps}", extra={'agent': self.name})
                package_json_path = os.path.join(self.project_root, 'package.json')
                if check_file_exists_tool(package_json_path):
                    package_json_str = read_file_tool(package_json_path)
                    try:
                        package_json = json.loads(package_json_str)
                        dependencies = package_json.setdefault('dependencies', {})
                        added_deps = []
                        for pkg in proposed_js_deps:
                            if pkg not in dependencies:
                                dependencies[pkg] = '*'
                                added_deps.append(pkg)
                                self.monitor.info(f"Added {pkg} to package.json dependencies", extra={'agent': self.name})
                        if added_deps:
                            package_json['dependencies'] = dependencies
                            new_package_json_str = json.dumps(package_json, indent=2)
                            write_file_tool(package_json_path, new_package_json_str)
                            self.monitor.info(f"Updated package.json with new deps: {added_deps}", extra={'agent': self.name})
                        # Install the proposed deps
                        for pkg in proposed_js_deps:
                            try:
                                npm_install_tool(
                                    package_name=pkg,
                                    is_dev=False,
                                    save_exact=True,
                                    cwd=self.project_root
                                )
                                installed_deps.append(pkg)
                                self.monitor.info(f"Installed {pkg}", extra={'agent': self.name})
                            except Exception as e:
                                self.monitor.info(f"Failed to install {pkg}: {str(e)}", extra={'agent': self.name})
                    except json.JSONDecodeError as e:
                        self.monitor.info(f"Invalid package.json: {str(e)}", extra={'agent': self.name})
                    except Exception as e:
                        self.monitor.info(f"Error handling deps: {str(e)}", extra={'agent': self.name})
                else:
                    self.monitor.info(f"package.json not found at {package_json_path}, skipping deps install", extra={'agent': self.name})
                state['installed_deps'] = installed_deps
                self.monitor.info(f"Dependency handling complete. Installed: {installed_deps}", extra={'agent': self.name})

            refined_ticket = state.get('refined_ticket')
            if not refined_ticket:
                self.monitor.info("INTEGRATOR_NO_REFINED_TICKET_FALLBACK", {"agent": self.name, "keys": list(state.keys())})
                raise ValueError(f"No refined_ticket in state for integrator: {list(state.keys())}")
            task_details = refined_ticket
            relevant_code_files = state.get('relevant_code_files', [])
            relevant_test_files = state.get('relevant_test_files', [])

            # If no generated code/tests, skip integration
            if not state.get('generated_code') or not state.get('generated_tests'):
                self.monitor.info("No generated code/tests; skipping integration", extra={'agent': self.name})
                return state
            self.monitor.info(f"Task details received: {json.dumps(task_details, indent=2)}", extra={'agent': self.name})
            self.monitor.info(f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}", extra={'agent': self.name})
            self.monitor.info(f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}", extra={'agent': self.name})

            # Extract code and tests (raw text)
            self.monitor.info("Extracting code and test content from generated output", extra={'agent': self.name})
            code_content = self.extract_content(state['generated_code'])
            test_content = self.extract_content(state['generated_tests'])
            self.monitor.info(f"Extracted code content length: {len(code_content)}", extra={'agent': self.name})
            self.monitor.info(f"Extracted code content: {code_content}", extra={'agent': self.name})
            self.monitor.info(f"Extracted test content length: {len(test_content)}", extra={'agent': self.name})
            self.monitor.info(f"Extracted test content: {test_content}", extra={'agent': self.name})

            # Remove any lines containing "typescript" or "javascript"
            code_content = self.remove_unwanted_lines(code_content)
            test_content = self.remove_unwanted_lines(test_content)
            self.monitor.info(f"Code content length after removing unwanted lines: {len(code_content)}", extra={'agent': self.name})
            self.monitor.info(f"Code content after removing unwanted lines: {code_content}", extra={'agent': self.name})
            self.monitor.info(f"Test content length after removing unwanted lines: {len(test_content)}", extra={'agent': self.name})
            self.monitor.info(f"Test content after removing unwanted lines: {test_content}", extra={'agent': self.name})

            if not code_content or not test_content:
                self.monitor.error("content_empty", data={"type": "code_or_test"})
                raise ValueError("Code or test content is empty")

            if relevant_code_files or relevant_test_files:
                self.monitor.info("Processing existing files for update", extra={'agent': self.name})
                # Update existing code files
                for file_data in relevant_code_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    self.monitor.info(f"Processing code file: {rel_file_path}", extra={'agent': self.name})
                    self.monitor.info(f"Existing content length: {len(existing_content)}", extra={'agent': self.name})
                    self.monitor.info(f"Existing content: {existing_content}", extra={'agent': self.name})
                    updated_content = self.generate_updated_code_file(existing_content, code_content)
                    self.monitor.info(f"Generated updated content length: {len(updated_content)}", extra={'agent': self.name})
                    self.monitor.info(f"Generated updated content: {updated_content}", extra={'agent': self.name})
                    self.update_file(abs_file_path, updated_content)
                # Update existing test files
                for file_data in relevant_test_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    self.monitor.info(f"Processing test file: {rel_file_path}", extra={'agent': self.name})
                    self.monitor.info(f"Existing content length: {len(existing_content)}", extra={'agent': self.name})
                    self.monitor.info(f"Existing content: {existing_content}", extra={'agent': self.name})
                    updated_content = self.generate_updated_test_file(existing_content, test_content)
                    self.monitor.info(f"Generated updated content length: {len(updated_content)}", extra={'agent': self.name})
                    self.monitor.info(f"Generated updated content: {updated_content}", extra={'agent': self.name})
                    self.update_file(abs_file_path, updated_content)
            else:
                self.monitor.info("No relevant files found; creating new files", extra={'agent': self.name})
                task_description = task_details['description']
                task_title = task_details['title']
                filename = self.generate_filename(task_description, task_title)
                self.monitor.info(f"Generated filename for new files: {filename}", extra={'agent': self.name})

                new_code_file = os.path.join(self.project_root, 'src', f"{filename}{self.code_ext}")
                new_test_file = os.path.join(self.project_root, 'src', '__tests__', f"{filename}{self.test_ext}")
                self.monitor.info(f"New code file path: {new_code_file}", extra={'agent': self.name})
                self.monitor.info(f"New test file path: {new_test_file}", extra={'agent': self.name})

                self.create_file(new_code_file, code_content)
                self.create_file(new_test_file, test_content)
                state['relevant_code_files'] = [
                    {"file_path": os.path.relpath(new_code_file, self.project_root), "content": code_content}
                ]
                state['relevant_test_files'] = [
                    {"file_path": os.path.relpath(new_test_file, self.project_root), "content": test_content}
                ]
                self.monitor.info("Updated state with new file details", extra={'agent': self.name})

            self.monitor.info("Code integration process completed successfully", extra={'agent': self.name})
            self.monitor.info(f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}", extra={'agent': self.name})
            return state

        except Exception as e:
            self.monitor.error("integration_error", data={"error": str(e)})
            raise

    def generate_updated_code_file(self, existing_content: str, new_code: str) -> str:
        """Use LLM to integrate new code into the existing file, specifically into the TimestampPlugin class."""
        return self.integrate_code_with_llm(existing_content, new_code)

    def generate_updated_test_file(self, existing_content: str, new_tests: str) -> str:
        """Manually integrate new tests into the existing test file by handling imports and placing describe blocks at the top."""
        return self.integrate_tests_manually(existing_content, new_tests)

    def integrate_code_with_llm(self, existing_content: str, new_code: str) -> str:
        """
        Use LLM to generate updated code by integrating new code into the existing TimestampPlugin class.
        """
        tool_instructions = ModularPrompts.get_tool_instructions_for_code_integrator_agent()
        prompt = (
            "/think\n"
            f"You are integrating new TypeScript code into an existing Obsidian plugin file (`main{self.code_ext}`). "
            "The new code must be added to the `TimestampPlugin` class without modifying any existing code. "
            "NEVER modify existing original files like src/main.ts or src/__tests__/main.test.ts. Only integrate newly generated code into new or existing non-original files. "
            "Follow these instructions carefully:\n\n"
            "1. **Existing Code:**\n"
            f"{existing_content}\n\n"
            "2. **New Code to Integrate:**\n"
            f"{new_code}\n\n"
            "3. **Integration Rules:**\n"
            "   **CRITICAL: Integrate EXACT new code from section 2 VERBATIM into TimestampPlugin class (methods) or onload (commands). Do NOT change it.**\n"
            "   - Generate precise integrated code:\n"
            "   - Valid TS syntax, no unterminated template literals/strings.\n"
            "   - Obsidian API: TFile.extension (not .ext), mock Notice/Plugin as in __mocks__/obsidian.ts.\n"
            "     - Mock functions: use jest.fn().\n"
            "     - No unused variables/imports.\n"
            "     - Preserve existing code structure.\n"
            "   - Add new methods or properties to the `TimestampPlugin` class.\n"
            "   - Add new commands within the `onload` method using `this.addCommand`.\n"
            "   - Preserve all existing imports, methods, and commands.\n"
            "   - Add only necessary new imports that are not already present.\n"
            "   - Ensure the code is properly formatted and uses TypeScript syntax.\n"
            "   - Do not remove or alter any existing code.\n   3.5 **Repair TS Errors:** Fix editorCallback sig (Editor+ctx:MarkdownView|MarkdownFileInfo; cast view=ctx as MarkdownView; use 'editor'; no unused; string/number;\n\n"
            f"{tool_instructions}\n\n"
            "4. **Output Instructions:**\n"
            "   - Your response must contain only the updated TypeScript code for `main{self.code_ext}`.\n"
            "   - The code should start with the import statements and end with the closing brace of the class.\n"
            "   - Do not include any comments, explanations, or additional text outside the code itself.\n"
            "   - Do not add any markers or comments indicating the start or end of the updated code.\n"
            "   - Do not include any lines containing the word 'typescript'.\n"
            "   - The response must consist solely of the code, with no additional lines or text before or after.\n"
            "   - The first line of your response should be a TypeScript import statement or the beginning of the class.\n\n"
            "5. **Output:**\n"
            "   - Provide the complete updated TypeScript code for `main{self.code_ext}` with the new code integrated."
        )
        self.monitor.info(f"Code integration prompt length: {len(prompt)}", extra={'agent': self.name})
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        updated_content = self.remove_unwanted_lines(clean_response.strip())
        self.monitor.info(f"LLM response for code integration after removing unwanted lines, length: {len(updated_content)}", extra={'agent': self.name})
        self.monitor.info(f"Updated code content: {updated_content}", extra={'agent': self.name})
        return updated_content

    def integrate_tests_manually(self, existing_content: str, new_tests: str) -> str:
        """
        Manually integrate new tests into the existing test file by handling imports and placing describe blocks inside existing describe.
        Always use '../main' import for TimestampPlugin.
        """
        self.monitor.info("Starting manual test integration", extra={'agent': self.name})
        existing_lines = existing_content.split('\n')

        # Remove any lines containing "typescript" or "javascript" from new test content
        new_test_lines = new_tests.split('\n')
        new_test_lines = [line for line in new_test_lines if 'typescript' not in line.lower() and 'javascript' not in line.lower()]
        new_tests = '\n'.join(new_test_lines)
        self.monitor.info(f"New test lines after removing unwanted lines: {len(new_test_lines)}", extra={'agent': self.name})
        self.monitor.info(f"Filtered new test lines: {new_test_lines}", extra={'agent': self.name})

        # Strip outer describe('TimestampPlugin') if present to avoid duplicates
        match = re.search(r"describe\('TimestampPlugin',\s*\(\)\s*=>\s*\{(.*)\}\);\s*$", new_tests, re.DOTALL)
        if match:
            new_tests = match.group(1).strip()
            self.monitor.info("Stripped outer describe block from new tests", extra={'agent': self.name})

        # Extract import lines from new test content
        new_imports = [line for line in new_tests.split('\n') if line.strip().startswith('import')]
        self.monitor.info(f"Extracted {len(new_imports)} import lines from new tests: {new_imports}", extra={'agent': self.name})

        # Force TimestampPlugin import to '../main'
        for i, imp in enumerate(new_imports):
            if 'TimestampPlugin' in imp:
                new_imports[i] = "import TimestampPlugin from '../main';"

        # Find the end of the import section in existing content
        import_end_idx = 0
        for i, line in enumerate(existing_lines):
            if not line.strip().startswith('import') and line.strip():
                import_end_idx = i
                break
        self.monitor.info(f"Import section ends at index: {import_end_idx}", extra={'agent': self.name})

        # Find unique new imports not already present
        existing_imports_set = set(line.strip() for line in existing_lines[:import_end_idx] if line.strip().startswith('import'))
        unique_new_imports = [imp for imp in new_imports if imp.strip() not in existing_imports_set]
        self.monitor.info(f"Unique new imports to add: {len(unique_new_imports)}: {unique_new_imports}", extra={'agent': self.name})

        # Insert new imports after existing imports if any
        if unique_new_imports:
            existing_lines = existing_lines[:import_end_idx] + unique_new_imports + [''] + existing_lines[import_end_idx:]

        # Prepare new describe blocks (inner content)
        describe_blocks = [line for line in new_tests.split('\n') if not line.strip().startswith('import')]

        # Try to find the start of the top-level describe block
        describe_start_idx = -1
        for i, line in enumerate(existing_lines):
            if line.strip().startswith("describe('TimestampPlugin', "):
                describe_start_idx = i
                break

        if describe_start_idx != -1:
            self.monitor.info(f"Top-level describe block starts at index: {describe_start_idx}", extra={'agent': self.name})
            # Find the position just after the opening of the describe block
            insert_idx = describe_start_idx + 1
            while insert_idx < len(existing_lines) and not existing_lines[insert_idx].strip():
                insert_idx += 1
            self.monitor.info(f"Insert position for new tests: {insert_idx}", extra={'agent': self.name})

            # Prepare new describe blocks with proper indentation (4 spaces)
            if describe_blocks:
                indented_describe_blocks = ['    ' + line for line in describe_blocks]
                # Insert a blank line and new tests at the top of the describe block
                existing_lines = (
                    existing_lines[:insert_idx] +
                    indented_describe_blocks +
                    [''] +
                    existing_lines[insert_idx:]
                )
                self.monitor.info(f"Inserted {len(describe_blocks)} new test lines: {indented_describe_blocks}", extra={'agent': self.name})
        else:
            # No existing describe block, append new tests at the end
            if describe_blocks:
                existing_lines.extend([''] + describe_blocks)
                self.monitor.info(f"Appended {len(describe_blocks)} new test lines at the end", extra={'agent': self.name})

        updated_content = '\n'.join(existing_lines)
        self.monitor.info(f"Updated test file content length: {len(updated_content)}", extra={'agent': self.name})
        self.monitor.info(f"Updated test file content: {updated_content}", extra={'agent': self.name})
        return updated_content

    def remove_unwanted_lines(self, content: str) -> str:
        """Remove lines containing 'typescript'/'javascript' (case-insens.) or only '```'."""
        lines = content.split('\n')
        filtered_lines = [line for line in lines if 'typescript' not in line.lower() and 'javascript' not in line.lower() and line.strip() != '```']
        removed_count = len(lines) - len(filtered_lines)
        self.monitor.info(f"Removed {removed_count} unwanted lines (typescript/js/```)", extra={'agent': self.name})
        filtered_content = '\n'.join(filtered_lines)
        self.monitor.info(f"Filtered content: {filtered_content}", extra={'agent': self.name})
        return filtered_content

    def strip_markdown_blocks(self, content: str) -> str:
        """Remove markdown code blocks like ```typescript ... ```"""
        pattern = r'```(?:typescript|javascript|js)?\\s*\\n[\\s\\S]*?\\n```'
        cleaned = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        return cleaned

    def generate_filename(self, task_description: str, task_title: str) -> str:
        """
        Generate a camelCase filename using LLM with fallback to sanitized title.
        """
        self.monitor.info("Generating filename", extra={'agent': self.name})
        self.monitor.info(f"Task description length: {len(task_description)}", extra={'agent': self.name})
        self.monitor.info(f"Task description: {task_description}", extra={'agent': self.name})
        self.monitor.info(f"Task title: {task_title}", extra={'agent': self.name})

        prompt = (
            "/think\n"
            f"Provide only a single-word filename in camelCase for a TypeScript file "
            f"that implements the following feature: {task_description}. "
            f"Do not include additional text or explanation."
        )
        self.monitor.info(f"Filename generation prompt length: {len(prompt)}", extra={'agent': self.name})
        self.monitor.info(f"Filename generation prompt: {prompt}", extra={'agent': self.name})
        try:
            self.monitor.info("Invoking LLM for filename generation", extra={'agent': self.name})
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            suggested_filename = clean_response.strip()
            self.monitor.info(f"LLM suggested filename: {suggested_filename}", extra={'agent': self.name})


        except Exception as e:
            self.monitor.warning("filename_suggestion_failed", data={"error": str(e)})
            sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', task_title).lower()
            filename = sanitized_title.split('_')[0] or "newFeature"
            self.monitor.info(f"Using fallback filename: {filename}", extra={'agent': self.name})
            return filename

    def extract_content(self, text: str) -> str:
        """Extract code content: strip thinking tags, markdown blocks, parse JSON wrappers, trim."""
        log_info(self.name, "Extracting content from raw text")
        log_info(self.name, f"Input text length: {len(text)}")
        log_info(self.name, f"Input text: {text}")
        clean_text = remove_thinking_tags(text)
        clean_text = self.strip_markdown_blocks(clean_text)
        # Try to parse as JSON and extract 'tests' or 'code' if present
        try:
            parsed = json.loads(clean_text)
            if 'tests' in parsed:
                clean_text = parsed['tests']
            elif 'code' in parsed:
                clean_text = parsed['code']
        except json.JSONDecodeError:
            pass  # Use full content
        log_info(self.name, f"Extracted content length: {len(clean_text)}")
        log_info(self.name, f"Extracted content: {clean_text}")
        return clean_text.strip()

    def update_file(self, file_path: str, new_content: str):
        """Update an existing file with new content."""
        log_info(self.name, f"Updating file: {file_path}")
        log_info(self.name, f"New content length: {len(new_content)}")
        log_info(self.name, f"New content: {new_content}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            log_info(self.name, f"File updated successfully: {file_path}")
        except Exception as e:
            self.monitor.error("file_update_failed", data={"file_path": file_path, "error": str(e)})
            raise

    def create_file(self, file_path: str, content: str):
        """Create a new file with the given content."""
        log_info(self.name, f"Creating new file: {file_path}")
        log_info(self.name, f"Content length: {len(content)}")
        log_info(self.name, f"Content: {content}")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            log_info(self.name, f"File created successfully: {file_path}")
        except Exception as e:
            self.monitor.error("file_creation_failed", data={"file_path": file_path, "error": str(e)})
            raise

