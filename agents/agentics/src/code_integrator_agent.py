import os
import logging
import re
import json
from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags, log_info

class CodeIntegratorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeIntegrator")
        # Configurable project root and file extensions
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.code_ext = os.getenv('CODE_FILE_EXTENSION', '.ts')
        self.test_ext = os.getenv('TEST_FILE_EXTENSION', '.test.ts')
        self.llm = llm_client
        self.logger = logging.getLogger("CodeIntegrator")
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with project root: {self.project_root}, code extension: {self.code_ext}, test extension: {self.test_ext}")

    def process(self, state: State) -> State:
        """
        Integrate generated code and tests into project files based on relevant code and test files.
        Updates existing files if present, otherwise creates new ones under src/ and src/__tests__/.
        """
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting code integration process")
        try:
            task_details = state['result']
            relevant_code_files = state.get('relevant_code_files', [])
            relevant_test_files = state.get('relevant_test_files', [])

            # If no relevant files or no generated code/tests, skip integration
            if (not relevant_code_files and not relevant_test_files) or \
               not state.get('generated_code') or not state.get('generated_tests'):
                log_info(self.logger, "No relevant files or no generated code/tests; skipping integration")
                return state
            log_info(self.logger, f"Task details received: {json.dumps(task_details, indent=2)}")
            log_info(self.logger, f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}")
            log_info(self.logger, f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}")

            # Extract code and tests (raw text)
            log_info(self.logger, "Extracting code and test content from generated output")
            code_content = self.extract_content(state['generated_code'])
            test_content = self.extract_content(state['generated_tests'])
            log_info(self.logger, f"Extracted code content length: {len(code_content)}")
            log_info(self.logger, f"Extracted code content: {code_content}")
            log_info(self.logger, f"Extracted test content length: {len(test_content)}")
            log_info(self.logger, f"Extracted test content: {test_content}")

            # Remove any lines containing "typescript" or "javascript"
            code_content = self.remove_unwanted_lines(code_content)
            test_content = self.remove_unwanted_lines(test_content)
            log_info(self.logger, f"Code content length after removing unwanted lines: {len(code_content)}")
            log_info(self.logger, f"Code content after removing unwanted lines: {code_content}")
            log_info(self.logger, f"Test content length after removing unwanted lines: {len(test_content)}")
            log_info(self.logger, f"Test content after removing unwanted lines: {test_content}")

            if not code_content or not test_content:
                self.logger.error("Code or test content is empty")
                raise ValueError("Code or test content is empty")

            if relevant_code_files or relevant_test_files:
                log_info(self.logger, "Processing existing files for update")
                # Update existing code files
                for file_data in relevant_code_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    log_info(self.logger, f"Processing code file: {rel_file_path}")
                    log_info(self.logger, f"Existing content length: {len(existing_content)}")
                    log_info(self.logger, f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_code_file(existing_content, code_content)
                    log_info(self.logger, f"Generated updated content length: {len(updated_content)}")
                    log_info(self.logger, f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
                # Update existing test files
                for file_data in relevant_test_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    log_info(self.logger, f"Processing test file: {rel_file_path}")
                    log_info(self.logger, f"Existing content length: {len(existing_content)}")
                    log_info(self.logger, f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_test_file(existing_content, test_content)
                    log_info(self.logger, f"Generated updated content length: {len(updated_content)}")
                    log_info(self.logger, f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
            else:
                log_info(self.logger, "No relevant files found; creating new files")
                task_description = task_details['description']
                task_title = task_details['title']
                filename = self.generate_filename(task_description, task_title)
                log_info(self.logger, f"Generated filename for new files: {filename}")

                new_code_file = os.path.join(self.project_root, 'src', f"{filename}{self.code_ext}")
                new_test_file = os.path.join(self.project_root, 'src', '__tests__', f"{filename}{self.test_ext}")
                log_info(self.logger, f"New code file path: {new_code_file}")
                log_info(self.logger, f"New test file path: {new_test_file}")

                self.create_file(new_code_file, code_content)
                self.create_file(new_test_file, test_content)
                state['relevant_code_files'] = [
                    {"file_path": os.path.relpath(new_code_file, self.project_root), "content": code_content}
                ]
                state['relevant_test_files'] = [
                    {"file_path": os.path.relpath(new_test_file, self.project_root), "content": test_content}
                ]
                log_info(self.logger, "Updated state with new file details")

            log_info(self.logger, "Code integration process completed successfully")
            log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state

        except Exception as e:
            self.logger.error(f"Error during code integration: {str(e)}")
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
        prompt = (
            "/think\n"
            f"You are integrating new TypeScript code into an existing Obsidian plugin file (`main{self.code_ext}`). "
            "The new code must be added to the `TimestampPlugin` class without modifying any existing code. "
            "Follow these instructions carefully:\n\n"
            "1. **Existing Code:**\n"
            f"{existing_content}\n\n"
            "2. **New Code to Integrate:**\n"
            f"{new_code}\n\n"
            "3. **Integration Rules:**\n"
            "   - Add new methods or properties to the `TimestampPlugin` class.\n"
            "   - Add new commands within the `onload` method using `this.addCommand`.\n"
            "   - Preserve all existing imports, methods, and commands.\n"
            "   - Add only necessary new imports that are not already present.\n"
            "   - Ensure the code is properly formatted and uses TypeScript syntax.\n"
            "   - Do not remove or alter any existing code.\n\n"
            "4. **Output Instructions:**\n"
            f"   - Your response must contain only the updated TypeScript code for `main{self.code_ext}`.\n"
            "   - The code should start with the import statements and end with the closing brace of the class.\n"
            "   - Do not include any comments, explanations, or additional text outside the code itself.\n"
            "   - Do not add any markers or comments indicating the start or end of the updated code.\n"
            "   - Do not include any lines containing the word 'typescript'.\n"
            "   - The response must consist solely of the code, with no additional lines or text before or after.\n"
            "   - The first line of your response should be a TypeScript import statement or the beginning of the class.\n\n"
            "5. **Output:**\n"
            f"   - Provide the complete updated TypeScript code for `main{self.code_ext}` with the new code integrated."
        )
        log_info(self.logger, f"Code integration prompt length: {len(prompt)}")
        log_info(self.logger, f"Code integration prompt: {prompt}")
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        updated_content = self.remove_unwanted_lines(clean_response.strip())
        log_info(self.logger, f"LLM response for code integration after removing unwanted lines, length: {len(updated_content)}")
        log_info(self.logger, f"Updated code content: {updated_content}")
        return updated_content

    def integrate_tests_manually(self, existing_content: str, new_tests: str) -> str:
        """
        Manually integrate new tests into the existing test file by handling imports and placing describe blocks at the top.
        """
        log_info(self.logger, "Starting manual test integration")
        existing_lines = existing_content.split('\n')
        new_test_lines = new_tests.split('\n')

        # Remove any lines containing "typescript" or "javascript" from new test content
        new_test_lines = [line for line in new_test_lines if 'typescript' not in line.lower() and 'javascript' not in line.lower()]
        log_info(self.logger, f"New test lines after removing unwanted lines: {len(new_test_lines)}")
        log_info(self.logger, f"Filtered new test lines: {new_test_lines}")

        # Extract import lines from new test content
        new_imports = [line for line in new_test_lines if line.strip().startswith('import')]
        log_info(self.logger, f"Extracted {len(new_imports)} import lines from new tests: {new_imports}")

        # Find the end of the import section in existing content
        import_end_idx = 0
        for i, line in enumerate(existing_lines):
            if not line.strip().startswith('import') and line.strip():
                import_end_idx = i
                break
        log_info(self.logger, f"Import section ends at index: {import_end_idx}")

        # Find unique new imports not already present
        existing_imports_set = set(line.strip() for line in existing_lines[:import_end_idx] if line.strip().startswith('import'))
        unique_new_imports = [imp for imp in new_imports if imp.strip() not in existing_imports_set]
        log_info(self.logger, f"Unique new imports to add: {len(unique_new_imports)}: {unique_new_imports}")

        # Insert new imports after existing imports if any
        if unique_new_imports:
            existing_lines = existing_lines[:import_end_idx] + unique_new_imports + [''] + existing_lines[import_end_idx:]

        # Find the start of the top-level describe block
        describe_start_idx = -1
        for i, line in enumerate(existing_lines):
            if line.strip().startswith("describe('TimestampPlugin', "):
                describe_start_idx = i
                break
        if describe_start_idx == -1:
            self.logger.error("Could not find describe('TimestampPlugin', block")
            raise ValueError("Could not find describe('TimestampPlugin', block")
        log_info(self.logger, f"Top-level describe block starts at index: {describe_start_idx}")

        # Find the position just after the opening of the describe block
        insert_idx = describe_start_idx + 1
        while insert_idx < len(existing_lines) and not existing_lines[insert_idx].strip():
            insert_idx += 1
        log_info(self.logger, f"Insert position for new tests: {insert_idx}")

        # Prepare new describe blocks with proper indentation (4 spaces)
        describe_blocks = [line for line in new_test_lines if not line.strip().startswith('import')]
        if describe_blocks:
            indented_describe_blocks = ['    ' + line for line in describe_blocks]
            # Insert a blank line and new tests at the top of the describe block
            existing_lines = (
                existing_lines[:insert_idx] +
                indented_describe_blocks +
                [''] +
                existing_lines[insert_idx:]
            )
            log_info(self.logger, f"Inserted {len(describe_blocks)} new test lines: {indented_describe_blocks}")

        updated_content = '\n'.join(existing_lines)
        log_info(self.logger, f"Updated test file content length: {len(updated_content)}")
        log_info(self.logger, f"Updated test file content: {updated_content}")
        return updated_content

    def remove_unwanted_lines(self, content: str) -> str:
        """Remove any line that contains the words 'typescript' or 'javascript' (case-insensitive)."""
        lines = content.split('\n')
        filtered_lines = [line for line in lines if 'typescript' not in line.lower() and 'javascript' not in line.lower()]
        removed_count = len(lines) - len(filtered_lines)
        log_info(self.logger, f"Removed {removed_count} lines containing 'typescript' or 'javascript'")
        filtered_content = '\n'.join(filtered_lines)
        log_info(self.logger, f"Filtered content: {filtered_content}")
        return filtered_content

    def generate_filename(self, task_description: str, task_title: str) -> str:
        """
        Generate a camelCase filename using LLM with fallback to sanitized title.
        """
        log_info(self.logger, "Generating filename")
        log_info(self.logger, f"Task description length: {len(task_description)}")
        log_info(self.logger, f"Task description: {task_description}")
        log_info(self.logger, f"Task title: {task_title}")

        prompt = (
            "/think\n"
            f"Provide only a single-word filename in camelCase for a TypeScript file "
            f"that implements the following feature: {task_description}. "
            f"Do not include additional text or explanation."
        )
        log_info(self.logger, f"Filename generation prompt length: {len(prompt)}")
        log_info(self.logger, f"Filename generation prompt: {prompt}")
        try:
            log_info(self.logger, "Invoking LLM for filename generation")
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            suggested_filename = clean_response.strip()
            log_info(self.logger, f"LLM suggested filename: {suggested_filename}")

            if re.match(r'^[a-zA-Z0-9_]+$', suggested_filename) and len(suggested_filename.split()) == 1:
                return suggested_filename
            else:
                self.logger.warning("LLM suggested an invalid filename")
                raise ValueError("LLM suggested an invalid filename")
        except Exception as e:
            self.logger.warning(f"LLM failed to suggest a valid filename: {str(e)}")
            sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', task_title).lower()
            filename = sanitized_title.split('_')[0] or "newFeature"
            log_info(self.logger, f"Using fallback filename: {filename}")
            return filename

    def extract_content(self, text: str) -> str:
        """Extract content directly from raw text since no markdown blocks are used."""
        log_info(self.logger, "Extracting content from raw text")
        log_info(self.logger, f"Input text length: {len(text)}")
        log_info(self.logger, f"Input text: {text}")
        clean_text = remove_thinking_tags(text)
        log_info(self.logger, f"Extracted content length: {len(clean_text)}")
        log_info(self.logger, f"Extracted content: {clean_text}")
        return clean_text.strip()

    def update_file(self, file_path: str, new_content: str):
        """Update an existing file with new content."""
        log_info(self.logger, f"Updating file: {file_path}")
        log_info(self.logger, f"New content length: {len(new_content)}")
        log_info(self.logger, f"New content: {new_content}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            log_info(self.logger, f"File updated successfully: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to update file {file_path}: {str(e)}")
            raise

    def create_file(self, file_path: str, content: str):
        """Create a new file with the given content."""
        log_info(self.logger, f"Creating new file: {file_path}")
        log_info(self.logger, f"Content length: {len(content)}")
        log_info(self.logger, f"Content: {content}")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            log_info(self.logger, f"File created successfully: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to create file {file_path}: {str(e)}")
            raise
