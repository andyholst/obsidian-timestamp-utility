"""
Configuration Integration Tests for Agentics Application.

These tests validate the configuration management system working with the full
application architecture, including service initialization, dependency injection,
and error handling scenarios.

Tests cover:
1. Full application initialization with configuration loading
2. Service setup and dependency injection with real configurations
3. Configuration validation in integration scenarios
4. Custom configuration scenarios and overrides
5. Environment variable integration with configuration
6. Configuration error handling in full application context
7. Service initialization with various configuration combinations
"""

import pytest
import os
import asyncio
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from src.agentics import AgenticsApp
from src.config import AgenticsConfig, init_config, get_config, ConfigValidationError
from src.services import init_services, ServiceManager, get_service_manager
from src.exceptions import AgenticsError, ServiceUnavailableError


class TestConfigurationIntegration:
    """Integration tests for configuration management with full application context."""

    @pytest.fixture
    async def clean_app_state(self):
        """Clean up global state before and after tests."""
        # Store original state
        original_config = globals().get('_config', None)
        original_service_manager = globals().get('_service_manager', None)

        # Clean up
        from src.config import _config
        from src.services import _service_manager
        from src.agentics import _service_manager as app_service_manager

        globals()['_config'] = None
        globals()['_service_manager'] = None
        app_service_manager = None

        yield

        # Restore or clean up
        globals()['_config'] = original_config
        globals()['_service_manager'] = original_service_manager

    @pytest.mark.integration
    async def test_full_application_initialization_with_configuration_loading(self, clean_app_state):
        """Test full application initialization with configuration loading."""
        # Ensure required environment variables are set

        # Create app with default configuration
        app = AgenticsApp()

        # Verify initial state
        assert app.config is not None
        assert app._initialized is False
        assert app.service_manager is None
        assert app.workflow_manager is None

        # Initialize application
        await app.initialize()

        # Verify full initialization
        assert app._initialized is True
        assert app.config is not None
        assert isinstance(app.config, AgenticsConfig)
        assert app.service_manager is not None
        assert app.workflow_manager is not None

        # Verify configuration values
        assert app.config.github_token is not None
        assert app.config.ollama_host.startswith(('http://', 'https://'))
        assert app.config.ollama_reasoning_model is not None
        assert app.config.ollama_code_model is not None

        # Verify services are initialized
        assert app.service_manager.ollama_reasoning is not None
        assert app.service_manager.ollama_code is not None
        assert app.service_manager.github is not None

        # Clean up
        await app.shutdown()

    @pytest.mark.integration
    async def test_service_setup_and_dependency_injection_with_real_configurations(self, clean_app_state):
        """Test service setup and dependency injection with real configurations."""

        # Create custom configuration
        custom_config = AgenticsConfig(
            github_token=os.getenv('GITHUB_TOKEN'),
            ollama_host="http://localhost:11434",
            ollama_reasoning_model="test-reasoning-model",
            ollama_code_model="test-code-model"
        )

        # Initialize services directly
        service_manager = await init_services(custom_config)

        # Verify service manager is created
        assert service_manager is not None
        assert service_manager.config is custom_config

        # Verify Ollama clients are initialized with custom config
        assert service_manager.ollama_reasoning is not None
        assert service_manager.ollama_code is not None

        # Verify LLM configurations match custom config
        reasoning_config = service_manager.ollama_reasoning.config
        code_config = service_manager.ollama_code.config

        assert reasoning_config.model == "test-reasoning-model"
        assert reasoning_config.base_url == "http://localhost:11434"
        assert code_config.model == "test-code-model"
        assert code_config.base_url == "http://localhost:11434"

        # Verify GitHub client is initialized
        assert service_manager.github is not None
        assert service_manager.github.token == os.getenv('GITHUB_TOKEN')

        # Clean up
        await service_manager.close_services()

    @pytest.mark.integration
    async def test_configuration_validation_in_integration_scenarios(self, clean_app_state):
        """Test configuration validation in integration scenarios."""
        # Test valid configuration
        valid_config = AgenticsConfig(
            github_token="test-token",
            ollama_host="http://localhost:11434"
        )
        assert valid_config.github_token == "test-token"
        assert valid_config.ollama_host == "http://localhost:11434"

        # Test invalid GitHub token
        with pytest.raises(ConfigValidationError):
            AgenticsConfig(github_token="")

        # Test invalid Ollama host
        with pytest.raises(ConfigValidationError):
            AgenticsConfig(
                github_token="test-token",
                ollama_host="invalid-url"
            )

        # Test configuration with app initialization
        app = AgenticsApp(valid_config)
        await app.initialize()

        # Verify config is used
        assert app.config.github_token == "test-token"
        assert app.config.ollama_host == "http://localhost:11434"

        await app.shutdown()

    @pytest.mark.integration
    async def test_custom_configuration_scenarios_and_overrides(self, clean_app_state):
        """Test custom configuration scenarios and overrides."""
        # Test various configuration overrides
        custom_configs = [
            # Basic override
            AgenticsConfig(
                github_token="test-token",
                ollama_host="http://localhost:11434",
                ollama_reasoning_model="custom-reasoning",
                ollama_code_model="custom-code"
            ),
            # Circuit breaker overrides
            AgenticsConfig(
                github_token="test-token",
                circuit_breaker_failure_threshold=10,
                circuit_breaker_recovery_timeout=120,
                github_circuit_breaker_failure_threshold=15,
                github_circuit_breaker_recovery_timeout=180
            ),
            # Logging overrides
            AgenticsConfig(
                github_token="test-token",
                logger_level=10,  # DEBUG
                info_as_debug=True
            )
        ]

        for custom_config in custom_configs:
            app = AgenticsApp(custom_config)
            await app.initialize()

            # Verify custom config is applied
            assert app.config.github_token == "test-token"

            # Verify service manager uses custom config
            if hasattr(custom_config, 'ollama_reasoning_model'):
                assert app.service_manager.config.ollama_reasoning_model == custom_config.ollama_reasoning_model
                assert app.service_manager.config.ollama_code_model == custom_config.ollama_code_model

            if hasattr(custom_config, 'circuit_breaker_failure_threshold'):
                assert app.config.circuit_breaker_failure_threshold == custom_config.circuit_breaker_failure_threshold
                assert app.config.circuit_breaker_recovery_timeout == custom_config.circuit_breaker_recovery_timeout

            await app.shutdown()

    @pytest.mark.integration
    async def test_environment_variable_integration_with_configuration(self, clean_app_state):
        """Test environment variable integration with configuration."""
        # Store original environment
        original_env = {
            'GITHUB_TOKEN': os.getenv('GITHUB_TOKEN'),
            'OLLAMA_HOST': os.getenv('OLLAMA_HOST'),
            'OLLAMA_REASONING_MODEL': os.getenv('OLLAMA_REASONING_MODEL'),
            'OLLAMA_CODE_MODEL': os.getenv('OLLAMA_CODE_MODEL')
        }

        try:
            # Test with custom environment variables
            test_env = {
                'GITHUB_TOKEN': 'env-test-token',
                'OLLAMA_HOST': 'http://env-test-host:11434',
                'OLLAMA_REASONING_MODEL': 'env-reasoning-model',
                'OLLAMA_CODE_MODEL': 'env-code-model'
            }

            with patch.dict(os.environ, test_env):
                # Create config from environment
                config = AgenticsConfig()

                # Verify environment variables are used
                assert config.github_token == 'env-test-token'
                assert config.ollama_host == 'http://env-test-host:11434'
                assert config.ollama_reasoning_model == 'env-reasoning-model'
                assert config.ollama_code_model == 'env-code-model'

                # Test with app
                app = AgenticsApp(config)
                await app.initialize()

                # Verify app uses environment-based config
                assert app.config.github_token == 'env-test-token'
                assert app.config.ollama_host == 'http://env-test-host:11434'

                await app.shutdown()

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                elif key in os.environ:
                    del os.environ[key]

    @pytest.mark.integration
    async def test_configuration_error_handling_in_full_application_context(self, clean_app_state):
        """Test configuration error handling in full application context."""
        # Test with invalid configuration that should fail during app initialization
        invalid_configs = [
            # Missing GitHub token
            AgenticsConfig(github_token=""),
            # Invalid Ollama host
            AgenticsConfig(
                github_token="test-token",
                ollama_host="invalid-host"
            ),
        ]

        for invalid_config in invalid_configs:
            app = AgenticsApp(invalid_config)

            # App creation should succeed, but initialization should fail
            with pytest.raises((ConfigValidationError, AgenticsError, ServiceUnavailableError)):
                await app.initialize()

    @pytest.mark.integration
    async def test_service_initialization_with_various_configuration_combinations(self, clean_app_state):
        """Test service initialization with various configuration combinations."""

        # Test different service configuration combinations
        config_combinations = [
            # Full services
            {
                'github_token': os.getenv('GITHUB_TOKEN'),
                'ollama_host': 'http://localhost:11434',
                'ollama_reasoning_model': 'qwen2.5:14b',
                'ollama_code_model': 'qwen2.5-coder:14b'
            },
            # Minimal services (just GitHub)
            {
                'github_token': os.getenv('GITHUB_TOKEN'),
                'ollama_host': 'http://localhost:11434',
                'ollama_reasoning_model': 'minimal-model',
                'ollama_code_model': 'minimal-code-model'
            },
            # Custom circuit breaker settings
            {
                'github_token': os.getenv('GITHUB_TOKEN'),
                'circuit_breaker_failure_threshold': 5,
                'circuit_breaker_recovery_timeout': 60,
                'github_circuit_breaker_failure_threshold': 3,
                'github_circuit_breaker_recovery_timeout': 30
            }
        ]

        for config_dict in config_combinations:
            config = AgenticsConfig(**config_dict)
            service_manager = await init_services(config)

            # Verify services are initialized according to config
            assert service_manager.ollama_reasoning is not None
            assert service_manager.ollama_code is not None
            assert service_manager.github is not None

            # Verify config values are applied
            assert service_manager.config.github_token == config_dict['github_token']
            assert service_manager.config.ollama_host == config_dict['ollama_host']
            assert service_manager.config.ollama_reasoning_model == config_dict['ollama_reasoning_model']
            assert service_manager.config.ollama_code_model == config_dict['ollama_code_model']

            if 'circuit_breaker_failure_threshold' in config_dict:
                assert service_manager.config.circuit_breaker_failure_threshold == config_dict['circuit_breaker_failure_threshold']
                assert service_manager.config.circuit_breaker_recovery_timeout == config_dict['circuit_breaker_recovery_timeout']

            # Test health checks
            health_results = await service_manager.check_services_health()
            assert isinstance(health_results, dict)
            assert 'ollama_reasoning' in health_results
            assert 'ollama_code' in health_results
            assert 'github' in health_results

            await service_manager.close_services()

    @pytest.mark.integration
    async def test_configuration_persistence_across_app_instances(self, clean_app_state):
        """Test configuration persistence across multiple app instances."""

        # Create first app with custom config
        custom_config = AgenticsConfig(
            github_token=os.getenv('GITHUB_TOKEN'),
            ollama_host="http://localhost:11434",
            ollama_reasoning_model="persistent-reasoning",
            ollama_code_model="persistent-code"
        )

        app1 = AgenticsApp(custom_config)
        await app1.initialize()

        # Create second app (should use default config, not inherit from first)
        app2 = AgenticsApp()
        await app2.initialize()

        # Verify configs are independent
        assert app1.config.ollama_reasoning_model == "persistent-reasoning"
        assert app1.config.ollama_code_model == "persistent-code"

        # Second app should have default values
        assert app2.config.ollama_reasoning_model != "persistent-reasoning"
        assert app2.config.ollama_code_model != "persistent-code"

        await app1.shutdown()
        await app2.shutdown()

    @pytest.mark.integration
    async def test_configuration_with_service_dependency_injection(self, clean_app_state):
        """Test configuration working with service dependency injection."""

        # Create config
        config = AgenticsConfig(
            github_token=os.getenv('GITHUB_TOKEN'),
            ollama_host="http://localhost:11434"
        )

        # Initialize services
        service_manager = await init_services(config)

        # Verify dependency injection - services should have access to config
        assert service_manager.config is config

        # Ollama clients should be initialized with config values
        reasoning_llm_config = service_manager.ollama_reasoning.config
        code_llm_config = service_manager.ollama_code.config

        assert reasoning_llm_config.base_url == config.ollama_host
        assert reasoning_llm_config.model == config.ollama_reasoning_model
        assert code_llm_config.base_url == config.ollama_host
        assert code_llm_config.model == config.ollama_code_model

        # GitHub client should have token from config
        assert service_manager.github.token == config.github_token

        await service_manager.close_services()

    @pytest.mark.integration
    async def test_configuration_validation_edge_cases(self, clean_app_state):
        """Test configuration validation edge cases."""
        # Test with None values that should use defaults
        config = AgenticsConfig(
            github_token="test-token",
            ollama_host=None,  # Should use environment or default
            ollama_reasoning_model=None,
            ollama_code_model=None
        )

        # Should not raise validation errors for None values that have defaults
        assert config.github_token == "test-token"

        # Test with app - should handle None values gracefully
        app = AgenticsApp(config)
        await app.initialize()

        # Config should have resolved values
        assert app.config.ollama_host is not None
        assert app.config.ollama_reasoning_model is not None
        assert app.config.ollama_code_model is not None

        await app.shutdown()