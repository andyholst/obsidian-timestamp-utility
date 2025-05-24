import os
import logging
import re
import json
from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags

class CodeIntegratorAgent(BaseAgent):
    project_root = '/project'

    def __init__(self, llm_client):
        super().__init__("CodeIntegrator")
        self.llm = llm_client
        self.logger = logging.getLogger("CodeIntegrator")
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        """
        Integrate generated code and tests into project files based on relevant code and test files.
        Updates existing files if present, otherwise creates new ones under src/ and src/__tests__/.
        """
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting code integration process")
        try:
            task_details = state['result']
            relevant_code_files = state.get('relevant_code_files', [])
            relevant_test_files = state.get('relevant_test_files', [])
            self.logger.info(f"Task details received: {task_details}")
            self.logger.info(f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}")
            self.logger.info(f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}")

            # Extract code and tests (now raw text)
            self.logger.info("Extracting code and test content from generated output")
            code_content = self.extract_content(state['generated_code'])
            test_content = self.extract_content(state['generated_tests'])
            self.logger.info(f"Extracted code content: {code_content}")
            self.logger.info(f"Extracted test content: {test_content}")

            if not code_content or not test_content:
                self.logger.error("Code or test content is empty")
                raise ValueError("Code or test content is empty")

            if relevant_code_files or relevant_test_files:
                self.logger.info("Processing existing files for update")
                # Update existing code files
                for file_data in relevant_code_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    self.logger.info(f"Processing code file: {rel_file_path}")
                    self.logger.info(f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_code_file(existing_content, code_content)
                    self.logger.info(f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
                # Update existing test files
                for file_data in relevant_test_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    self.logger.info(f"Processing test file: {rel_file_path}")
                    self.logger.info(f"Existing content: {existing_content}")
                    updated_content = self.generate_updated_test_file(existing_content, test_content, task_details)
                    self.logger.info(f"Generated updated content: {updated_content}")
                    self.update_file(abs_file_path, updated_content)
            else:
                self.logger.info("No relevant files found; creating new files")
                task_description = task_details['description']
                task_title = task_details['title']
                filename = self.generate_filename(task_description, task_title)
                self.logger.info(f"Generated filename for new files: {filename}")

                new_code_file = os.path.join(self.project_root, 'src', f"{filename}.ts")
                new_test_file = os.path.join(self.project_root, 'src', '__tests__', f"{filename}.test.ts")
                self.logger.info(f"New code file path: {new_code_file}")
                self.logger.info(f"New test file path: {new_test_file}")

                self.create_file(new_code_file, code_content)
                self.create_file(new_test_file, test_content)
                state['relevant_code_files'] = [
                    {"file_path": os.path.relpath(new_code_file, self.project_root), "content": code_content}
                ]
                state['relevant_test_files'] = [
                    {"file_path": os.path.relpath(new_test_file, self.project_root), "content": test_content}
                ]
                self.logger.info("Updated state with new file details")

            self.logger.info("Code integration process completed successfully")
            self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state

        except Exception as e:
            self.logger.error(f"Error during code integration: {str(e)}")
            raise

    def generate_updated_code_file(self, existing_content: str, new_code: str) -> str:
        """
        Use LLM to integrate new code into the existing TypeScript file, specifically into the TimestampPlugin class.
        """
        return self.integrate_code_with_llm(existing_content, new_code)

    def generate_updated_test_file(self, existing_content: str, new_tests: str, task_details: dict) -> str:
        """
        Use LLM to integrate new tests into the existing TypeScript test file, handling imports and describe blocks.
        """
        task_title = task_details['title']
        return self.integrate_tests_with_llm(existing_content, new_tests, task_title)

    def integrate_code_with_llm(self, existing_content: str, new_code: str) -> str:
        """
        Use LLM to generate updated code by integrating new code into the existing TimestampPlugin class.
        """
        prompt = (
            "Here is the existing TypeScript code for an Obsidian plugin:\n\n"
            f"{existing_content}\n\n"
            "And here is the new code to integrate into the `TimestampPlugin` class:\n\n"
            f"{new_code}\n\n"
            "Please provide the updated TypeScript code with the new code integrated appropriately into the `TimestampPlugin` class. "
            "Ensure that any new commands are added within the `onload` method, and any new methods are added as class methods. "
            "Preserve all existing code and maintain proper TypeScript syntax. "
            "Handle import statements correctly, avoiding duplicates. "
            "Do not add any explanations or comments outside of what's necessary. "
            "Return only the updated TypeScript code."
        )
        self.logger.info(f"Code integration prompt: {prompt}")
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        updated_content = clean_response.strip()
        self.logger.info(f"LLM response for code integration: {updated_content}")
        return updated_content

    def integrate_tests_with_llm(self, existing_content: str, new_tests: str, task_title: str) -> str:
        """
        Use LLM to integrate new tests into the existing TypeScript test file, ensuring imports are consolidated
        and new describe blocks are appended at the end of the existing TimestampPlugin suite without modifying existing code.
        """
        prompt = (
            f"Here is the existing TypeScript test file for the Obsidian TimestampPlugin:\n\n"
            f"{existing_content}\n\n"
            f"And here are the new tests to integrate for the task: {task_title}\n\n"
            f"{new_tests}\n\n"
            "Integrate the new tests into the existing test file according to these strict instructions:\n\n"
            "1. **Preserve Existing Code Completely**: Do not modify, remove, reorder, or reformat any part of the existing test file. "
            "This includes all imports, mock definitions, utility functions (e.g., `parseDateString`, `generateDateRange`), "
            "the `beforeEach` block, and all existing `describe` and `test` blocks within `describe('TimestampPlugin', ...)`.\n\n"
            "2. **Add New Imports Only**: At the top of the file, append only the import statements from the new tests that are not already present. "
            "Do not duplicate existing imports (e.g., `import TimestampPlugin from '../main';` or `import * as obsidian from 'obsidian';`). "
            "If an import already exists, use it as is and do not add it again.\n\n"
            "3. **Append New Describe Blocks**: Inside the existing `describe('TimestampPlugin', () => {{ ... }})` block, "
            "append only the two new `describe` blocks from the new tests. "
            "Place them immediately before the closing brace `}}` of the `describe('TimestampPlugin', ...)` block, "
            "after all existing `describe` and `test` blocks. Do not add any other code from the new tests.\n\n"
            "4. **Do Not Add Redundant Structures**: Do not include additional `describe('TimestampPlugin', ...)` blocks, `beforeEach` blocks, "
            "or any other test setup code from the new tests. Only the two inner `describe` blocks are to be appended.\n\n"
            "5. **Maintain Exact Structure**: Ensure the output retains the exact structure of the existing file, with only the new imports "
            "at the top and the two new `describe` blocks appended as specified. Do not alter indentation, spacing, or formatting of existing code.\n\n"
            "6. **Ensure Valid Jest Syntax**: The resulting file must be a valid Jest test file with correct TypeScript syntax.\n\n"
            "7. **No Extra Text**: Do not add comments, explanations, or any text outside the updated test code itself.\n\n"
            "Return only the updated TypeScript test code."
        )
        self.logger.info(f"Test integration prompt: {prompt}")
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        updated_content = clean_response.strip()
        self.logger.info(f"LLM response for test integration: {updated_content}")
        return updated_content

    def generate_filename(self, task_description: str, task_title: str) -> str:
        """
        Generate a camelCase filename using LLM with fallback to sanitized title.
        """
        self.logger.info("Generating filename")
        self.logger.info(f"Task description: {task_description}")
        self.logger.info(f"Task title: {task_title}")

        prompt = (
            "/think\n"
            f"Provide only a single-word filename in camelCase for a TypeScript file "
            f"that implements the following feature: {task_description}. "
            f"Do not include additional text or explanation."
        )
        try:
            self.logger.info("Invoking LLM for filename generation")
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            suggested_filename = clean_response.strip()
            self.logger.info(f"LLM suggested filename: {suggested_filename}")

            if re.match(r'^[a-zA-Z0-9_]+$', suggested_filename) and len(suggested_filename.split()) == 1:
                return suggested_filename
            else:
                raise ValueError("LLM suggested an invalid filename")
        except Exception as e:
            self.logger.warning(f"LLM failed to suggest a valid filename: {str(e)}")
            sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', task_title).lower()
            filename = sanitized_title.split('_')[0] or "newFeature"
            self.logger.info(f"Using fallback filename: {filename}")
            return filename

    def extract_content(self, text: str) -> str:
        """
        Extract content directly from raw text since no markdown blocks are used.
        """
        self.logger.info("Extracting content from raw text")
        self.logger.info(f"Input text: {text}")
        clean_text = remove_thinking_tags(text)
        self.logger.info(f"Extracted content: {clean_text}")
        return clean_text.strip()

    def update_file(self, file_path: str, new_content: str):
        """
        Update an existing file with new content.
        """
        self.logger.info(f"Updating file: {file_path}")
        self.logger.info(f"New content to write: {new_content}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            self.logger.info(f"File updated successfully: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to update file {file_path}: {str(e)}")
            raise

    def create_file(self, file_path: str, content: str):
        """
        Create a new file with the given content.
        """
        self.logger.info(f"Creating new file: {file_path}")
        self.logger.info(f"Content to write: {content}")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"File created successfully: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to create file {file_path}: {str(e)}")
            raise
