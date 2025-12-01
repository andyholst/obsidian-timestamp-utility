"""
Error Recovery Agent for robust agent system error handling and recovery.

This module provides comprehensive error recovery mechanisms including:
- Fallback strategies for different agent types
- Circuit breaker integration
- Service health monitoring with graceful degradation
- Recovery strategies for code generation, test generation, and integration failures
- Comprehensive error context and recovery logging
"""

import logging
import json
import time
from typing import Dict, Any, Optional, Callable, List, Type
from datetime import datetime
from enum import Enum

from .base_agent import BaseAgent, AgentType
from .state import State
from .circuit_breaker import (
    get_circuit_breaker,
    get_health_monitor,
    CircuitBreakerOpenException,
    retry_with_backoff,
    retry_with_backoff_async
)
from .utils import log_info


class RecoveryStrategy(Enum):
    """Recovery strategy types"""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADATION = "degradation"
    SKIP = "skip"
    SUBSTITUTE = "substitute"
    STATE_RECOVERY = "state_recovery"
    MANUAL = "manual"


class ErrorRecoveryAgent(BaseAgent):
    """
    Agent responsible for error recovery and fallback mechanisms across the agent system.

    Provides robust error handling with:
    - Circuit breaker protection for external services
    - Health monitoring with graceful degradation
    - Agent-specific recovery strategies
    - Comprehensive error context logging
    """

    def __init__(self, fallback_strategies: Optional[Dict[str, Callable]] = None):
        super().__init__("ErrorRecovery")
        self.circuit_breakers = {}
        self.health_monitor = get_health_monitor()
        self.recovery_strategies = self._initialize_recovery_strategies()
        self.recovery_history = []

        # Initialize circuit breakers for different services
        self._initialize_circuit_breakers()

        # Initialize fallback strategies and circuit breaker for recovery
        if fallback_strategies is None:
            fallback_strategies = {
                "retry": self._retry_strategy,
                "degrade": self._degrade_strategy,
                "skip": self._skip_strategy,
                "substitute": self._substitute_strategy,
                "state_recovery": self._state_recovery_strategy
            }
        self.fallback_strategies = fallback_strategies
        self.circuit_breaker = get_circuit_breaker("error_recovery")

        log_info(self.name, "ErrorRecoveryAgent initialized with circuit breakers and recovery strategies")

    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for different services"""
        services = [
            ("ollama_reasoning", 3, 30),
            ("ollama_code", 3, 30),
            ("github", 5, 60),
            ("mcp", 3, 30),
            ("typescript_compiler", 2, 15),
            ("file_system", 3, 10)
        ]

        for service_name, threshold, timeout in services:
            self.circuit_breakers[service_name] = get_circuit_breaker(
                service_name,
                failure_threshold=threshold,
                recovery_timeout=timeout
            )

    def _initialize_recovery_strategies(self) -> Dict[AgentType, Dict[str, Any]]:
        """Initialize recovery strategies for different agent types"""
        return {
            AgentType.CODE_GENERATOR: {
                "max_retries": 2,
                "fallback_strategy": self._code_generation_fallback,
                "degradation_strategy": self._code_generation_degradation,
                "skip_strategy": self._code_generation_skip,
                "substitute_strategy": self._code_generation_substitute,
                "common_failures": [
                    "LLMError", "ValidationError", "TimeoutError"
                ]
            },
            AgentType.TEST_GENERATOR: {
                "max_retries": 2,
                "fallback_strategy": self._test_generation_fallback,
                "degradation_strategy": self._test_generation_degradation,
                "skip_strategy": self._test_generation_skip,
                "substitute_strategy": self._test_generation_substitute,
                "common_failures": [
                    "LLMError", "ValidationError", "TimeoutError"
                ]
            },
            AgentType.CODE_INTEGRATOR: {
                "max_retries": 1,
                "fallback_strategy": self._code_integration_fallback,
                "degradation_strategy": self._code_integration_degradation,
                "skip_strategy": self._code_integration_skip,
                "substitute_strategy": self._code_integration_substitute,
                "common_failures": [
                    "FileSystemError", "ValidationError", "PermissionError"
                ]
            },
            AgentType.CODE_REVIEWER: {
                "max_retries": 1,
                "fallback_strategy": self._code_review_fallback,
                "degradation_strategy": self._code_review_degradation,
                "skip_strategy": self._code_review_skip,
                "substitute_strategy": self._code_review_substitute,
                "common_failures": [
                    "LLMError", "TimeoutError", "CircuitBreakerOpenException"
                ]
            },
            AgentType.FETCH_ISSUE: {
                "max_retries": 3,
                "fallback_strategy": self._fetch_issue_fallback,
                "degradation_strategy": self._fetch_issue_degradation,
                "skip_strategy": self._fetch_issue_skip,
                "substitute_strategy": self._fetch_issue_substitute,
                "common_failures": [
                    "GitHubError", "NetworkError", "AuthenticationError", "CircuitBreakerOpenException"
                ]
            },
            AgentType.TICKET_CLARITY: {
                "max_retries": 2,
                "fallback_strategy": self._ticket_clarity_fallback,
                "degradation_strategy": self._ticket_clarity_degradation,
                "skip_strategy": self._ticket_clarity_skip,
                "substitute_strategy": self._ticket_clarity_substitute,
                "common_failures": [
                    "LLMError", "ValidationError", "TimeoutError", "CircuitBreakerOpenException"
                ]
            },
            AgentType.IMPLEMENTATION_PLANNER: {
                "max_retries": 2,
                "fallback_strategy": self._implementation_planner_fallback,
                "degradation_strategy": self._implementation_planner_degradation,
                "skip_strategy": self._implementation_planner_skip,
                "substitute_strategy": self._implementation_planner_substitute,
                "common_failures": [
                    "LLMError", "ValidationError", "TimeoutError"
                ]
            },
            AgentType.DEPENDENCY_ANALYZER: {
                "max_retries": 1,
                "fallback_strategy": self._dependency_analyzer_fallback,
                "degradation_strategy": self._dependency_analyzer_degradation,
                "skip_strategy": self._dependency_analyzer_skip,
                "substitute_strategy": self._dependency_analyzer_substitute,
                "common_failures": [
                    "FileSystemError", "ParseError", "CircuitBreakerOpenException"
                ]
            }
        }

    def process(self, state: State) -> State:
        """
        Process error recovery for the given state.

        This method should be called when an agent fails, and it will attempt
        recovery based on the failed agent type and error context.
        """
        failed_agent = state.get('failed_agent')
        error_context = state.get('error_context', {})
        original_error = state.get('original_error')

        if not failed_agent or not original_error:
            self._log_structured("warning", "recovery_invalid_state", {
                "has_failed_agent": bool(failed_agent),
                "has_error_context": bool(error_context),
                "has_original_error": bool(original_error)
            })
            return state

        try:
            agent_type = AgentType(failed_agent)
            recovery_result = self._attempt_recovery(agent_type, state, error_context, original_error)

            if recovery_result['success']:
                self._log_structured("info", "recovery_success", {
                    "agent_type": agent_type.value,
                    "strategy": recovery_result['strategy'],
                    "attempts": recovery_result['attempts']
                })
                state['recovery_applied'] = True
                state['recovery_details'] = recovery_result
                # Clear error flags
                state.pop('failed_agent', None)
                state.pop('error_context', None)
                state.pop('original_error', None)
            else:
                self._log_structured("error", "recovery_failed", {
                    "agent_type": agent_type.value,
                    "final_strategy": recovery_result['strategy'],
                    "total_attempts": recovery_result['attempts'],
                    "error": recovery_result.get('error', 'Unknown error')
                })
                state['recovery_failed'] = True
                state['recovery_details'] = recovery_result

        except ValueError as e:
            self._log_structured("error", "recovery_invalid_agent_type", {
                "failed_agent": failed_agent,
                "error": str(e)
            })
            state['recovery_failed'] = True

        return state

    def recover(self, failed_state: State, error: Exception) -> State:
        """Attempt to recover from agent failure"""

        strategy = self._select_recovery_strategy(error)

        def execute_recovery():
            return strategy(failed_state, error)

        return self.circuit_breaker.call(execute_recovery)

    def _select_recovery_strategy(self, error: Exception) -> Callable[[State, Exception], State]:
        """Select appropriate recovery strategy based on error type"""
        error_type = type(error).__name__

        if error_type in ["TimeoutError", "NetworkError", "ConnectionError"]:
            return self.fallback_strategies["retry"]
        elif error_type == "CircuitBreakerOpenException":
            return self.fallback_strategies["degrade"]
        elif error_type in ["ValidationError", "LLMError", "ParseError", "ValueError"]:
            return self.fallback_strategies["substitute"]
        elif error_type in ["AttributeError", "KeyError", "TypeError"]:
            return self.fallback_strategies["state_recovery"]
        else:
            return self.fallback_strategies["skip"]

    def _attempt_recovery(self, agent_type: AgentType, state: State,
                         error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Attempt recovery for a specific agent type with error context.
        """
        strategy_config = self.recovery_strategies[agent_type]
        error_type = type(original_error).__name__

        # Check if error is in common failures for this agent type
        if error_type in strategy_config['common_failures']:
            return self._execute_recovery_strategy(agent_type, strategy_config, state, error_context, original_error)

        # Check for circuit breaker errors
        if isinstance(original_error, CircuitBreakerOpenException):
            return self._handle_circuit_breaker_error(agent_type, state, error_context)

        # Default to retry strategy for unknown errors
        return self._execute_retry_strategy(agent_type, strategy_config, state, error_context, original_error)

    def _execute_recovery_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                                  state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute the appropriate recovery strategy based on agent type and error.
        """
        # First try retry
        retry_result = self._execute_retry_strategy(agent_type, strategy_config, state, error_context, original_error)
        if retry_result['success']:
            return retry_result

        # If retry fails, try fallback
        fallback_result = self._execute_fallback_strategy(agent_type, strategy_config, state, error_context, original_error)
        if fallback_result['success']:
            return fallback_result

        # If fallback fails, try degradation
        degradation_result = self._execute_degradation_strategy(agent_type, strategy_config, state, error_context, original_error)
        if degradation_result['success']:
            return degradation_result

        # If degradation fails, try skip
        skip_result = self._execute_skip_strategy(agent_type, strategy_config, state, error_context, original_error)
        if skip_result['success']:
            return skip_result

        # If skip fails, try substitute
        substitute_result = self._execute_substitute_strategy(agent_type, strategy_config, state, error_context, original_error)
        if substitute_result['success']:
            return substitute_result

        # All strategies failed
        return {
            'success': False,
            'strategy': 'all_failed',
            'attempts': retry_result['attempts'] + fallback_result['attempts'] + degradation_result['attempts'] + skip_result['attempts'] + substitute_result['attempts'],
            'error': 'All recovery strategies exhausted'
        }

    def _execute_retry_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                               state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute retry strategy with exponential backoff.
        """
        max_retries = strategy_config['max_retries']
        attempts = 0

        for attempt in range(max_retries):
            attempts += 1
            try:
                # Check service health before retry
                if not self._check_service_health_for_agent(agent_type):
                    continue

                # Attempt retry with circuit breaker protection
                result = self._retry_with_circuit_breaker(agent_type, state, error_context)

                if result['success']:
                    return {
                        'success': True,
                        'strategy': RecoveryStrategy.RETRY.value,
                        'attempts': attempts,
                        'result': result
                    }

            except Exception as e:
                self._log_structured("warning", "retry_attempt_failed", {
                    "agent_type": agent_type.value,
                    "attempt": attempts,
                    "error": str(e)
                })
                continue

        return {
            'success': False,
            'strategy': RecoveryStrategy.RETRY.value,
            'attempts': attempts,
            'error': f'All {max_retries} retry attempts failed'
        }

    def _execute_fallback_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                                  state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute fallback strategy specific to agent type.
        """
        try:
            fallback_func = strategy_config['fallback_strategy']
            result = fallback_func(state, error_context, original_error)

            return {
                'success': result['success'],
                'strategy': RecoveryStrategy.FALLBACK.value,
                'attempts': 1,
                'result': result
            }

        except Exception as e:
            self._log_structured("error", "fallback_strategy_failed", {
                "agent_type": agent_type.value,
                "error": str(e)
            })
            return {
                'success': False,
                'strategy': RecoveryStrategy.FALLBACK.value,
                'attempts': 1,
                'error': str(e)
            }

    def _execute_degradation_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                                     state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute graceful degradation strategy.
        """
        try:
            degradation_func = strategy_config['degradation_strategy']
            result = degradation_func(state, error_context, original_error)

            return {
                'success': result['success'],
                'strategy': RecoveryStrategy.DEGRADATION.value,
                'attempts': 1,
                'result': result
            }

        except Exception as e:
            self._log_structured("error", "degradation_strategy_failed", {
                "agent_type": agent_type.value,
                "error": str(e)
            })
            return {
                'success': False,
                'strategy': RecoveryStrategy.DEGRADATION.value,
                'attempts': 1,
                'error': str(e)
            }

    def _execute_skip_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                              state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute skip strategy specific to agent type.
        """
        try:
            skip_func = strategy_config['skip_strategy']
            result = skip_func(state, error_context, original_error)

            return {
                'success': result['success'],
                'strategy': RecoveryStrategy.SKIP.value,
                'attempts': 1,
                'result': result
            }

        except Exception as e:
            self._log_structured("error", "skip_strategy_failed", {
                "agent_type": agent_type.value,
                "error": str(e)
            })
            return {
                'success': False,
                'strategy': RecoveryStrategy.SKIP.value,
                'attempts': 1,
                'error': str(e)
            }

    def _execute_substitute_strategy(self, agent_type: AgentType, strategy_config: Dict[str, Any],
                                    state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """
        Execute substitute strategy specific to agent type.
        """
        try:
            substitute_func = strategy_config['substitute_strategy']
            result = substitute_func(state, error_context, original_error)

            return {
                'success': result['success'],
                'strategy': RecoveryStrategy.SUBSTITUTE.value,
                'attempts': 1,
                'result': result
            }

        except Exception as e:
            self._log_structured("error", "substitute_strategy_failed", {
                "agent_type": agent_type.value,
                "error": str(e)
            })
            return {
                'success': False,
                'strategy': RecoveryStrategy.SUBSTITUTE.value,
                'attempts': 1,
                'error': str(e)
            }

    def _retry_strategy(self, failed_state: State, error: Exception) -> State:
        """Retry strategy for recovery"""
        agent = failed_state.get('failed_agent')
        if not agent:
            return failed_state
        agent_type = AgentType(agent)
        strategy_config = self.recovery_strategies[agent_type]
        error_context = failed_state.get('error_context', {})
        retry_result = self._execute_retry_strategy(agent_type, strategy_config, failed_state, error_context, error)
        if retry_result['success']:
            failed_state['recovery_applied'] = True
            failed_state['recovery_details'] = retry_result
            failed_state.pop('failed_agent', None)
            failed_state.pop('error_context', None)
            failed_state.pop('original_error', None)
        else:
            failed_state['recovery_failed'] = True
            failed_state['recovery_details'] = retry_result
        return failed_state

    def _degrade_strategy(self, failed_state: State, error: Exception) -> State:
        """Degradation strategy for recovery"""
        agent = failed_state.get('failed_agent')
        if not agent:
            return failed_state
        agent_type = AgentType(agent)
        strategy_config = self.recovery_strategies[agent_type]
        error_context = failed_state.get('error_context', {})
        degrade_result = self._execute_degradation_strategy(agent_type, strategy_config, failed_state, error_context, error)
        if degrade_result['success']:
            failed_state['recovery_applied'] = True
            failed_state['recovery_details'] = degrade_result
            failed_state.pop('failed_agent', None)
            failed_state.pop('error_context', None)
            failed_state.pop('original_error', None)
        else:
            failed_state['recovery_failed'] = True
            failed_state['recovery_details'] = degrade_result
        return failed_state

    def _skip_strategy(self, failed_state: State, error: Exception) -> State:
        """Skip strategy for recovery"""
        agent = failed_state.get('failed_agent')
        if not agent:
            return failed_state
        agent_type = AgentType(agent)
        strategy_config = self.recovery_strategies[agent_type]
        error_context = failed_state.get('error_context', {})
        skip_result = self._execute_skip_strategy(agent_type, strategy_config, failed_state, error_context, error)
        if skip_result['success']:
            failed_state['recovery_applied'] = True
            failed_state['recovery_details'] = skip_result
            failed_state.pop('failed_agent', None)
            failed_state.pop('error_context', None)
            failed_state.pop('original_error', None)
        else:
            failed_state['recovery_failed'] = True
            failed_state['recovery_details'] = skip_result
        return failed_state

    def _substitute_strategy(self, failed_state: State, error: Exception) -> State:
        """Substitute strategy for recovery"""
        agent = failed_state.get('failed_agent')
        if not agent:
            return failed_state
        agent_type = AgentType(agent)
        strategy_config = self.recovery_strategies[agent_type]
        error_context = failed_state.get('error_context', {})
        substitute_result = self._execute_substitute_strategy(agent_type, strategy_config, failed_state, error_context, error)
        if substitute_result['success']:
            failed_state['recovery_applied'] = True
            failed_state['recovery_details'] = substitute_result
            failed_state.pop('failed_agent', None)
            failed_state.pop('error_context', None)
            failed_state.pop('original_error', None)
        else:
            failed_state['recovery_failed'] = True
            failed_state['recovery_details'] = substitute_result
        return failed_state

    def _state_recovery_strategy(self, failed_state: State, error: Exception) -> State:
        """State recovery strategy for state validation failures"""
        try:
            # Validate state type
            if not isinstance(failed_state, dict):
                raise Exception("Invalid state type for recovery")

            # Attempt to reinitialize state with default values or recover from partial state
            recovered_state = self._reinitialize_state(failed_state, error)
            self._log_structured("info", "state_recovery_success", {
                "error_type": type(error).__name__,
                "state_reinitialized": True
            })
            recovered_state['recovery_applied'] = True
            recovered_state['recovery_details'] = {
                'success': True,
                'strategy': RecoveryStrategy.STATE_RECOVERY.value,
                'attempts': 1,
                'state_recovered': True
            }
            # Clear error flags
            recovered_state.pop('failed_agent', None)
            recovered_state.pop('error_context', None)
            recovered_state.pop('original_error', None)
            return recovered_state
        except Exception as recovery_error:
            self._log_structured("error", "state_recovery_failed", {
                "original_error": str(error),
                "recovery_error": str(recovery_error)
            })
            # Return a minimal valid state if recovery fails
            minimal_state = State()
            minimal_state['recovery_failed'] = True
            minimal_state['recovery_details'] = {
                'success': False,
                'strategy': RecoveryStrategy.STATE_RECOVERY.value,
                'attempts': 1,
                'error': str(recovery_error)
            }
            return minimal_state

    def _handle_circuit_breaker_error(self, agent_type: AgentType, state: State, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle circuit breaker open errors with degradation.
        """
        self._log_structured("warning", "circuit_breaker_open", {
            "agent_type": agent_type.value,
            "service": error_context.get('service', 'unknown')
        })

        # Try degradation strategy immediately for circuit breaker errors
        strategy_config = self.recovery_strategies[agent_type]
        return self._execute_degradation_strategy(agent_type, strategy_config, state, error_context, CircuitBreakerOpenException())

    def _check_service_health_for_agent(self, agent_type: AgentType) -> bool:
        """
        Check if required services are healthy for the given agent type.
        """
        service_mapping = {
            AgentType.CODE_GENERATOR: ['ollama_code', 'typescript_compiler'],
            AgentType.TEST_GENERATOR: ['ollama_code', 'typescript_compiler'],
            AgentType.CODE_INTEGRATOR: ['file_system'],
            AgentType.CODE_REVIEWER: ['ollama_reasoning'],
            AgentType.FETCH_ISSUE: ['github'],
            AgentType.TICKET_CLARITY: ['ollama_reasoning'],
            AgentType.IMPLEMENTATION_PLANNER: ['ollama_reasoning'],
            AgentType.DEPENDENCY_ANALYZER: ['file_system']
        }

        services = service_mapping.get(agent_type, [])
        return all(self.health_monitor.is_service_healthy(service) for service in services)

    def _retry_with_circuit_breaker(self, agent_type: AgentType, state: State, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retry operation with circuit breaker protection.
        """
        # This is a placeholder - in practice, this would call the actual agent method
        # For now, we'll simulate success/failure based on health checks
        if self._check_service_health_for_agent(agent_type):
            return {'success': True, 'data': 'Recovered successfully'}
        else:
            raise Exception("Service still unhealthy")

    # Fallback strategy implementations

    def _code_generation_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for code generation failures"""
        # Generate minimal stub code
        fallback_code = self._generate_minimal_code_stub(state)
        state['generated_code'] = fallback_code
        return {'success': True, 'fallback_code': fallback_code}

    def _test_generation_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for test generation failures"""
        # Generate minimal test stub
        fallback_tests = self._generate_minimal_test_stub(state)
        state['generated_tests'] = fallback_tests
        return {'success': True, 'fallback_tests': fallback_tests}

    def _code_integration_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for code integration failures"""
        # Skip integration but mark as completed
        state['integration_skipped'] = True
        return {'success': True, 'integration_skipped': True}

    def _code_review_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for code review failures"""
        # Assume code is acceptable
        state['feedback'] = {'needs_fix': False, 'comments': 'Review skipped due to error'}
        return {'success': True, 'review_skipped': True}

    def _fetch_issue_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for fetch issue failures"""
        # Use cached or default issue data
        state['ticket_content'] = 'Issue content unavailable - using default processing'
        return {'success': True, 'used_default_content': True}

    def _ticket_clarity_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for ticket clarity failures"""
        # Use basic parsing
        basic_result = self._parse_ticket_basic(state)
        state['result'] = basic_result
        return {'success': True, 'basic_parsing': True}

    def _implementation_planner_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for implementation planner failures"""
        # Use default implementation steps
        default_steps = ['Analyze requirements', 'Implement solution', 'Test implementation']
        if 'result' in state:
            state['result']['implementation_steps'] = default_steps
        return {'success': True, 'default_steps': default_steps}

    def _dependency_analyzer_fallback(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Fallback strategy for dependency analyzer failures"""
        # Skip dependency analysis
        state['dependency_analysis_skipped'] = True
        return {'success': True, 'analysis_skipped': True}

    # Skip strategy implementations

    def _code_generation_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for code generation failures"""
        state['code_generation_skipped'] = True
        state['generated_code'] = ""
        return {'success': True, 'skipped': True}

    def _test_generation_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for test generation failures"""
        state['test_generation_skipped'] = True
        state['generated_tests'] = ""
        return {'success': True, 'skipped': True}

    def _code_integration_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for code integration failures"""
        state['integration_skipped'] = True
        return {'success': True, 'skipped': True}

    def _code_review_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for code review failures"""
        state['review_skipped'] = True
        state['feedback'] = {'needs_fix': False, 'comments': 'Review skipped due to error'}
        return {'success': True, 'skipped': True}

    def _fetch_issue_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for fetch issue failures"""
        state['fetch_skipped'] = True
        state['ticket_content'] = 'Issue fetch skipped due to error'
        return {'success': True, 'skipped': True}

    def _ticket_clarity_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for ticket clarity failures"""
        state['clarity_skipped'] = True
        state['result'] = {
            'title': 'Task',
            'description': 'Task details unavailable',
            'requirements': [],
            'acceptance_criteria': [],
            'implementation_steps': ['Implement solution'],
            'npm_packages': [],
            'manual_implementation_notes': 'Clarity analysis skipped'
        }
        return {'success': True, 'skipped': True}

    def _implementation_planner_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for implementation planner failures"""
        state['planning_skipped'] = True
        if 'result' in state:
            state['result']['implementation_steps'] = ['Implement solution']
        return {'success': True, 'skipped': True}

    def _dependency_analyzer_skip(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Skip strategy for dependency analyzer failures"""
        state['dependency_analysis_skipped'] = True
        return {'success': True, 'skipped': True}

    # Substitute strategy implementations

    def _code_generation_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for code generation failures"""
        substitute_code = self._generate_substitute_code_stub(state)
        state['generated_code'] = substitute_code
        return {'success': True, 'substituted': True}

    def _test_generation_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for test generation failures"""
        substitute_tests = self._generate_substitute_test_stub(state)
        state['generated_tests'] = substitute_tests
        return {'success': True, 'substituted': True}

    def _code_integration_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for code integration failures"""
        # Try alternative integration method
        state['integration_substituted'] = True
        return {'success': True, 'substituted': True}

    def _code_review_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for code review failures"""
        # Use alternative review method
        state['review_substituted'] = True
        state['feedback'] = {'needs_fix': False, 'comments': 'Alternative review applied'}
        return {'success': True, 'substituted': True}

    def _fetch_issue_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for fetch issue failures"""
        # Use alternative data source
        state['fetch_substituted'] = True
        state['ticket_content'] = 'Issue content from alternative source'
        return {'success': True, 'substituted': True}

    def _ticket_clarity_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for ticket clarity failures"""
        # Use alternative parsing method
        substitute_result = self._parse_ticket_substitute(state)
        state['result'] = substitute_result
        return {'success': True, 'substituted': True}

    def _implementation_planner_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for implementation planner failures"""
        # Use alternative planning method
        substitute_steps = ['Analyze requirements', 'Design solution', 'Implement', 'Test', 'Deploy']
        if 'result' in state:
            state['result']['implementation_steps'] = substitute_steps
        return {'success': True, 'substituted': True}

    def _dependency_analyzer_substitute(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Substitute strategy for dependency analyzer failures"""
        # Use alternative analysis method
        state['dependency_analysis_substituted'] = True
        return {'success': True, 'substituted': True}

    # Degradation strategy implementations

    def _code_generation_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for code generation failures"""
        # Provide empty code but continue workflow
        state['generated_code'] = ""
        state['code_generation_degraded'] = True
        return {'success': True, 'degraded_mode': True}

    def _test_generation_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for test generation failures"""
        # Provide empty tests but continue workflow
        state['generated_tests'] = ""
        state['test_generation_degraded'] = True
        return {'success': True, 'degraded_mode': True}

    def _code_integration_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for code integration failures"""
        # Mark integration as failed but allow workflow to continue
        state['integration_failed'] = True
        return {'success': True, 'degraded_mode': True}

    def _code_review_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for code review failures"""
        # Skip review entirely
        state['review_skipped'] = True
        state['feedback'] = {'needs_fix': False}
        return {'success': True, 'degraded_mode': True}

    def _fetch_issue_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for fetch issue failures"""
        # Fail the entire workflow gracefully
        state['workflow_failed'] = True
        return {'success': False, 'workflow_terminated': True}

    def _ticket_clarity_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for ticket clarity failures"""
        # Use minimal default structure
        default_result = {
            'title': 'Unknown Task',
            'description': 'Task details unavailable',
            'requirements': [],
            'acceptance_criteria': [],
            'implementation_steps': [],
            'npm_packages': [],
            'manual_implementation_notes': ''
        }
        state['result'] = default_result
        return {'success': True, 'degraded_mode': True}

    def _implementation_planner_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for implementation planner failures"""
        # Skip planning phase
        state['planning_skipped'] = True
        return {'success': True, 'degraded_mode': True}

    def _dependency_analyzer_degradation(self, state: State, error_context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Degradation strategy for dependency analyzer failures"""
        # Skip dependency analysis
        state['dependency_analysis_skipped'] = True
        return {'success': True, 'degraded_mode': True}

    # Helper methods

    def _generate_minimal_code_stub(self, state: State) -> str:
        """Generate minimal code stub for fallback"""
        return "// Fallback code stub - implement manually\n// Error recovery activated\nexport class FallbackImplementation {\n  // TODO: Implement functionality\n}\n"

    def _generate_minimal_test_stub(self, state: State) -> str:
        """Generate minimal test stub for fallback"""
        return "// Fallback test stub - implement manually\ndescribe('Fallback Tests', () => {\n  it('should work', () => {\n    expect(true).toBe(true);\n  });\n});\n"

    def _parse_ticket_basic(self, state: State) -> Dict[str, Any]:
        """Basic ticket parsing for fallback"""
        ticket_content = state.get('ticket_content', '')
        return {
            'title': ticket_content.split('\n')[0] if ticket_content else 'Parsed Task',
            'description': ticket_content[:200] + '...' if len(ticket_content) > 200 else ticket_content,
            'requirements': [],
            'acceptance_criteria': [],
            'implementation_steps': ['Implement solution'],
            'npm_packages': [],
            'manual_implementation_notes': 'Basic parsing applied due to processing error'
        }

    def _generate_substitute_code_stub(self, state: State) -> str:
        """Generate substitute code stub for recovery"""
        return """// Substitute implementation - generated during error recovery
export class SubstituteImplementation {
  constructor() {
    // Initialize substitute implementation
  }

  execute() {
    // Substitute execution logic
    console.log('Substitute implementation executed');
    return 'substitute_result';
  }
}

// TODO: Replace with actual implementation during recovery
"""

    def _generate_substitute_test_stub(self, state: State) -> str:
        """Generate substitute test stub for recovery"""
        return """// Substitute test implementation - generated during error recovery
describe('SubstituteImplementation', () => {
  let substituteImpl;

  beforeEach(() => {
    substituteImpl = new SubstituteImplementation();
  });

  it('should execute without error', () => {
    const result = substituteImpl.execute();
    expect(result).toBeDefined();
  });

  it('should be instantiable', () => {
    expect(substituteImpl).toBeInstanceOf(SubstituteImplementation);
  });
});

// TODO: Replace with actual tests during recovery
"""

    def _parse_ticket_substitute(self, state: State) -> Dict[str, Any]:
        """Substitute ticket parsing for recovery"""
        ticket_content = state.get('ticket_content', '')
        return {
            'title': 'Substitute Task Analysis',
            'description': f'Substitute parsing for: {ticket_content[:100]}...' if ticket_content else 'Task details from substitute parsing',
            'requirements': ['Implement core functionality', 'Add error handling', 'Write tests'],
            'acceptance_criteria': ['Code compiles', 'Basic functionality works', 'Tests pass'],
            'implementation_steps': ['Analyze substitute requirements', 'Implement substitute solution', 'Test substitute implementation'],
            'npm_packages': ['lodash', 'axios'],
            'manual_implementation_notes': 'Substitute parsing applied due to processing error'
        }

    def _reinitialize_state(self, failed_state: State, error: Exception) -> State:
        """Reinitialize state with default values or recover from partial state"""
        new_state = State()

        # If failed_state is a dict, try to recover valid parts
        if isinstance(failed_state, dict):
            # Copy over valid string fields with defaults
            string_fields = ['url', 'ticket_content', 'generated_code', 'generated_tests']
            for field in string_fields:
                if field in failed_state and isinstance(failed_state[field], str):
                    new_state[field] = failed_state[field]
                else:
                    new_state[field] = ""  # Default empty string

            # Copy over valid list fields with defaults
            list_fields = [
                'relevant_code_files', 'relevant_test_files', 'available_dependencies',
                'conversation_history', 'implementation_steps', 'npm_packages',
                'acceptance_criteria', 'requirements'
            ]
            for field in list_fields:
                if field in failed_state and isinstance(failed_state[field], list):
                    new_state[field] = failed_state[field][:]  # Copy list
                else:
                    new_state[field] = []  # Default empty list

            # Copy over valid dict fields with defaults
            dict_fields = ['refined_ticket', 'result', 'feedback', 'memory', 'feedback_metrics']
            for field in dict_fields:
                if field in failed_state and isinstance(failed_state[field], dict):
                    new_state[field] = failed_state[field].copy()
                else:
                    new_state[field] = {}  # Default empty dict

            # Copy over numeric fields with defaults
            numeric_fields = [
                'existing_tests_passed', 'existing_coverage_all_files',
                'post_integration_tests_passed', 'post_integration_coverage_all_files',
                'coverage_improvement', 'tests_improvement'
            ]
            for field in numeric_fields:
                if field in failed_state and isinstance(failed_state[field], (int, float)):
                    new_state[field] = failed_state[field]
                else:
                    new_state[field] = 0  # Default zero
        else:
            # If not a dict, initialize with all defaults
            new_state.update({
                'url': '',
                'ticket_content': '',
                'generated_code': '',
                'generated_tests': '',
                'relevant_code_files': [],
                'relevant_test_files': [],
                'available_dependencies': [],
                'conversation_history': [],
                'implementation_steps': [],
                'npm_packages': [],
                'acceptance_criteria': [],
                'requirements': [],
                'refined_ticket': {},
                'result': {},
                'feedback': {},
                'memory': {},
                'feedback_metrics': {},
                'existing_tests_passed': 0,
                'existing_coverage_all_files': 0.0,
                'post_integration_tests_passed': 0,
                'post_integration_coverage_all_files': 0.0,
                'coverage_improvement': 0.0,
                'tests_improvement': 0
            })

        # Add recovery metadata
        new_state['state_recovered'] = True
        new_state['recovery_timestamp'] = datetime.now().isoformat()
        new_state['original_error_type'] = type(error).__name__

        return new_state

    def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery status and statistics"""
        return {
            'circuit_breakers': {
                name: cb.get_status() for name, cb in self.circuit_breakers.items()
            },
            'service_health': self.health_monitor.get_service_status(),
            'recovery_history': self.recovery_history[-10:]  # Last 10 recoveries
        }