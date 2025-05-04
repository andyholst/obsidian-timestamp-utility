from .base_agent import BaseAgent
from .state import State

class CodeGeneratorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeGenerator")
        self.llm = llm_client

    def process(self, state: State) -> State:
        try:
            task_details = state['result']
            title = task_details['title']
            description = task_details['description']
            requirements = task_details['requirements']
            acceptance_criteria = task_details['acceptance_criteria']

            code_prompt = (
                f"Generate TypeScript code for the following task:\n"
                f"Title: {title}\nDescription: {description}\n"
                f"Requirements: {', '.join(requirements)}\n"
                f"Acceptance Criteria: {', '.join(acceptance_criteria)}\n"
                f"Ensure the code is well-documented with comments.\n"
                f"Wrap the code in ```typescript``` markdown code blocks."
            )
            code_response = self.llm.invoke(code_prompt)
            generated_code = code_response.strip()

            test_prompt = (
                f"Generate unit and integration tests for this TypeScript code using Jest:\n"
                f"{generated_code}\n"
                f"Validate: {', '.join(requirements)} and {', '.join(acceptance_criteria)}.\n"
                f"Ensure the tests include at least one 'test' or 'describe' block and use 'expect' for assertions.\n"
                f"Wrap the test code in ```typescript``` markdown code blocks."
            )
            test_response = self.llm.invoke(test_prompt)
            generated_tests = test_response.strip()

            state['generated_code'] = generated_code
            state['generated_tests'] = generated_tests
            return state
        except KeyError as e:
            raise ValueError(f"Missing field in state['result']: {e}")
