import json
import logging
from typing import Dict, Any, List
from langchain_core.runnables import Runnable
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .state import CodeGenerationState
from .utils import safe_get
from .exceptions import TestRecoveryNeeded, CompileError
from .prompts import ModularPrompts

logger = logging.getLogger(__name__)

class FixesModel(BaseModel):
    """Pydantic model for LLM fixes output"""
    fixed_code: str = Field(..., description="Complete fixed TypeScript code for the main file")
    fixed_tests: str = Field(..., description="Complete fixed Jest test code for the test file")
    confidence: float = Field(..., ge=0, le=100, description="Confidence in fixes (0-100)")
    explanation: str = Field(..., description="Brief explanation of fixes applied")

class ErrorRecoveryAgent(Runnable[CodeGenerationState, CodeGenerationState]):
    """Simplified error recovery agent for test failures using LCEL chain and Pydantic."""

    def __init__(self, llm_reasoning: Runnable):
        self.llm_reasoning = llm_reasoning
        self.chain = self._build_chain()
        self.strategies = {
            "POST_TEST_RUNNER": self._test_failure_recovery
        }

    def _build_chain(self) -> Runnable:
        # Fix for code-reviewer error_recovery_agent.py:33-41 issue: Configurable backoff/retries - Prevents build failures
        parser = PydanticOutputParser(pydantic_object=FixesModel)
        prompt = PromptTemplate(
            template=ModularPrompts.get_ts_build_fix_prompt(),
            input_variables=["errors", "generated_code", "generated_tests"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = (prompt | self.llm_reasoning | parser).with_retry(max_attempts=3, backoff_factor=2)
        return chain

    def invoke(self, input: CodeGenerationState, config=None) -> CodeGenerationState:
        return self.process(input)

    def _test_failure_recovery(self, state: CodeGenerationState) -> CodeGenerationState:
        """Process recovery for test failures."""
        logger.info(f"ErrorRecovery process called with recovery_attempt={safe_get(state, 'recovery_attempt', 0)}, test_errors={len(safe_get(state, 'test_errors', []))} ")

        if not safe_get(state, 'test_errors', []) or safe_get(state, 'recovery_attempt', 0) >= 3:
            raise TestRecoveryNeeded(f"Max recovery attempts ({safe_get(state, 'recovery_attempt', 0)}) reached or no test_errors. Log: {safe_get(state, 'test_log_path', 'N/A')}")

        try:
            fixes = self.chain.invoke({
                "errors": json.dumps(safe_get(state, 'test_errors', []) + safe_get(state, 'build_errors', []), indent=2),
                "generated_code": safe_get(state, 'generated_code', ''),
                "generated_tests": safe_get(state, 'generated_tests', ''),
            })
            logger.info(f"Recovery fixes generated, confidence={fixes.confidence}")

            new_state = (state
                         .with_code(fixes.fixed_code)
                         .with_tests(fixes.fixed_tests)
                         .with_recovery_update(fixes.confidence, fixes.explanation))
            return new_state
        except Exception as e:
            logger.error(f"Recovery chain failed: {str(e)}")
            return state

    def process(self, state: CodeGenerationState) -> CodeGenerationState:
        """Dispatch to the appropriate recovery strategy based on state['recovery_strategy']."""
        strategy_name: str = safe_get(state, 'recovery_strategy', 'POST_TEST_RUNNER')
        strategy = self.strategies.get(strategy_name)
        if strategy:
            logger.info(f"Executing {strategy_name} recovery strategy")
            return strategy(state)
        logger.warning(f"Unknown recovery strategy '{strategy_name}', skipping recovery")
        return state
