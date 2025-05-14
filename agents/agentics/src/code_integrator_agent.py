import os
import logging
import re
from .base_agent import BaseAgent
from .state import State

class CodeIntegratorAgent(BaseAgent):
    project_root = '/project'

    def __init__(self, llm_client):
        super().__init__("CodeIntegrator")
        self.llm = llm_client
        self.logger = logging.getLogger("CodeIntegrator")

    def process(self, state: State) -> State:
        """
        Integrate generated code and tests into the project files based on relevant files.
        If relevant files exist, update them with new content, preserving existing code and sorting alphanumerically.
        If no relevant files are found, create new files with LLM-generated filenames.
        """
        try:
            task_details = state['result']  # Use state['result'] for task details
            relevant_files = state.get('relevant_files', [])

            # Extract code and tests from markdown blocks or use the entire response
            code_content = self.extract_content(state['generated_code'])
            test_content = self.extract_content(state['generated_tests'])

            if not code_content or not test_content:
                raise ValueError("Failed to extract code or tests from generated content")

            if relevant_files:
                # Update existing files with new content
                for file_data in relevant_files:
                    rel_file_path = file_data['file_path']
                    abs_file_path = os.path.join(self.project_root, rel_file_path)
                    existing_content = file_data['content']
                    if 'test' in rel_file_path.lower():
                        updated_content = self.generate_updated_test_file(existing_content, test_content, task_details)
                    else:
                        updated_content = self.generate_updated_code_file(existing_content, code_content, task_details)
                    self.update_file(abs_file_path, updated_content)
            else:
                # Generate filename using LLM based on task description with fallback to task title
                task_description = task_details['description']
                task_title = task_details['title']
                filename = self.generate_filename(task_description, task_title)
                # Sort new code and tests before writing to ensure alphabetical order
                sorted_code = self.sort_code_content(code_content, task_details, is_test=False)
                sorted_tests = self.sort_code_content(test_content, task_details, is_test=True)
                # Create new files with sorted content
                new_code_file = os.path.join(self.project_root, 'src', f"{filename}.ts")
                new_test_file = os.path.join(self.project_root, 'tests', f"{filename}.test.ts")
                self.create_file(new_code_file, sorted_code)
                self.create_file(new_test_file, sorted_tests)
                # Store relative paths in state for consistency
                state['relevant_files'] = [
                    {"file_path": os.path.relpath(new_code_file, self.project_root), "content": sorted_code},
                    {"file_path": os.path.relpath(new_test_file, self.project_root), "content": sorted_tests}
                ]

            self.logger.info("Code integration completed successfully")
            return state

        except Exception as e:
            self.logger.error(f"Error in CodeIntegratorAgent: {e}")
            raise

    def generate_updated_code_file(self, existing_content: str, new_code: str, task_details: dict) -> str:
        """
        Use LLM to integrate new code into an existing TypeScript file, ensuring imports, functions,
        methods, and classes are sorted alphanumerically and follow TypeScript best practices.
        """
        prompt = (
            f"Given the following existing TypeScript code file:\n"
            f"```\n{existing_content}\n```\n\n"
            f"And the following new code to integrate:\n"
            f"```\n{new_code}\n```\n\n"
            f"For the task:\n"
            f"Title: {task_details['title']}\n"
            f"Description: {task_details['description']}\n"
            f"Requirements: {', '.join(task_details['requirements'])}\n"
            f"Acceptance Criteria: {', '.join(task_details['acceptance_criteria'])}\n\n"
            f"Integrate the new code into the existing file with these instructions:\n"
            f"- Preserve all existing content.\n"
            f"- Integrate the new code in a logical location, such as after existing functions or classes.\n"
            f"- Add any necessary imports at the top of the file, merging with existing imports without duplicates and sorting them alphanumerically.\n"
            f"- Sort all functions, methods, and classes alphanumerically by their names within their respective scopes (e.g., methods within a class, functions at module level).\n"
            f"- Ensure the code follows TypeScript best practices, including explicit type annotations, consistent formatting, and proper code organization.\n"
            f"- Do not remove or alter existing code unless necessary for integration or sorting.\n"
            f"- Log a warning if new code duplicates existing identifiers.\n"
            f"Return the complete updated file content."
        )
        response = self.llm.invoke(prompt)
        # Check for duplicate identifiers and log if found
        if self.detect_duplicates(existing_content, new_code):
            self.logger.warning(f"Potential identifier duplication detected in updated code file")
        return response.strip()

    def generate_updated_test_file(self, existing_content: str, new_tests: str, task_details: dict) -> str:
        """
        Use LLM to integrate new tests into an existing TypeScript test file, ensuring imports,
        test methods, describe blocks, and helper functions/classes are sorted alphanumerically.
        """
        prompt = (
            f"Given the following existing TypeScript test file:\n"
            f"```\n{existing_content}\n```\n\n"
            f"And the following new tests to integrate:\n"
            f"```\n{new_tests}\n```\n\n"
            f"For the task:\n"
            f"Title: {task_details['title']}\n"
            f"Description: {task_details['description']}\n"
            f"Requirements: {', '.join(task_details['requirements'])}\n"
            f"Acceptance Criteria: {', '.join(task_details['acceptance_criteria'])}\n\n"
            f"Integrate the new tests into the existing test file with these instructions:\n"
            f"- Preserve all existing content.\n"
            f"- Add the new test methods within the appropriate 'describe' block or create a new one if needed.\n"
            f"- Add any necessary imports at the top of the file, merging with existing imports without duplicates and sorting them alphanumerically.\n"
            f"- Sort all test methods (e.g., 'it' or 'test' functions), 'describe' blocks, and any helper functions or classes alphanumerically by their names within their respective scopes.\n"
            f"- Ensure the tests follow TypeScript and Jest best practices, including explicit type annotations, clear assertions, and consistent formatting.\n"
            f"- Do not remove or alter existing tests unless necessary for integration or sorting.\n"
            f"- Log a warning if new tests duplicate existing test names.\n"
        )
        response = self.llm.invoke(prompt)
        if self.detect_duplicates(existing_content, new_tests):
            self.logger.warning(f"Potential test name duplication detected in updated test file")
        return response.strip()

    def sort_code_content(self, content: str, task_details: dict, is_test: bool = False) -> str:
        """
        Sort code or test content before writing to new files.
        Uses LLM to ensure imports, functions, methods, classes, or test blocks are sorted alphanumerically.
        """
        prompt = (
            f"{'TypeScript test' if is_test else 'TypeScript'} code:\n```\n{content}\n```\n"
            f"Task: {task_details['title']} - {task_details['description']}\n"
            f"Sort the content:\n"
            f"- Merge imports at the top, no duplicates, sorted alphanumerically.\n"
            f"- Sort {'test methods and describe blocks' if is_test else 'functions, methods, and classes'} alphanumerically within scopes.\n"
            f"- Follow {'TypeScript/Jest' if is_test else 'TypeScript'} best practices.\n"
            f"Return the sorted content."
        )
        return self.llm.invoke(prompt).strip()

    def generate_filename(self, task_description: str, task_title: str) -> str:
        """
        Use LLM to generate a single-word camelCase filename based on the task description.
        Fall back to sanitized task title if LLM fails.
        """
        prompt = (
            f"Provide only a single-word filename in camelCase for a TypeScript file "
            f"that implements the following feature: {task_description}. "
            f"Do not include any additional text or explanation."
        )
        try:
            response = self.llm.invoke(prompt)
            suggested_filename = response.strip()
            # Validate: must be a single word, alphanumeric with optional underscores
            if re.match(r'^[a-zA-Z0-9_]+$', suggested_filename) and len(suggested_filename.split()) == 1:
                return suggested_filename
            else:
                raise ValueError("LLM suggested an invalid filename")
        except Exception as e:
            self.logger.warning(f"LLM failed to suggest a valid filename: {e}")
            # Fallback: use sanitized task title
            sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', task_title).lower()
            filename = sanitized_title.split('_')[0] or "newFeature"
            return filename

    def extract_content(self, text: str) -> str:
        """
        Extract content from markdown code blocks. If no code blocks are found, return the entire text.
        """
        pattern = r'```(?:typescript)?(.*?)```'  # Match TypeScript or generic code blocks
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            # Return the first code block found, stripped of leading/trailing whitespace
            return matches[0].strip()
        else:
            # If no code blocks are found, return the entire text stripped of leading/trailing whitespace
            return text.strip()

    def detect_duplicates(self, existing_content: str, new_content: str) -> bool:
        """
        Basic check for identifier duplication.
        Looks for overlapping function or class names between existing and new content.
        """
        existing_ids = set(re.findall(r'\bfunction\s+([a-zA-Z_]\w*)|\bclass\s+([a-zA-Z_]\w*)', existing_content))
        new_ids = set(re.findall(r'\bfunction\s+([a-zA-Z_]\w*)|\bclass\s+([a-zA-Z_]\w*)', new_content))
        return bool(existing_ids.intersection(new_ids))

    def update_file(self, file_path: str, new_content: str):
        """
        Update the content of an existing file, logging a warning for overwrites.
        Expects file_path to be absolute.
        """
        try:
            self.logger.warning(f"Overwriting existing file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            self.logger.info(f"Updated file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to update file {file_path}: {e}")
            raise

    def create_file(self, file_path: str, content: str):
        """
        Create a new file with the given content.
        Expects file_path to be absolute.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Created new file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to create file {file_path}: {e}")
            raise
