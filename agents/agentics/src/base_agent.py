import logging
from typing import Optional
from langchain_core.runnables import RunnableConfig
import json
from datetime import datetime
from typing import Dict, Any
from langchain_core.runnables import Runnable
from enum import Enum
from .state import CodeGenerationState
from dataclasses import asdict, is_dataclass
from .config import LOGGER_LEVEL
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from .monitoring import structured_log, track_agent_execution, record_circuit_breaker_state


class AgentType(Enum):
    """Agent types for recovery strategies"""
    CODE_GENERATOR = "code_generator"
    TEST_GENERATOR = "test_generator"
    CODE_INTEGRATOR = "code_integrator"
    CODE_REVIEWER = "code_reviewer"
    DEPENDENCY_ANALYZER = "dependency_analyzer"
    FETCH_ISSUE = "fetch_issue"
    TICKET_CLARITY = "ticket_clarity"
    IMPLEMENTATION_PLANNER = "implementation_planner"


class BaseAgent(Runnable[CodeGenerationState, CodeGenerationState]):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOGGER_LEVEL)
        self.agent_type = self._get_agent_type()
        self.circuit_breaker = get_circuit_breaker(self.name, **self._get_circuit_breaker_config())
        self.monitor = structured_log(name)
        self.monitor.setLevel(LOGGER_LEVEL)

    def _get_agent_type(self) -> AgentType:
        """Map agent name to AgentType enum."""
        name_to_type = {
            "CodeGenerator": AgentType.CODE_GENERATOR,
            "TestGenerator": AgentType.TEST_GENERATOR,
            "CodeIntegrator": AgentType.CODE_INTEGRATOR,
            "CodeReviewer": AgentType.CODE_REVIEWER,
            "DependencyAnalyzer": AgentType.DEPENDENCY_ANALYZER,
            "FetchIssueAgent": AgentType.FETCH_ISSUE,
            "TicketClarityAgent": AgentType.TICKET_CLARITY,
            "ImplementationPlannerAgent": AgentType.IMPLEMENTATION_PLANNER,
            # Add more mappings as needed
        }
        return name_to_type.get(self.name, AgentType.CODE_GENERATOR)  # Default fallback

    def _get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get circuit breaker configuration based on agent type."""
        configs = {
            AgentType.CODE_GENERATOR: {"failure_threshold": 3, "recovery_timeout": 30},
            AgentType.TEST_GENERATOR: {"failure_threshold": 3, "recovery_timeout": 30},
            AgentType.CODE_INTEGRATOR: {"failure_threshold": 2, "recovery_timeout": 15},
            AgentType.CODE_REVIEWER: {"failure_threshold": 2, "recovery_timeout": 30},
            AgentType.DEPENDENCY_ANALYZER: {"failure_threshold": 2, "recovery_timeout": 15},
            AgentType.FETCH_ISSUE: {"failure_threshold": 5, "recovery_timeout": 60},
            AgentType.TICKET_CLARITY: {"failure_threshold": 3, "recovery_timeout": 30},
            AgentType.IMPLEMENTATION_PLANNER: {"failure_threshold": 3, "recovery_timeout": 30},
        }
        return configs.get(self.agent_type, {"failure_threshold": 5, "recovery_timeout": 60})  # Default

    def invoke(self, input: CodeGenerationState, config: Optional[RunnableConfig] = None) -> CodeGenerationState:
        return self(input)

    @track_agent_execution("base_agent")
    def __call__(self, state: CodeGenerationState) -> CodeGenerationState:
        self.monitor.info("agent_start", {"agent": self.name})
        try:
            state = self.circuit_breaker.call(self._monitored_process, state)
            self.monitor.info("agent_complete", {"agent": self.name})
            return state
        except CircuitBreakerOpenException as e:
            self.monitor.error("circuit_breaker_open", {"agent": self.name, "error": str(e)})
            raise
        except Exception as e:
            error_context = self._create_error_context(state, e)
            self.monitor.error("agent_error", error_context)
            raise

    def _monitored_process(self, state: CodeGenerationState) -> CodeGenerationState:
        """Monitored version of process method"""
        return self.process(state)

    def _log_structured(self, level: str, event: str, data: Dict[str, Any]):
        """Legacy method for backward compatibility - use self.monitor instead."""
        log_method = getattr(self.monitor, level.lower(), self.monitor.info)
        log_method(event, data)

    def _create_error_context(self, state: CodeGenerationState, exception: Exception) -> Dict[str, Any]:
        """Create detailed error context with state snapshot."""
        if is_dataclass(state):
            state_dict = asdict(state)
        else:
            state_dict = dict(state)
        return {
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "state_snapshot": {
                "url": state_dict.get("issue_url") or state_dict.get("url", ""),
                "ticket_content_length": len(str(state_dict.get("ticket_content") or "")),
                "result_keys": list((state_dict.get("result") or {}).keys()),
                "generated_code_length": len(str(state_dict.get("generated_code") or "")),
                "generated_tests_length": len(str(state_dict.get("generated_tests") or "")),
                "relevant_files_count": len(state_dict.get("relevant_code_files", []) or []) + len(state_dict.get("relevant_test_files", []) or [])
            },
            "traceback": None  # Could add full traceback if needed
        }

    def process(self, state: CodeGenerationState) -> CodeGenerationState:
        raise NotImplementedError("Subclasses must implement this method")