import pytest
import json
import os
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

# Set environment variables before importing
os.environ['PROJECT_ROOT'] = '/tmp'
os.environ['GITHUB_TOKEN'] = 'fake_token'

from src.error_recovery_agent import (
    ErrorRecoveryAgent,
    RecoveryStrategy,
    CircuitBreakerOpenException
)
from src.base_agent import AgentType
from src.state import State
from src.circuit_breaker import get_circuit_breaker, get_health_monitor


class LLMError(Exception):
    """Mock LLM Error for testing"""
    pass


class TestErrorRecoveryAgent:
    """Comprehensive unit tests for ErrorRecoveryAgent"""

    @pytest.fixture
    def mock_health_monitor(self):
        """Mock health monitor for testing"""
        with patch('src.error_recovery_agent.get_health_monitor') as mock_get_monitor:
            monitor = MagicMock()
            monitor.is_service_healthy.return_value = True
            mock_get_monitor.return_value = monitor
            yield monitor

    @pytest.fixture
    def mock_circuit_breaker(self):
        """Mock circuit breaker for testing"""
        with patch('src.error_recovery_agent.get_circuit_breaker') as mock_get_cb:
            cb = MagicMock()
            cb.call = MagicMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
            mock_get_cb.return_value = cb
            yield cb

    @pytest.fixture
    def error_recovery_agent(self, mock_health_monitor, mock_circuit_breaker):
        """Create ErrorRecoveryAgent instance with mocked dependencies"""
        return ErrorRecoveryAgent()

    @pytest.fixture
    def valid_failed_state(self):
        """Create a valid failed state for testing"""
        return State(
            failed_agent="code_generator",
            error_context={"service": "ollama_code", "attempt": 1},
            original_error=ValueError("LLM Error"),
            url="https://example.com",
            ticket_content="Test ticket",
            generated_code="",
            generated_tests=""
        )

    @pytest.fixture
    def invalid_failed_state(self):
        """Create an invalid failed state for testing"""
        return State(
            # Missing failed_agent
            error_context={"service": "ollama_code"},
            # Missing original_error
            url="https://example.com"
        )

    def test_initialization(self, mock_health_monitor, mock_circuit_breaker):
        """Test ErrorRecoveryAgent initialization"""
        agent = ErrorRecoveryAgent()

        assert agent.name == "ErrorRecovery"
        assert isinstance(agent.circuit_breakers, dict)
        assert isinstance(agent.recovery_strategies, dict)
        assert isinstance(agent.fallback_strategies, dict)
        assert agent.circuit_breaker is not None
        assert len(agent.recovery_strategies) == 8  # All agent types

        # Check circuit breakers were initialized for all services
        expected_services = [
            "ollama_reasoning", "ollama_code", "github", "mcp",
            "typescript_compiler", "file_system"
        ]
        for service in expected_services:
            assert service in agent.circuit_breakers

    def test_initialization_with_custom_strategies(self, mock_health_monitor, mock_circuit_breaker):
        """Test initialization with custom fallback strategies"""
        custom_strategies = {
            "custom_retry": MagicMock(),
            "custom_degrade": MagicMock()
        }

        agent = ErrorRecoveryAgent(fallback_strategies=custom_strategies)

        assert agent.fallback_strategies == custom_strategies

    def test_process_with_invalid_state(self, error_recovery_agent, invalid_failed_state):
        """Test process method with invalid state (missing required fields)"""
        result = error_recovery_agent.process(invalid_failed_state)

        assert result == invalid_failed_state
        assert 'recovery_failed' not in result

    def test_process_with_valid_state_success(self, error_recovery_agent, valid_failed_state):
        """Test process method with valid state that recovers successfully"""
        with patch.object(error_recovery_agent, '_attempt_recovery') as mock_attempt:
            mock_attempt.return_value = {
                'success': True,
                'strategy': RecoveryStrategy.RETRY.value,
                'attempts': 1
            }

            result = error_recovery_agent.process(valid_failed_state)

            assert result['recovery_applied'] == True
            assert result['recovery_details']['success'] == True
            assert 'failed_agent' not in result
            assert 'error_context' not in result
            assert 'original_error' not in result

    def test_process_with_valid_state_failure(self, error_recovery_agent, valid_failed_state):
        """Test process method with valid state that fails to recover"""
        with patch.object(error_recovery_agent, '_attempt_recovery') as mock_attempt:
            mock_attempt.return_value = {
                'success': False,
                'strategy': RecoveryStrategy.RETRY.value,
                'attempts': 3,
                'error': 'All retries failed'
            }

            result = error_recovery_agent.process(valid_failed_state)

            assert result['recovery_failed'] == True
            assert result['recovery_details']['success'] == False

    def test_process_with_invalid_agent_type(self, error_recovery_agent):
        """Test process method with invalid agent type"""
        invalid_state = State(
            failed_agent="invalid_agent_type",
            error_context={},
            original_error=ValueError("Test error")
        )

        result = error_recovery_agent.process(invalid_state)

        assert result['recovery_failed'] == True

    def test_recover_method(self, error_recovery_agent, valid_failed_state):
        """Test recover method with circuit breaker protection"""
        with patch.object(error_recovery_agent, '_select_recovery_strategy') as mock_select, \
             patch.object(error_recovery_agent.circuit_breaker, 'call') as mock_cb_call:
            mock_strategy = MagicMock(return_value=valid_failed_state)
            mock_select.return_value = mock_strategy
            mock_cb_call.return_value = valid_failed_state

            result = error_recovery_agent.recover(valid_failed_state, ValueError("Test"))

            # Verify that _select_recovery_strategy was called with a ValueError
            mock_select.assert_called_once()
            call_args = mock_select.call_args[0]
            assert len(call_args) == 1
            assert isinstance(call_args[0], ValueError)
            assert str(call_args[0]) == "Test"

            mock_cb_call.assert_called_once()
            assert result == valid_failed_state

    def test_select_recovery_strategy_timeout_error(self, error_recovery_agent):
        """Test recovery strategy selection for TimeoutError"""
        strategy = error_recovery_agent._select_recovery_strategy(TimeoutError("Connection timeout"))

        assert strategy == error_recovery_agent.fallback_strategies["retry"]

    def test_select_recovery_strategy_network_error(self, error_recovery_agent):
        """Test recovery strategy selection for NetworkError"""
        strategy = error_recovery_agent._select_recovery_strategy(ConnectionError("Network error"))

        assert strategy == error_recovery_agent.fallback_strategies["retry"]

    def test_select_recovery_strategy_circuit_breaker_open(self, error_recovery_agent):
        """Test recovery strategy selection for CircuitBreakerOpenException"""
        strategy = error_recovery_agent._select_recovery_strategy(CircuitBreakerOpenException("Circuit open"))

        assert strategy == error_recovery_agent.fallback_strategies["degrade"]

    def test_select_recovery_strategy_validation_error(self, error_recovery_agent):
        """Test recovery strategy selection for ValidationError"""
        strategy = error_recovery_agent._select_recovery_strategy(ValueError("Validation failed"))

        assert strategy == error_recovery_agent.fallback_strategies["substitute"]

    def test_select_recovery_strategy_state_error(self, error_recovery_agent):
        """Test recovery strategy selection for state-related errors"""
        strategy = error_recovery_agent._select_recovery_strategy(KeyError("Missing key"))

        assert strategy == error_recovery_agent.fallback_strategies["state_recovery"]

    def test_select_recovery_strategy_unknown_error(self, error_recovery_agent):
        """Test recovery strategy selection for unknown error types"""
        strategy = error_recovery_agent._select_recovery_strategy(RuntimeError("Unknown error"))

        assert strategy == error_recovery_agent.fallback_strategies["skip"]

    def test_attempt_recovery_common_failure(self, error_recovery_agent, valid_failed_state):
        """Test attempt recovery for common failure types"""
        with patch.object(error_recovery_agent, '_execute_recovery_strategy') as mock_execute:
            mock_execute.return_value = {'success': True, 'strategy': 'retry', 'attempts': 1}

            # Use an error that's in common_failures for CODE_GENERATOR
            result = error_recovery_agent._attempt_recovery(
                AgentType.CODE_GENERATOR, valid_failed_state, {}, LLMError("LLM Error")
            )

            mock_execute.assert_called_once()
            assert result['success'] == True

    def test_attempt_recovery_circuit_breaker_error(self, error_recovery_agent, valid_failed_state):
        """Test attempt recovery for circuit breaker errors"""
        with patch.object(error_recovery_agent, '_handle_circuit_breaker_error') as mock_handle:
            mock_handle.return_value = {'success': True, 'strategy': 'degradation', 'attempts': 1}

            result = error_recovery_agent._attempt_recovery(
                AgentType.CODE_GENERATOR, valid_failed_state, {}, CircuitBreakerOpenException("Circuit open")
            )

            mock_handle.assert_called_once()
            assert result['success'] == True

    def test_attempt_recovery_unknown_error(self, error_recovery_agent, valid_failed_state):
        """Test attempt recovery for unknown error types"""
        with patch.object(error_recovery_agent, '_execute_retry_strategy') as mock_retry:
            mock_retry.return_value = {'success': True, 'strategy': 'retry', 'attempts': 1}

            result = error_recovery_agent._attempt_recovery(
                AgentType.CODE_GENERATOR, valid_failed_state, {}, RuntimeError("Unknown error")
            )

            mock_retry.assert_called_once()
            assert result['success'] == True

    def test_execute_recovery_strategy_success_first_try(self, error_recovery_agent, valid_failed_state):
        """Test execute recovery strategy when first strategy succeeds"""
        with patch.object(error_recovery_agent, '_execute_retry_strategy') as mock_retry:
            mock_retry.return_value = {'success': True, 'strategy': 'retry', 'attempts': 1}

            result = error_recovery_agent._execute_recovery_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.RETRY.value
            assert result['attempts'] == 1

    def test_execute_recovery_strategy_fallback_success(self, error_recovery_agent, valid_failed_state):
        """Test execute recovery strategy when fallback succeeds after retry fails"""
        with patch.object(error_recovery_agent, '_execute_retry_strategy') as mock_retry, \
             patch.object(error_recovery_agent, '_execute_fallback_strategy') as mock_fallback:

            mock_retry.return_value = {'success': False, 'strategy': 'retry', 'attempts': 2}
            mock_fallback.return_value = {'success': True, 'strategy': 'fallback', 'attempts': 1}

            result = error_recovery_agent._execute_recovery_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.FALLBACK.value
            assert result['attempts'] == 1  # fallback succeeds with 1 attempt

    def test_execute_recovery_strategy_all_fail(self, error_recovery_agent, valid_failed_state):
        """Test execute recovery strategy when all strategies fail"""
        with patch.object(error_recovery_agent, '_execute_retry_strategy') as mock_retry, \
             patch.object(error_recovery_agent, '_execute_fallback_strategy') as mock_fallback, \
             patch.object(error_recovery_agent, '_execute_degradation_strategy') as mock_degrade, \
             patch.object(error_recovery_agent, '_execute_skip_strategy') as mock_skip, \
             patch.object(error_recovery_agent, '_execute_substitute_strategy') as mock_substitute:

            mock_retry.return_value = {'success': False, 'strategy': 'retry', 'attempts': 2}
            mock_fallback.return_value = {'success': False, 'strategy': 'fallback', 'attempts': 1}
            mock_degrade.return_value = {'success': False, 'strategy': 'degradation', 'attempts': 1}
            mock_skip.return_value = {'success': False, 'strategy': 'skip', 'attempts': 1}
            mock_substitute.return_value = {'success': False, 'strategy': 'substitute', 'attempts': 1}

            result = error_recovery_agent._execute_recovery_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == False
            assert result['strategy'] == 'all_failed'
            assert result['attempts'] == 6  # 2+1+1+1+1

    def test_execute_retry_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test execute retry strategy success"""
        with patch.object(error_recovery_agent, '_check_service_health_for_agent') as mock_health, \
             patch.object(error_recovery_agent, '_retry_with_circuit_breaker') as mock_retry_cb:

            mock_health.return_value = True
            mock_retry_cb.return_value = {'success': True, 'data': 'recovered'}

            result = error_recovery_agent._execute_retry_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.RETRY.value
            assert result['attempts'] == 1

    def test_execute_retry_strategy_service_unhealthy(self, error_recovery_agent, valid_failed_state):
        """Test execute retry strategy when service is unhealthy"""
        with patch.object(error_recovery_agent, '_check_service_health_for_agent') as mock_health:
            mock_health.return_value = False

            result = error_recovery_agent._execute_retry_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == False
            assert result['attempts'] == 2  # max_retries for CODE_GENERATOR

    def test_execute_retry_strategy_max_attempts_exceeded(self, error_recovery_agent, valid_failed_state):
        """Test execute retry strategy when max attempts exceeded"""
        with patch.object(error_recovery_agent, '_check_service_health_for_agent') as mock_health, \
             patch.object(error_recovery_agent, '_retry_with_circuit_breaker') as mock_retry_cb:

            mock_health.return_value = True
            mock_retry_cb.side_effect = Exception("Retry failed")

            result = error_recovery_agent._execute_retry_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == False
            assert result['attempts'] == 2  # max_retries for CODE_GENERATOR

    def test_execute_fallback_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test execute fallback strategy success"""
        strategy_config = error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR]

        with patch.object(error_recovery_agent, '_code_generation_fallback') as mock_fallback_func:
            mock_fallback_func.return_value = {'success': True, 'fallback_code': 'stub code'}

            result = error_recovery_agent._execute_fallback_strategy(
                AgentType.CODE_GENERATOR, strategy_config, valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.FALLBACK.value
            assert result['attempts'] == 1

    def test_execute_fallback_strategy_failure(self, error_recovery_agent, valid_failed_state):
        """Test execute fallback strategy failure"""
        strategy_config = error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR]

        with patch.object(error_recovery_agent, '_code_generation_fallback') as mock_fallback_func:
            mock_fallback_func.side_effect = Exception("Fallback failed")

            result = error_recovery_agent._execute_fallback_strategy(
                AgentType.CODE_GENERATOR, strategy_config, valid_failed_state, {}, ValueError("Test")
            )

            # Verify the mock was called
            mock_fallback_func.assert_called_once()

            assert result['success'] == False
            assert result['strategy'] == RecoveryStrategy.FALLBACK.value
            assert result['attempts'] == 1

    def test_execute_degradation_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test execute degradation strategy success"""
        strategy_config = error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR]

        with patch.object(error_recovery_agent, '_code_generation_degradation') as mock_degrade_func:
            mock_degrade_func.return_value = {'success': True, 'degraded_mode': True}

            result = error_recovery_agent._execute_degradation_strategy(
                AgentType.CODE_GENERATOR, strategy_config, valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.DEGRADATION.value
            assert result['attempts'] == 1

    def test_execute_skip_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test execute skip strategy success"""
        strategy_config = error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR]

        with patch.object(error_recovery_agent, '_code_generation_skip') as mock_skip_func:
            mock_skip_func.return_value = {'success': True, 'skipped': True}

            result = error_recovery_agent._execute_skip_strategy(
                AgentType.CODE_GENERATOR, strategy_config, valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.SKIP.value
            assert result['attempts'] == 1

    def test_execute_substitute_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test execute substitute strategy success"""
        strategy_config = error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR]

        with patch.object(error_recovery_agent, '_code_generation_substitute') as mock_substitute_func:
            mock_substitute_func.return_value = {'success': True, 'substituted': True}

            result = error_recovery_agent._execute_substitute_strategy(
                AgentType.CODE_GENERATOR, strategy_config, valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.SUBSTITUTE.value
            assert result['attempts'] == 1

    def test_handle_circuit_breaker_error(self, error_recovery_agent, valid_failed_state):
        """Test handling circuit breaker open errors"""
        with patch.object(error_recovery_agent, '_execute_degradation_strategy') as mock_degrade:
            mock_degrade.return_value = {'success': True, 'strategy': 'degradation', 'attempts': 1}

            result = error_recovery_agent._handle_circuit_breaker_error(
                AgentType.CODE_GENERATOR, valid_failed_state, {'service': 'ollama_code'}
            )

            mock_degrade.assert_called_once()
            assert result['success'] == True

    def test_check_service_health_for_agent(self, error_recovery_agent):
        """Test service health checking for different agent types"""
        # Test CODE_GENERATOR services
        with patch.object(error_recovery_agent.health_monitor, 'is_service_healthy') as mock_healthy:
            mock_healthy.return_value = True

            healthy = error_recovery_agent._check_service_health_for_agent(AgentType.CODE_GENERATOR)

            assert healthy == True
            mock_healthy.assert_has_calls([
                call('ollama_code'),
                call('typescript_compiler')
            ])

    def test_check_service_health_for_agent_unhealthy(self, error_recovery_agent):
        """Test service health checking when services are unhealthy"""
        with patch.object(error_recovery_agent.health_monitor, 'is_service_healthy') as mock_healthy:
            mock_healthy.return_value = False

            healthy = error_recovery_agent._check_service_health_for_agent(AgentType.CODE_GENERATOR)

            assert healthy == False

    def test_retry_with_circuit_breaker_success(self, error_recovery_agent, valid_failed_state):
        """Test retry with circuit breaker protection success"""
        with patch.object(error_recovery_agent, '_check_service_health_for_agent') as mock_health:
            mock_health.return_value = True

            result = error_recovery_agent._retry_with_circuit_breaker(
                AgentType.CODE_GENERATOR, valid_failed_state, {}
            )

            assert result['success'] == True
            assert result['data'] == 'Recovered successfully'

    def test_retry_with_circuit_breaker_service_unhealthy(self, error_recovery_agent, valid_failed_state):
        """Test retry with circuit breaker when service is unhealthy"""
        with patch.object(error_recovery_agent, '_check_service_health_for_agent') as mock_health:
            mock_health.return_value = False

            with pytest.raises(Exception, match="Service still unhealthy"):
                error_recovery_agent._retry_with_circuit_breaker(
                    AgentType.CODE_GENERATOR, valid_failed_state, {}
                )

    def test_state_recovery_strategy_success(self, error_recovery_agent, valid_failed_state):
        """Test state recovery strategy success"""
        result = error_recovery_agent._state_recovery_strategy(valid_failed_state, KeyError("Missing key"))

        assert result['recovery_applied'] == True
        assert result['recovery_details']['success'] == True
        assert result['recovery_details']['strategy'] == RecoveryStrategy.STATE_RECOVERY.value
        assert result['state_recovered'] == True
        assert 'failed_agent' not in result

    def test_state_recovery_strategy_failure(self, error_recovery_agent):
        """Test state recovery strategy failure"""
        # Create a state that will cause reinitialization to fail
        invalid_state = "not_a_dict"

        result = error_recovery_agent._state_recovery_strategy(invalid_state, KeyError("Missing key"))

        assert isinstance(result, dict)  # State is a TypedDict, so check for dict type
        assert result['recovery_failed'] == True
        assert result['recovery_details']['success'] == False

    def test_fallback_strategies_execution(self, error_recovery_agent, valid_failed_state):
        """Test that fallback strategies are properly called"""
        # Test retry strategy
        result = error_recovery_agent._retry_strategy(valid_failed_state, ValueError("Test"))
        assert 'recovery_applied' in result or 'recovery_failed' in result

        # Test degrade strategy
        result = error_recovery_agent._degrade_strategy(valid_failed_state, ValueError("Test"))
        assert 'recovery_applied' in result or 'recovery_failed' in result

        # Test skip strategy
        result = error_recovery_agent._skip_strategy(valid_failed_state, ValueError("Test"))
        assert 'recovery_applied' in result or 'recovery_failed' in result

        # Test substitute strategy
        result = error_recovery_agent._substitute_strategy(valid_failed_state, ValueError("Test"))
        assert 'recovery_applied' in result or 'recovery_failed' in result

    def test_agent_specific_fallback_strategies(self, error_recovery_agent, valid_failed_state):
        """Test agent-specific fallback strategy implementations"""
        # Test code generation fallback
        result = error_recovery_agent._code_generation_fallback(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert 'fallback_code' in result
        assert valid_failed_state['generated_code'] == result['fallback_code']

        # Test test generation fallback
        result = error_recovery_agent._test_generation_fallback(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert 'fallback_tests' in result
        assert valid_failed_state['generated_tests'] == result['fallback_tests']

        # Test code integration fallback
        result = error_recovery_agent._code_integration_fallback(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert valid_failed_state['integration_skipped'] == True

    def test_agent_specific_skip_strategies(self, error_recovery_agent, valid_failed_state):
        """Test agent-specific skip strategy implementations"""
        # Test code generation skip
        result = error_recovery_agent._code_generation_skip(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert valid_failed_state['code_generation_skipped'] == True
        assert valid_failed_state['generated_code'] == ""

        # Test test generation skip
        result = error_recovery_agent._test_generation_skip(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert valid_failed_state['test_generation_skipped'] == True
        assert valid_failed_state['generated_tests'] == ""

    def test_agent_specific_substitute_strategies(self, error_recovery_agent, valid_failed_state):
        """Test agent-specific substitute strategy implementations"""
        # Test code generation substitute
        result = error_recovery_agent._code_generation_substitute(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert result['substituted'] == True
        assert 'SubstituteImplementation' in valid_failed_state['generated_code']

        # Test test generation substitute
        result = error_recovery_agent._test_generation_substitute(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert result['substituted'] == True
        assert 'SubstituteImplementation' in valid_failed_state['generated_tests']

    def test_agent_specific_degradation_strategies(self, error_recovery_agent, valid_failed_state):
        """Test agent-specific degradation strategy implementations"""
        # Test code generation degradation
        result = error_recovery_agent._code_generation_degradation(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert result['degraded_mode'] == True
        assert valid_failed_state['generated_code'] == ""
        assert valid_failed_state['code_generation_degraded'] == True

        # Test test generation degradation
        result = error_recovery_agent._test_generation_degradation(valid_failed_state, {}, ValueError("Test"))
        assert result['success'] == True
        assert result['degraded_mode'] == True
        assert valid_failed_state['generated_tests'] == ""
        assert valid_failed_state['test_generation_degraded'] == True

    def test_get_recovery_status(self, error_recovery_agent):
        """Test getting recovery status"""
        with patch.object(error_recovery_agent.health_monitor, 'get_service_status') as mock_status:
            mock_status.return_value = {"service1": {"healthy": True}}

            status = error_recovery_agent.get_recovery_status()

            assert 'circuit_breakers' in status
            assert 'service_health' in status
            assert 'recovery_history' in status
            assert status['service_health'] == {"service1": {"healthy": True}}

    def test_helper_methods(self, error_recovery_agent, valid_failed_state):
        """Test helper methods for generating stubs and parsing"""
        # Test minimal code stub generation
        code_stub = error_recovery_agent._generate_minimal_code_stub(valid_failed_state)
        assert isinstance(code_stub, str)
        assert 'Fallback code stub' in code_stub

        # Test minimal test stub generation
        test_stub = error_recovery_agent._generate_minimal_test_stub(valid_failed_state)
        assert isinstance(test_stub, str)
        assert 'Fallback test stub' in test_stub

        # Test basic ticket parsing
        basic_result = error_recovery_agent._parse_ticket_basic(valid_failed_state)
        assert isinstance(basic_result, dict)
        assert 'title' in basic_result
        assert 'description' in basic_result

        # Test substitute code generation
        substitute_code = error_recovery_agent._generate_substitute_code_stub(valid_failed_state)
        assert isinstance(substitute_code, str)
        assert 'Substitute implementation' in substitute_code

        # Test substitute test generation
        substitute_test = error_recovery_agent._generate_substitute_test_stub(valid_failed_state)
        assert isinstance(substitute_test, str)
        assert 'Substitute test implementation' in substitute_test

        # Test substitute ticket parsing
        substitute_result = error_recovery_agent._parse_ticket_substitute(valid_failed_state)
        assert isinstance(substitute_result, dict)
        assert 'Substitute Task Analysis' in substitute_result['title']

    def test_reinitialize_state(self, error_recovery_agent):
        """Test state reinitialization with different input types"""
        # Test with dict state
        dict_state = {
            'url': 'https://example.com',
            'ticket_content': 'content',
            'generated_code': 'code',
            'relevant_code_files': [{'file_path': 'test.ts', 'content': 'test'}]
        }

        result = error_recovery_agent._reinitialize_state(dict_state, ValueError("Test"))

        assert isinstance(result, dict)  # State is a TypedDict, so it's a dict
        assert result['url'] == 'https://example.com'
        assert result['ticket_content'] == 'content'
        assert result['generated_code'] == 'code'
        assert result['state_recovered'] == True
        assert result['original_error_type'] == 'ValueError'

        # Test with non-dict state (should create default state)
        result = error_recovery_agent._reinitialize_state("invalid_state", ValueError("Test"))

        assert isinstance(result, dict)
        assert result['url'] == ''
        assert result['ticket_content'] == ''
        assert result['state_recovered'] == True

    def test_multiple_exception_types(self, error_recovery_agent, valid_failed_state):
        """Test recovery with different exception types"""
        exception_types = [
            TimeoutError("Connection timeout"),
            ConnectionError("Network error"),
            ValueError("Validation error"),
            KeyError("Missing key"),
            AttributeError("Attribute error"),
            TypeError("Type error"),
            RuntimeError("Runtime error"),
            CircuitBreakerOpenException("Circuit open")
        ]

        for exception in exception_types:
            with patch.object(error_recovery_agent, '_attempt_recovery') as mock_attempt:
                mock_attempt.return_value = {'success': True, 'strategy': 'test', 'attempts': 1}

                result = error_recovery_agent.process(State(
                    failed_agent="code_generator",
                    error_context={},
                    original_error=exception
                ))

                assert 'recovery_applied' in result or 'recovery_failed' in result

    def test_recovery_chain_multiple_attempts(self, error_recovery_agent, valid_failed_state):
        """Test recovery chain with multiple strategy attempts"""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call (retry) fails
                return {'success': False, 'strategy': 'retry', 'attempts': 2}
            elif call_count == 2:  # Second call (fallback) fails
                return {'success': False, 'strategy': 'fallback', 'attempts': 1}
            else:  # Third call (degradation) succeeds
                return {'success': True, 'strategy': 'degradation', 'attempts': 1}

        with patch.object(error_recovery_agent, '_execute_retry_strategy') as mock_retry, \
             patch.object(error_recovery_agent, '_execute_fallback_strategy') as mock_fallback, \
             patch.object(error_recovery_agent, '_execute_degradation_strategy') as mock_degrade:

            mock_retry.side_effect = lambda *args, **kwargs: {'success': False, 'strategy': 'retry', 'attempts': 2}
            mock_fallback.side_effect = lambda *args, **kwargs: {'success': False, 'strategy': 'fallback', 'attempts': 1}
            mock_degrade.side_effect = lambda *args, **kwargs: {'success': True, 'strategy': 'degradation', 'attempts': 1}

            result = error_recovery_agent._execute_recovery_strategy(
                AgentType.CODE_GENERATOR, error_recovery_agent.recovery_strategies[AgentType.CODE_GENERATOR],
                valid_failed_state, {}, ValueError("Test")
            )

            assert result['success'] == True
            assert result['strategy'] == RecoveryStrategy.DEGRADATION.value
            assert result['attempts'] == 1  # degradation succeeds with 1 attempt