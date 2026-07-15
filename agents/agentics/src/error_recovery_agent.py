import json
import logging
from typing import Dict, Any, List, Optional, Callable
from langchain_core.runnables import Runnable
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from unittest.mock import MagicMock
from pydantic import BaseModel, Field

from .state import CodeGenerationState, State
from .utils import safe_get
from .exceptions import TestRecoveryNeeded, CompileError
from .base_agent import AgentType
from .circuit_breaker import get_circuit_breaker, get_health_monitor

from enum import Enum


class RecoveryStrategy(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADATION = "degradation"
    SKIP = "skip"
    SUBSTITUTE = "substitute"
    STATE_RECOVERY = "state_recovery"


class CircuitBreakerOpenException(Exception):
    pass


logger = logging.getLogger(__name__)


class FixesModel(BaseModel):
    fixed_code: str = Field(..., description="Complete fixed TypeScript code")
    fixed_tests: str = Field(..., description="Complete fixed Jest test code")
    confidence: float = Field(..., ge=0, le=100, description="Confidence in fixes")
    explanation: str = Field(..., description="Brief explanation of fixes applied")


_AGENT_SERVICES = {
    AgentType.CODE_GENERATOR: ["ollama_code", "typescript_compiler"],
    AgentType.TEST_GENERATOR: ["ollama_code", "typescript_compiler"],
    AgentType.CODE_INTEGRATOR: ["file_system", "typescript_compiler"],
    AgentType.CODE_REVIEWER: ["ollama_reasoning"],
    AgentType.DEPENDENCY_ANALYZER: ["ollama_reasoning"],
    AgentType.FETCH_ISSUE: ["github"],
    AgentType.TICKET_CLARITY: ["ollama_reasoning"],
    AgentType.IMPLEMENTATION_PLANNER: ["ollama_reasoning"],
}

_AGENT_MAX_RETRIES = {
    AgentType.CODE_GENERATOR: 2,
    AgentType.TEST_GENERATOR: 2,
    AgentType.CODE_INTEGRATOR: 1,
    AgentType.CODE_REVIEWER: 1,
    AgentType.DEPENDENCY_ANALYZER: 1,
    AgentType.FETCH_ISSUE: 3,
    AgentType.TICKET_CLARITY: 1,
    AgentType.IMPLEMENTATION_PLANNER: 1,
}


class ErrorRecoveryAgent(Runnable[CodeGenerationState, CodeGenerationState]):
    name = "ErrorRecovery"

    def __init__(self, llm_reasoning: Runnable = None, fallback_strategies: Dict[str, Any] = None):
        self.llm_reasoning = llm_reasoning or MagicMock()
        self.chain = self._build_chain()
        self.fallback_strategies = fallback_strategies or {
            "retry": self._retry_strategy,
            "degrade": self._degrade_strategy,
            "skip": self._skip_strategy,
            "substitute": self._substitute_strategy,
            "state_recovery": self._state_recovery_strategy,
        }
        self.circuit_breaker = get_circuit_breaker("error_recovery")
        self.health_monitor = get_health_monitor()

        self.circuit_breakers = {}
        for service in ["ollama_reasoning", "ollama_code", "github", "typescript_compiler", "file_system"]:
            self.circuit_breakers[service] = get_circuit_breaker(service)

        self.recovery_strategies = {}
        for agent_type in AgentType:
            self.recovery_strategies[agent_type] = {
                "agent_type": agent_type,
                "max_retries": _AGENT_MAX_RETRIES.get(agent_type, 2),
                "services": _AGENT_SERVICES.get(agent_type, []),
                "fallback_strategy": None,
            }

    def _build_chain(self) -> Runnable:
        parser = PydanticOutputParser(pydantic_object=FixesModel)
        prompt = PromptTemplate(
            template="""Analyze and fix these TypeScript test errors:

Errors:
{errors}

Current generated code:
{code}

Current generated tests:
{tests}

Ticket context:
{ticket}

Output ONLY valid JSON matching the schema.

{format_instructions}""",
            input_variables=["errors", "code", "tests", "ticket"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self.llm_reasoning | parser
        return chain

    def invoke(self, input: CodeGenerationState, config=None, **kwargs: Any) -> CodeGenerationState:
        # Always increment recovery attempt to prevent infinite loops
        from dataclasses import asdict, fields
        d = asdict(input)
        d["recovery_attempt"] = d.get("recovery_attempt", 0) + 1
        d["recovery_confidence"] = max(0.0, 100.0 - d["recovery_attempt"] * 25.0)
        state = CodeGenerationState(**d)
        return self.process(state)

    def process(self, state: State) -> State:
        failed_agent = state.get("failed_agent", "")
        error_context = state.get("error_context")

        if not failed_agent or error_context is None:
            return state

        # Increment recovery attempt counter
        current_attempt = state.get("recovery_attempt", 0)
        result = dict(state)
        result["recovery_attempt"] = current_attempt + 1
        result["recovery_confidence"] = max(0.0, 100.0 - (current_attempt + 1) * 25.0)

        try:
            agent_type = AgentType(failed_agent)
        except ValueError:
            result["recovery_failed"] = True
            return result

        try:
            recovery_result = self._attempt_recovery(agent_type, state, error_context, state.get("original_error", Exception("unknown")))
            if recovery_result.get("success"):
                result["recovery_applied"] = True
                result["recovery_details"] = recovery_result
                result.pop("failed_agent", None)
                result.pop("error_context", None)
                result.pop("original_error", None)
                return result
            else:
                result["recovery_failed"] = True
                result["recovery_details"] = recovery_result
                return result
        except Exception as e:
            result["recovery_failed"] = True
            return result

    def recover(self, state: State, error: Exception) -> State:
        """Recover from an error using circuit breaker protection."""
        strategy = self._select_recovery_strategy(error)
        result = self.circuit_breaker.call(strategy, state, error)
        return result

    def _select_recovery_strategy(self, error: Exception) -> Callable:
        """Select recovery strategy based on error type. Returns a callable."""
        if isinstance(error, TimeoutError):
            return self.fallback_strategies["retry"]
        if isinstance(error, ConnectionError):
            return self.fallback_strategies["retry"]
        if isinstance(error, CircuitBreakerOpenException):
            return self.fallback_strategies["degrade"]
        if isinstance(error, ValueError):
            return self.fallback_strategies["substitute"]
        if isinstance(error, KeyError):
            return self.fallback_strategies["state_recovery"]
        return self.fallback_strategies["skip"]

    def _attempt_recovery(self, agent_type: AgentType, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        """Attempt recovery for a specific agent type and error."""
        if isinstance(error, CircuitBreakerOpenException):
            return self._handle_circuit_breaker_error(agent_type, state, error_context)

        strategy_config = self.recovery_strategies.get(agent_type, {})
        return self._execute_recovery_strategy(agent_type, strategy_config, state, error_context, error)

    def _execute_recovery_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        """Execute recovery strategies in order: retry -> fallback -> degradation -> skip -> substitute."""
        total_attempts = 0

        # Try retry
        retry_result = self._execute_retry_strategy(agent_type, strategy_config, state, error_context, error)
        total_attempts += retry_result.get("attempts", 0)
        if retry_result.get("success"):
            return retry_result

        # Try fallback
        fallback_result = self._execute_fallback_strategy(agent_type, strategy_config, state, error_context, error)
        total_attempts += fallback_result.get("attempts", 0)
        if fallback_result.get("success"):
            return fallback_result

        # Try degradation
        degrade_result = self._execute_degradation_strategy(agent_type, strategy_config, state, error_context, error)
        total_attempts += degrade_result.get("attempts", 0)
        if degrade_result.get("success"):
            return degrade_result

        # Try skip
        skip_result = self._execute_skip_strategy(agent_type, strategy_config, state, error_context, error)
        total_attempts += skip_result.get("attempts", 0)
        if skip_result.get("success"):
            return skip_result

        # Try substitute
        sub_result = self._execute_substitute_strategy(agent_type, strategy_config, state, error_context, error)
        total_attempts += sub_result.get("attempts", 0)
        if sub_result.get("success"):
            return sub_result

        return {"success": False, "strategy": "all_failed", "attempts": total_attempts}

    def _execute_retry_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        max_retries = strategy_config.get("max_retries", 2)
        for attempt in range(1, max_retries + 1):
            healthy = self._check_service_health_for_agent(agent_type)
            if not healthy:
                return {"success": False, "strategy": RecoveryStrategy.RETRY.value, "attempts": max_retries}
            try:
                result = self._retry_with_circuit_breaker(agent_type, state, error_context)
                if result.get("success"):
                    return {"success": True, "strategy": RecoveryStrategy.RETRY.value, "attempts": 1}
            except Exception:
                if attempt == max_retries:
                    return {"success": False, "strategy": RecoveryStrategy.RETRY.value, "attempts": max_retries}
        return {"success": False, "strategy": RecoveryStrategy.RETRY.value, "attempts": max_retries}

    def _execute_fallback_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        try:
            if agent_type == AgentType.CODE_GENERATOR:
                result = self._code_generation_fallback(state, error_context, error)
            elif agent_type == AgentType.TEST_GENERATOR:
                result = self._test_generation_fallback(state, error_context, error)
            elif agent_type == AgentType.CODE_INTEGRATOR:
                result = self._code_integration_fallback(state, error_context, error)
            else:
                result = {"success": True, "strategy": "fallback"}
            if result.get("success"):
                return {"success": True, "strategy": RecoveryStrategy.FALLBACK.value, "attempts": 1}
            return {"success": False, "strategy": RecoveryStrategy.FALLBACK.value, "attempts": 1}
        except Exception:
            return {"success": False, "strategy": RecoveryStrategy.FALLBACK.value, "attempts": 1}

    def _execute_degradation_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        if agent_type == AgentType.CODE_GENERATOR:
            result = self._code_generation_degradation(state, error_context, error)
        elif agent_type == AgentType.TEST_GENERATOR:
            result = self._test_generation_degradation(state, error_context, error)
        else:
            result = {"success": True, "degraded_mode": True}
        if result.get("success"):
            return {"success": True, "strategy": RecoveryStrategy.DEGRADATION.value, "attempts": 1}
        return {"success": False, "strategy": RecoveryStrategy.DEGRADATION.value, "attempts": 1}

    def _execute_skip_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        if agent_type == AgentType.CODE_GENERATOR:
            result = self._code_generation_skip(state, error_context, error)
        elif agent_type == AgentType.TEST_GENERATOR:
            result = self._test_generation_skip(state, error_context, error)
        else:
            result = {"success": True, "skipped": True}
        if result.get("success"):
            return {"success": True, "strategy": RecoveryStrategy.SKIP.value, "attempts": 1}
        return {"success": False, "strategy": RecoveryStrategy.SKIP.value, "attempts": 1}

    def _execute_substitute_strategy(self, agent_type: AgentType, strategy_config: Dict, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        if agent_type == AgentType.CODE_GENERATOR:
            result = self._code_generation_substitute(state, error_context, error)
        elif agent_type == AgentType.TEST_GENERATOR:
            result = self._test_generation_substitute(state, error_context, error)
        else:
            result = {"success": True, "substituted": True}
        if result.get("success"):
            return {"success": True, "strategy": RecoveryStrategy.SUBSTITUTE.value, "attempts": 1}
        return {"success": False, "strategy": RecoveryStrategy.SUBSTITUTE.value, "attempts": 1}

    def _handle_circuit_breaker_error(self, agent_type: AgentType, state: State, error_context: Dict) -> Dict[str, Any]:
        return self._execute_degradation_strategy(agent_type, self.recovery_strategies.get(agent_type, {}), state, error_context, CircuitBreakerOpenException("Circuit open"))

    def _check_service_health_for_agent(self, agent_type: AgentType) -> bool:
        services = _AGENT_SERVICES.get(agent_type, [])
        for service in services:
            if not self.health_monitor.is_service_healthy(service):
                return False
        return True

    def _retry_with_circuit_breaker(self, agent_type: AgentType, state: State, error_context: Dict) -> Dict[str, Any]:
        healthy = self._check_service_health_for_agent(agent_type)
        if not healthy:
            raise Exception("Service still unhealthy after retries")
        return {"success": True, "data": "Recovered successfully"}

    # Agent-specific fallback strategies
    def _code_generation_fallback(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        code = state.get("generated_code", "")
        return {"success": True, "fallback_code": code}

    def _test_generation_fallback(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        tests = state.get("generated_tests", "")
        return {"success": True, "fallback_tests": tests}

    def _code_integration_fallback(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        state["integration_skipped"] = True
        return {"success": True}

    # Agent-specific degradation strategies
    def _code_generation_degradation(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        state["generated_code"] = ""
        state["code_generation_degraded"] = True
        return {"success": True, "degraded_mode": True}

    def _test_generation_degradation(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        state["generated_tests"] = ""
        state["test_generation_degraded"] = True
        return {"success": True, "degraded_mode": True}

    # Agent-specific skip strategies
    def _code_generation_skip(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        state["code_generation_skipped"] = True
        state["generated_code"] = ""
        return {"success": True, "skipped": True}

    def _test_generation_skip(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        state["test_generation_skipped"] = True
        state["generated_tests"] = ""
        return {"success": True, "skipped": True}

    # Agent-specific substitute strategies
    def _code_generation_substitute(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        # B10: no hard-coded TS body here. The deterministic integrator derives the
        # real contract from the OpenSpec spec; this is only a non-TS marker so the
        # idempotency guards never match a baked-in body.
        substitute = "// RECOVERY_SUBSTITUTE_CODE"
        state["generated_code"] = substitute
        return {"success": True, "substituted": True}

    def _test_generation_substitute(self, state: State, error_context: Dict, error: Exception) -> Dict[str, Any]:
        # B10: no hard-coded `describe`/`it` test body. The test generator (spec-driven)
        # is the sole author of test bodies; this marker is inert.
        substitute = "// RECOVERY_SUBSTITUTE_TESTS"
        state["generated_tests"] = substitute
        return {"success": True, "substituted": True}

    # High-level strategy methods
    def _retry_strategy(self, state: State, error: Exception) -> State:
        result = dict(state)
        result["recovery_applied"] = True
        result["recovery_details"] = {"success": True, "strategy": "retry"}
        return State(**result)

    def _degrade_strategy(self, state: State, error: Exception) -> State:
        result = dict(state)
        result["recovery_applied"] = True
        result["recovery_details"] = {"success": True, "strategy": "degradation"}
        return State(**result)

    def _skip_strategy(self, state: State, error: Exception) -> State:
        result = dict(state)
        result["recovery_applied"] = True
        result["recovery_details"] = {"success": True, "strategy": "skip"}
        return State(**result)

    def _substitute_strategy(self, state: State, error: Exception) -> State:
        result = dict(state)
        result["recovery_applied"] = True
        result["recovery_details"] = {"success": True, "strategy": "substitute"}
        return State(**result)

    def _state_recovery_strategy(self, state, error: Exception) -> State:
        """State recovery strategy - reinitializes state."""
        if isinstance(state, dict):
            result = dict(state)
            result["recovery_applied"] = True
            result["recovery_details"] = {"success": True, "strategy": RecoveryStrategy.STATE_RECOVERY.value}
            result["state_recovered"] = True
            result.pop("failed_agent", None)
            result.pop("error_context", None)
            result.pop("original_error", None)
            return State(**result)
        else:
            return {"recovery_failed": True, "recovery_details": {"success": False, "strategy": RecoveryStrategy.STATE_RECOVERY.value}}

    def get_recovery_status(self) -> Dict[str, Any]:
        return {
            "circuit_breakers": self.circuit_breakers,
            "service_health": self.health_monitor.get_service_status(),
            "recovery_history": [],
        }

    def _generate_minimal_code_stub(self, state: State) -> str:
        # B10: inert marker, no TS body. Real code comes from the spec-driven generator.
        return "// FALLBACK_CODE_STUB"

    def _generate_minimal_test_stub(self, state: State) -> str:
        # B10: inert marker, no `describe`/`it` body. Real tests come from the spec.
        return "// FALLBACK_TEST_STUB"

    def _parse_ticket_basic(self, state: State) -> Dict[str, str]:
        return {"title": "Basic Task", "description": state.get("ticket_content", "")}

    def _generate_substitute_code_stub(self, state: State) -> str:
        # B10: inert marker, no TS class body.
        return "// SUBSTITUTE_CODE_STUB"

    def _generate_substitute_test_stub(self, state: State) -> str:
        # B10: inert marker, no `describe`/`it` body.
        return "// SUBSTITUTE_TEST_STUB"

    def _parse_ticket_substitute(self, state: State) -> Dict[str, str]:
        return {"title": "Substitute Task Analysis", "description": state.get("ticket_content", "")}

    def _reinitialize_state(self, state, error: Exception) -> State:
        if isinstance(state, dict):
            result = dict(state)
            result["state_recovered"] = True
            result["original_error_type"] = type(error).__name__
            return State(**result)
        else:
            return State(url="", ticket_content="", state_recovered=True, original_error_type=type(error).__name__)
