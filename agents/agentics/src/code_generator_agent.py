import logging
import json

from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags

class CodeGeneratorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeGenerator")
        self.llm = llm_client
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting code generation process")
        try:
            task_details = state['result']
            relevant_code_files = state.get('relevant_code_files', [])
            relevant_test_files = state.get('relevant_test_files', [])
            self.logger.info(f"Task details: {task_details}")
            title = task_details['title']
            description = task_details['description']
            requirements = task_details['requirements']
            acceptance_criteria = task_details['acceptance_criteria']
            self.logger.info(f"Title: {title}")
            self.logger.info(f"Description: {description}")
            self.logger.info(f"Requirements: {requirements}")
            self.logger.info(f"Acceptance Criteria: {acceptance_criteria}")

            # Format task details
            task_details_str = (
                f"Title: {title}\n"
                f"Description: {description}\n"
                f"Requirements: {', '.join(requirements)}\n"
                f"Acceptance Criteria: {', '.join(acceptance_criteria)}"
            )

            # **Generate implementation code with existing code file context**
            self.logger.info("Preparing code generation prompt")
            existing_code_content = ""
            code_file_name = ""
            if relevant_code_files:
                for code_file in relevant_code_files:
                    file_path = code_file['file_path']
                    if file_path.endswith('main.ts'):
                        existing_code_content = code_file.get('content', "")
                        code_file_name = file_path
                        break
                if existing_code_content:
                    self.logger.info(f"Using existing code content from {code_file_name}: {existing_code_content}")
                else:
                    self.logger.warning("No matching 'main.ts' found in relevant_code_files")

            code_prompt = (
                "Generate TypeScript code for the task below, to be integrated into an existing `main.ts` file for the Obsidian `TimestampPlugin`. "
                "Use TypeScript syntax with type annotations. "
                "The new code must be part of the `TimestampPlugin` class. Do not generate standalone functions or classes outside of `TimestampPlugin`. "
                "Return only the code with:\n"
                "- Necessary imports (e.g., from 'obsidian') that are not already present in the file.\n"
                "- JSDoc comments for public functions.\n"
                "Follow these rules based on the existing file structure:\n"
                f"Existing Code File Content (main.ts):\n{existing_code_content}\n\n"
                "- Extend the existing `TimestampPlugin` class by adding a new method or command as required by the task.\n"
                "- Ensure the new command is added within the `onload` method using `this.addCommand`.\n"
                "- Reuse existing imports like `import * as obsidian from 'obsidian';`.\n"
                "- Do not redefine existing classes, interfaces, or functions unless the task requires it.\n"
                "- Do not include comments (except JSDoc), explanations, or non-code text.\n\n"
                f"Task Details:\n{task_details_str}"
            ) if existing_code_content else (
                "Generate TypeScript code for the task below. "
                "Use TypeScript syntax with type annotations. "
                "The code should define a class `TimestampPlugin` that extends `obsidian.Plugin` and includes the necessary methods and commands as per the task.\n"
                "Include only the code with necessary imports and JSDoc comments for public functions. "
                "Do not include any other comments, explanations, or non-code text.\n\n"
                f"Task Details:\n{task_details_str}"
            )
            self.logger.info(f"Code prompt: {code_prompt}")

            self.logger.info("Invoking LLM for code generation")
            code_response = self.llm.invoke(code_prompt)
            clean_code_response = remove_thinking_tags(code_response)
            generated_code = clean_code_response.strip()
            self.logger.info(f"Generated code: {generated_code}")

            # **Generate test code with existing test file context**
            self.logger.info("Preparing test generation prompt")
            existing_test_content = ""
            test_file_name = ""
            if relevant_test_files:
                for test_file in relevant_test_files:
                    file_path = test_file['file_path']
                    if file_path.endswith('main.test.ts'):
                        existing_test_content = test_file.get('content', "")
                        test_file_name = file_path
                        break
                if existing_test_content:
                    self.logger.info(f"Using existing test content from {test_file_name}: {existing_test_content}")
                else:
                    self.logger.warning("No matching 'main.test.ts' found in relevant_test_files")

            test_prompt = (
                "Generate TypeScript Jest tests for the new functionality added to the `TimestampPlugin` class as described in the task below. "
                "The new functionality is implemented in the following code:\n\n"
                f"{generated_code}\n\n"
                "The tests should be appended to an existing test file `main.test.ts` for the Obsidian `TimestampPlugin`. "
                "Use TypeScript syntax with type annotations. "
                "Return only the test code with exactly two `describe` blocks:\n"
                "- One `describe` block named `describe('TimestampPlugin: <methodName>', () => {...})` to test the new method directly, "
                "where `<methodName>` is the name of the new method added in the generated code (e.g., `generateTimestamp`). "
                "Test the real implementation of the method without mocking it.\n"
                "- One `describe` block named `describe('TimestampPlugin: <command-id> command', () => {...})` to test the new command, "
                "where `<command-id>` is the ID of the command added in the generated code (e.g., `insert-timestamp`). "
                "Use `mockEditor` to mock editor interactions, but call the real method implementation.\n"
                "- Include `test` blocks inside each `describe` with clear, specific names and `expect` assertions.\n"
                "Follow these strict rules based on the existing test file structure:\n"
                f"Existing Test File Content (main.test.ts):\n{existing_test_content}\n\n"
                "- Reuse existing imports: `import TimestampPlugin from '../main';` and `import * as obsidian from 'obsidian';`. "
                "Only add new imports if they are not already present in the existing test file.\n"
                "- Reuse existing mocks: `mockEditor`, `mockApp`, `mockFile`, `mockView`, `mockCommands`, and the `plugin` instance from `beforeEach`.\n"
                "- Do not mock the `TimestampPlugin` class or the new method’s implementation; test the real method behavior.\n"
                "- For the command test, verify `mockEditor.replaceSelection` is called with the expected value and the new method is invoked.\n"
                "- Reuse existing utility functions like `parseDateString` and `generateDateRange` if applicable.\n"
                "- Do not include a top-level `describe('TimestampPlugin', ...)` block; only provide the two inner `describe` blocks to be appended.\n"
                "- Do not include `beforeEach`, `afterEach`, or any setup/teardown code.\n"
                "- Do not include comments, explanations, or non-code text.\n"
                "- Ensure the generated tests match the style and indentation of existing `describe` blocks in the test file.\n\n"
                f"Task Details:\n{task_details_str}"
            ) if existing_test_content else (
                "Generate TypeScript Jest tests for the task below, to be integrated into an existing test file for the Obsidian `TimestampPlugin`. "
                "Use TypeScript syntax with type annotations. "
                "Return only the test code with exactly two `describe` blocks:\n"
                "- One `describe` block named `describe('TimestampPlugin: <methodName>', () => {...})` to test the new method directly.\n"
                "- One `describe` block named `describe('TimestampPlugin: <command-id> command', () => {...})` to test the new command.\n"
                "- Include `test` blocks inside each `describe` with clear, specific names and `expect` assertions.\n"
                "Do not include:\n"
                "- A top-level `describe('TimestampPlugin', ...)` block.\n"
                "- `beforeEach`, `afterEach`, or other setup/teardown code.\n"
                "- Comments, explanations, or non-code text.\n\n"
                f"Task Details:\n{task_details_str}"
            )
            self.logger.info(f"Test prompt: {test_prompt}")

            self.logger.info("Invoking LLM for test generation")
            test_response = self.llm.invoke(test_prompt)
            clean_test_response = remove_thinking_tags(test_response)
            generated_tests = clean_test_response.strip()
            self.logger.info(f"Generated tests: {generated_tests}")

            state['generated_code'] = generated_code
            state['generated_tests'] = generated_tests
            self.logger.info("Code and tests generated and stored in state successfully")
            self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state
        except KeyError as e:
            self.logger.error(f"Missing field in state['result']: {str(e)}")
            raise ValueError(f"Missing field in state['result']: {e}")
        except Exception as e:
            self.logger.error(f"Error during code generation: {str(e)}")
            raise
