import json
import logging
import os
from typing import Dict, List

from .base_agent import BaseAgent
from .state import State
from langchain.prompts import PromptTemplate
from .utils import safe_json_dumps, remove_thinking_tags, log_info, parse_json_response
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException


class ImplementationPlannerAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("ImplementationPlannerAgent")
        self.llm = llm_client
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        log_info(self.name, "Starting implementation planning")
        refined_ticket = state.get("refined_ticket", {})

        # In ultra-fast mode, ensure required fields exist without LLM call
        if refined_ticket.get("implementation_steps") and os.getenv("TEST_ULTRA_FAST_MODE") == "1":
            log_info(self.name, "Ultra-fast mode: ensuring required fields exist")
            refined_ticket.setdefault("implementation_steps", [f"Implement {refined_ticket.get('title', 'the feature')}"])
            refined_ticket.setdefault("npm_packages", [])
            refined_ticket.setdefault("manual_implementation_notes", "Ultra-fast mode: implementation planned without LLM")
            state["refined_ticket"] = refined_ticket
            return state

        # Otherwise, do the normal LLM-based planning
        try:
            enhanced_ticket = self.plan_implementation(refined_ticket)
            state["refined_ticket"] = enhanced_ticket
        except Exception as e:
            log_info(self.name, f"Implementation planning failed: {e}, using defaults")
            # Ensure required fields exist
            refined_ticket.setdefault("implementation_steps", ["Implement the feature"])
            refined_ticket.setdefault("npm_packages", [])

        log_info(self.name, "Implementation planning completed")
        return state

    def _default_enhanced_ticket(self, refined_ticket: Dict) -> Dict:
        """Return enhanced ticket with default values when LLM is unavailable."""
        enhanced = refined_ticket.copy()
        title = refined_ticket.get("title", "the required functionality")
        enhanced.setdefault("implementation_steps", [f"Implement {title}"])
        enhanced.setdefault("npm_packages", [])
        enhanced.setdefault("manual_implementation_notes", "LLM unavailable; manual implementation required")
        return enhanced

    def plan_implementation(self, refined_ticket: Dict) -> Dict:
        log_info(self.logger, "Planning implementation details")
        prompt = "/think\n" + PromptTemplate(
            input_variables=[
                "title",
                "description",
                "requirements",
                "acceptance_criteria",
            ],
            template=(
                "Analyze the following ticket and provide detailed implementation guidance. "
                "Research and suggest existing npm packages that can support the implementation. "
                "For each requirement, specify if it can be implemented using an npm package, manually, or a combination. "
                'Return ONLY valid JSON with these exact fields. Schema example: {{\\"implementation_steps\\": [\\"detailed step 1\\", \\"step 2\\"], \\"npm_packages\\": [\\"uuidv7 (UUIDv7 generation)\\"], \\"manual_implementation_notes\\": \\"notes\\"}}. '
                "Do not include the original fields in the response. Do not include any additional text, code blocks, or explanations.\n\n"
                "Title: {title}\n"
                "Description: {description}\n"
                "Requirements: {requirements}\n"
                "Acceptance Criteria: {acceptance_criteria}\n\n"
                "JSON response:"
            ),
        ).format(
            title=refined_ticket["title"],
            description=refined_ticket["description"],
            requirements="\n".join(
                f"- {req}" for req in refined_ticket["requirements"]
            ),
            acceptance_criteria="\n".join(
                f"- {ac}" for ac in refined_ticket["acceptance_criteria"]
            ),
        )
        log_info(self.logger, f"Implementation planning prompt: {prompt}")

        try:
            response = get_circuit_breaker("implementation_planning").call(
                lambda: self.llm.invoke(prompt)
            )
        except CircuitBreakerOpenException as e:
            log_info(
                self.logger,
                f"Circuit breaker open for implementation planning: {str(e)}",
            )
            return self._default_enhanced_ticket(refined_ticket)
        except Exception as e:
            log_info(self.logger, f"Implementation planning failed: {str(e)}")
            return self._default_enhanced_ticket(refined_ticket)
        clean_response = remove_thinking_tags(response)
        log_info(self.logger, f"LLM response: {clean_response}")
        result = parse_json_response(clean_response)
        log_info(self.logger, f"Parsed result: {result}")

        # Merge with original, preserving requirements and acceptance criteria
        enhanced = refined_ticket.copy()
        enhanced.update(result)
        # Preserve original requirements and acceptance criteria, append any new ones from planner
        enhanced["title"] = refined_ticket.get("title", "")
        enhanced["description"] = refined_ticket.get("description", "")
        enhanced["requirements"] = refined_ticket.get("requirements", []) + result.get(
            "requirements", []
        )
        enhanced["acceptance_criteria"] = refined_ticket.get(
            "acceptance_criteria", []
        ) + result.get("acceptance_criteria", [])
        return enhanced
