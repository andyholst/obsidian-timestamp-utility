import logging
import json
import re
import os

from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags, log_info

class CodeGeneratorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeGenerator")
        self.llm = llm_client
        self.main_file = os.getenv('MAIN_FILE', 'main.ts')
        self.test_file = os.getenv('TEST_FILE', 'main.test.ts')
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with main file: {self.main_file}, test file: {self.test_file}")

    def process(self, state: State) -> State:
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting code generation process")
        try:
            task_details = state['result']
            relevant_code_files = state.get('relevant_code_files', [])
            relevant_test_files = state.get('relevant_test_files', [])
            log_info(self.logger, f"Task details: {json.dumps(task_details, indent=2)}")
            title = task_details['title']
            description = task_details['description']
            requirements = task_details['requirements']
            acceptance_criteria = task_details['acceptance_criteria']
            log_info(self.logger, f"Title: {title}")
            log_info(self.logger, f"Description: {description}")
            log_info(self.logger, f"Requirements: {requirements}")
            log_info(self.logger, f"Acceptance Criteria: {acceptance_criteria}")

            task_details_str = (
                f"Title: {title}\n"
                f"Description: {description}\n"
                f"Requirements: {', '.join(requirements)}\n"
                f"Acceptance Criteria: {', '.join(acceptance_criteria)}"
            )
            log_info(self.logger, f"Formatted task details: {task_details_str}")

            log_info(self.logger, "Preparing code generation prompt")
            existing_code_content = ""
            code_file_name = ""
            if relevant_code_files:
                for code_file in relevant_code_files:
                    file_path = code_file['file_path']
                    if file_path.endswith(self.main_file):
                        existing_code_content = code_file.get('content', "")
                        code_file_name = file_path
                        break
                if existing_code_content:
                    log_info(self.logger, f"Using existing code content from {code_file_name}: {existing_code_content}")
                else:
                    self.logger.warning(f"No matching '{self.main_file}' found in relevant_code_files")

            code_prompt = (
                "/think\n"
                f"You are tasked with generating TypeScript code for an Obsidian plugin. The plugin is defined in `{self.main_file}`, and you must integrate the new functionality into the existing `TimestampPlugin` class without altering any existing code. Follow these instructions carefully:\n\n"
                "1. **Existing Code Structure:**\n"
                f"   - The file `{self.main_file}` contains the `TimestampPlugin` class, which extends `obsidian.Plugin`.\n"
                "   - Commands are added in the `onload` method using `this.addCommand`.\n"
                "   - Helper functions and modals may be defined outside the class.\n\n"
                "2. **New Code Requirements:**\n"
                "   - Add a new public method to the `TimestampPlugin` class with a name derived from the task title (e.g., `doSomethingMinimal` for 'Do something minimal').\n"
                "   - Ensure the method is public and does not use `private` or `protected` keywords.\n"
                "   - Add a new command within the `onload` method that calls this method using `this.addCommand`.\n"
                "   - Reuse existing imports (e.g., `import * as obsidian from 'obsidian';`).\n"
                "   - Do not redefine existing classes, interfaces, methods, or functions.\n"
                "   - You may include single-line comments (//) above new methods to describe their purpose, but do not add any other comments or explanations.\n\n"
                "3. **Task Details:**\n"
                f"{task_details_str}\n\n"
                f"4. **Existing Code ({self.main_file}):**\n"
                f"{existing_code_content}\n\n"
                "5. **Output Instructions:**\n"
                f"   - Your response must contain only the new TypeScript code to be added to `{self.main_file}`, including any necessary imports not already present.\n"
                "   - The code should start with any new imports, followed by the new method definition inside the class, and the command addition in `onload`.\n"
                "   - Do not include any comments, explanations, or additional text outside the code itself, except for single-line comments above new methods.\n"
                "   - Do not add any markers or comments indicating the start or end of the new code.\n"
                "   - Do not wrap the code in a code block.\n"
                "   - The response must start with the code and end with the code, with no additional lines or text before or after.\n"
                "   - Ensure the code is properly formatted and uses TypeScript syntax with type annotations."
            ) if existing_code_content else (
                "/think\n"
                "Generate TypeScript code for the task below. The code should define a class `TimestampPlugin` that extends `obsidian.Plugin` and includes the necessary methods and commands as per the task.\n\n"
                "- Ensure that all methods in the `TimestampPlugin` class are public. Do not use the `private` or `protected` keywords for any methods.\n"
                "- Add a new public method with a name derived from the task title (e.g., `doSomethingMinimal` for 'Do something minimal').\n"
                "- Add a command in the `onload` method that calls this method using `this.addCommand`.\n\n"
                "Include only the code with necessary imports. You may include single-line comments (//) above methods to describe their purpose, but do not add any other comments or explanations.\n\n"
                "Do not wrap the code in a code block or add any markers indicating the start or end of the code. The response must contain only the raw TypeScript code, starting and ending with the code itself.\n\n"
                f"Task Details:\n{task_details_str}"
            )
            log_info(self.logger, f"Code prompt length: {len(code_prompt)}")
            log_info(self.logger, f"Code prompt: {code_prompt}")

            log_info(self.logger, "Invoking LLM for code generation")
            code_response = self.llm.invoke(code_prompt)
            clean_code_response = remove_thinking_tags(code_response)
            generated_code = clean_code_response.strip()
            log_info(self.logger, f"Generated code length: {len(generated_code)}")
            log_info(self.logger, f"Generated code: {generated_code}")

            method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', generated_code)
            if method_match:
                method_name = method_match.group(2)
                log_info(self.logger, f"Extracted method name: {method_name}")
            else:
                self.logger.error("Could not find method name in generated code")
                raise ValueError("Could not find method name in generated code")

            command_match = re.search(r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', generated_code)
            if command_match:
                command_id = command_match.group(1)
                log_info(self.logger, f"Extracted command ID: {command_id}")
            else:
                self.logger.error("Could not find command ID in generated code")
                raise ValueError("Could not find command ID in generated code")

            log_info(self.logger, "Preparing test generation prompt")
            existing_test_content = ""
            test_file_name = ""
            if relevant_test_files:
                for test_file in relevant_test_files:
                    file_path = test_file['file_path']
                    if file_path.endswith(self.test_file):
                        existing_test_content = test_file.get('content', "")
                        test_file_name = file_path
                        break
                if existing_test_content:
                    log_info(self.logger, f"Using existing test content from {test_file_name}: {existing_test_content}")
                else:
                    self.logger.warning(f"No matching '{self.test_file}' found in relevant_test_files")

            test_prompt = (
                "/think\n"
                f"You are tasked with generating Jest tests for the new functionality added to the `TimestampPlugin` class in an Obsidian plugin. "
                f"The tests must be integrated into the existing `{self.test_file}` file without altering any existing code. "
                f"Follow these instructions carefully:\n\n"
                "1. **Existing Test Structure:**\n"
                f"   - The file `{self.test_file}` contains a top-level `describe('TimestampPlugin', () => {{ ... }})` block.\n"
                "   - Inside this block, there are multiple `describe` blocks for different methods and commands.\n"
                "   - Mocks are set up in a `beforeEach` block, including `mockEditor`, `mockApp`, `mockFile`, etc.\n"
                "   - Commands are accessed via `mockCommands['<command-id>']` after `await plugin.onload()` is called.\n"
                "   - `plugin` is an instance of `TimestampPlugin` initialized in `beforeEach`.\n\n"
                "2. **New Test Requirements:**\n"
                f"   - Generate exactly two `describe` blocks:\n"
                f"     - One for the method `{method_name}` added to `TimestampPlugin`.\n"
                f"     - One for the command `{command_id}` added via `this.addCommand`.\n"
                f"   - For the method test, call `plugin.{method_name}()` to use the real implementation.\n"
                f"   - For the command test, execute `mockCommands['{command_id}'].callback()` to trigger the command, which should call `{method_name}` and interact with `mockEditor`.\n"
                "   - Match the style of existing tests (e.g., async tests with `await plugin.onload()`, checking `mockEditor.replaceSelection`).\n"
                f"   - Only generate tests for `{method_name}` and `{command_id}`, as these are the new additions.\n\n"
                "3. **Task Details:**\n"
                f"{task_details_str}\n\n"
                "4. **Generated Code:**\n"
                f"{generated_code}\n\n"
                f"5. **Existing Test File ({self.test_file}):**\n"
                f"{existing_test_content}\n\n"
                "6. **Output Instructions:**\n"
                f"   - Return only the two `describe` blocks for `{method_name}` and `{command_id}`.\n"
                f"   - The first block must start with `describe('TimestampPlugin: {method_name}', () => {{`.\n"
                f"   - The second block must start with `describe('TimestampPlugin: {command_id} command', () => {{`.\n"
                "   - Each block must end with `});`.\n"
                "   - Do not include any code outside these `describe` blocks, such as imports, `beforeEach`, or other setup code.\n"
                "   - Ensure each `describe` block is indented with 4 spaces per level to match the existing file.\n"
                "   - Your response must start with the first `describe` line and end with the last `});`, with no additional text, comments, or explanations."
            ) if existing_test_content else (
                "/think\n"
                "Generate TypeScript Jest tests for the new functionality added to the `TimestampPlugin` class in an Obsidian plugin. "
                "The tests are to be integrated into a test file that follows a common pattern with a top-level `describe('TimestampPlugin', () => {{ ... }})` block, "
                "but only the two inner `describe` blocks are needed here. Follow these instructions:\n\n"
                "1. **Test Requirements:**\n"
                f"   - Generate exactly two `describe` blocks:\n"
                f"     - One for the method `{method_name}`.\n"
                f"     - One for the command `{command_id}`.\n"
                f"   - For the method test, assume `{method_name}` is an instance method on `TimestampPlugin` and call it via `plugin.{method_name}()`.\n"
                f"   - For the command test, assume the command is accessible via `mockCommands['{command_id}']`, uses `mockEditor`, and calls `{method_name}` in its callback.\n"
                "   - Use TypeScript syntax with type annotations.\n"
                f"   - Only generate tests for `{method_name}` and `{command_id}`, as these are the new additions.\n\n"
                "2. **Task Details:**\n"
                f"{task_details_str}\n\n"
                "3. **Generated Code:**\n"
                f"{generated_code}\n\n"
                "4. **Output Instructions:**\n"
                f"   - Return only the two `describe` blocks.\n"
                f"   - The first block must start with `describe('TimestampPlugin: {method_name}', () => {{`.\n"
                f"   - The second block must start with `describe('TimestampPlugin: {command_id} command', () => {{`.\n"
                "   - Each block must end with `});`.\n"
                "   - Do not include a top-level `describe('TimestampPlugin', ...)` block, `beforeEach`, or any setup/teardown code.\n"
                "   - Ensure 4-space indentation per level.\n"
                "   - No additional text or comments outside the `describe` blocks."
            )
            log_info(self.logger, f"Test prompt length: {len(test_prompt)}")
            log_info(self.logger, f"Test prompt: {test_prompt}")

            log_info(self.logger, "Invoking LLM for test generation")
            test_response = self.llm.invoke(test_prompt)
            clean_test_response = remove_thinking_tags(test_response)
            generated_tests = clean_test_response.strip()
            log_info(self.logger, f"Generated tests length: {len(generated_tests)}")
            log_info(self.logger, f"Generated tests: {generated_tests}")

            state['generated_code'] = generated_code
            state['generated_tests'] = generated_tests
            log_info(self.logger, "Code and tests generated and stored in state successfully")
            log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state
        except KeyError as e:
            self.logger.error(f"Missing field in state['result']: {str(e)}")
            raise ValueError(f"Missing field in state['result']: {e}")
        except Exception as e:
            self.logger.error(f"Error during code generation: {str(e)}")
            raise
