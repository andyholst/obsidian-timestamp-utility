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

            # Strict TypeScript code prompt
            self.logger.info("Preparing code generation prompt")
            code_prompt = (
                "Generate TypeScript code for the task below. "
                "Use TypeScript syntax with type annotations. "
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

            # Strict TypeScript test prompt
            self.logger.info("Preparing test generation prompt")
            test_prompt = (
                "Generate TypeScript Jest tests for the task below. "
                "Use TypeScript syntax with type annotations. "
                "Include only the test code with necessary imports, 'describe' and 'test' blocks with descriptive names, and 'expect' assertions. "
                "Do not include any comments or non-code text.\n\n"
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
