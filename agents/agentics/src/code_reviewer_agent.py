import logging
import json
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import read_file_tool, list_files_tool, check_file_exists_tool
from .state import State
from .utils import safe_json_dumps, remove_thinking_tags, log_info
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from .prompts import ModularPrompts


class CodeReviewerAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        super().__init__(llm_client, [read_file_tool, list_files_tool, check_file_exists_tool], name="CodeReviewer")
        self.monitor.logger.setLevel(logging.INFO)
        log_info(self.name, "Initialized CodeReviewerAgent for code/test analysis and feedback")
        # Define LCEL chain for review
        self.review_chain = self._create_review_chain()

    def _create_review_chain(self):
        """Create LCEL chain for code/test review against requirements."""
        def build_review_prompt(inputs):
            tool_instructions = "7. **Available Tools:**\nYou have access to file operation tools to help with code review:\n\n- **read_file_tool**: Read file contents for detailed analysis\n- **list_files_tool**: Explore project structure\n- **check_file_exists_tool**: Verify file availability\n\nUse these tools if you need to examine additional files for comprehensive review."
            return (
                "/think\n"
                "You are a code reviewer analyzing generated TypeScript code and tests for an Obsidian plugin against ticket requirements and acceptance criteria. "
                "Provide feedback on alignment, bugs, improvements, and a tuned prompt for re-generation if needed. "
                "Output a JSON with: 'is_aligned' (bool), 'feedback' (str: detailed issues/suggestions), 'tuned_prompt' (str: updated prompt for fixes, or empty if aligned), 'needs_fix' (bool).\n\n"
                "Requirements: {requirements}\n"
                "Acceptance Criteria: {acceptance_criteria}\n"
                "Generated Code: {generated_code}\n"
                "Generated Tests: {generated_tests}\n\n"
                f"{tool_instructions}\n\n"
                "Return only JSON."
            )

        # Use RunnableLambda to build the prompt dynamically
        return (
            RunnablePassthrough.assign(
                requirements=lambda x: json.dumps(x['result'].get('requirements', [])),
                acceptance_criteria=lambda x: json.dumps(x['result'].get('acceptance_criteria', [])),
                generated_code=lambda x: x['generated_code'],
                generated_tests=lambda x: x['generated_tests']
            )
            | RunnableLambda(build_review_prompt)
            | self.llm
            | RunnableLambda(self._process_review_response)
        )

    def _process_review_response(self, response):
        """Parse review JSON."""
        clean_response = remove_thinking_tags(response)
        try:
            return json.loads(clean_response.strip())
        except json.JSONDecodeError:
            # Return default structure if JSON parsing fails
            return {
                'is_aligned': False,
                'feedback': 'Invalid JSON response from LLM',
                'tuned_prompt': '',
                'needs_fix': True
            }

    def process(self, state: State) -> State:
        log_info(self.logger, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.logger, "Starting code/test review")
        try:
            try:
                review_result = get_circuit_breaker("code_review").call(lambda: self.review_chain.invoke(state))
            except CircuitBreakerOpenException as e:
                self.monitor.error(f"Circuit breaker open for code review: {str(e)}")
                raise
            except Exception as e:
                self.monitor.error(f"Code review failed: {str(e)}")
                raise
            state['feedback'] = review_result
            log_info(self.logger, f"Review result: {json.dumps(review_result, indent=2)}")
            log_info(self.logger, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
            return state
        except Exception as e:
            self.monitor.error(f"Error during review: {str(e)}")
            raise