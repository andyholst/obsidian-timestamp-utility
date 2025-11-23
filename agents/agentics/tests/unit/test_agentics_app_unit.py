import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.agentics import AgenticsApp
from src.config import AgenticsConfig
from src.services import ServiceManager
from src.workflows import WorkflowManager
from src.exceptions import AgenticsError, ValidationError, ServiceUnavailableError


@pytest.fixture
def mock_config():
    """Mock AgenticsConfig."""
    config = MagicMock(spec=AgenticsConfig)
    config.github_token = "test_token"
    config.ollama_host = "http://localhost:11434"
    config.ollama_reasoning_model = "test-reasoning"
    config.ollama_code_model = "test-code"
    return config


@pytest.fixture
def mock_service_manager():
    """Mock ServiceManager."""
    manager = MagicMock(spec=ServiceManager)
    manager.check_services_health = AsyncMock(return_value={
        "ollama_reasoning": True,
        "ollama_code": True,
        "github": True,
        "mcp": False
    })
    manager.close_services = AsyncMock()
    return manager


@pytest.fixture
def mock_workflow_manager():
    """Mock WorkflowManager."""
    manager = MagicMock(spec=WorkflowManager)
    manager.execute_workflow = AsyncMock(return_value={"success": True, "result": "test_result"})
    return manager


class TestAgenticsApp:
    """Test AgenticsApp functionality."""

    @patch('src.agentics.init_services')
    @patch('src.agentics.init_workflows')
    def test_initialize_success(self, mock_init_workflows, mock_init_services, mock_config, mock_service_manager, mock_workflow_manager):
        """Test successful initialization."""
        mock_init_services.return_value = mock_service_manager
        mock_init_workflows.return_value = mock_workflow_manager

        app = AgenticsApp(mock_config)

        asyncio.run(app.initialize())

        assert app._initialized is True
        assert app.service_manager == mock_service_manager
        assert app.workflow_manager == mock_workflow_manager
        mock_init_services.assert_called_once_with(mock_config)
        mock_init_workflows.assert_called_once()

    @patch('src.agentics.init_services')
    def test_initialize_failure(self, mock_init_services, mock_config):
        """Test initialization failure."""
        mock_init_services.side_effect = Exception("Init failed")

        app = AgenticsApp(mock_config)

        with pytest.raises(AgenticsError, match="Application initialization failed: Init failed"):
            asyncio.run(app.initialize())

        assert app._initialized is False

    @patch('src.agentics.init_services')
    @patch('src.agentics.init_workflows')
    def test_initialize_already_initialized(self, mock_init_workflows, mock_init_services, mock_config, mock_service_manager, mock_workflow_manager):
        """Test initialization when already initialized."""
        mock_init_services.return_value = mock_service_manager
        mock_init_workflows.return_value = mock_workflow_manager

        app = AgenticsApp(mock_config)
        app._initialized = True

        asyncio.run(app.initialize())

        # Should not call init functions again
        mock_init_services.assert_not_called()
        mock_init_workflows.assert_not_called()

    @patch('src.agentics.validate_github_url')
    def test_process_issue_success(self, mock_validate_url, mock_config, mock_service_manager, mock_workflow_manager):
        """Test successful issue processing."""
        mock_validate_url.return_value = True
        mock_workflow_manager.execute_workflow.return_value = {"success": True, "result": "processed"}

        app = AgenticsApp(mock_config)
        app._initialized = True
        app.service_manager = mock_service_manager
        app.workflow_manager = mock_workflow_manager

        result = asyncio.run(app.process_issue("https://github.com/test/repo/issues/1"))

        assert result == {"success": True, "result": "processed"}
        mock_validate_url.assert_called_once_with("https://github.com/test/repo/issues/1")
        mock_workflow_manager.execute_workflow.assert_called_once_with(
            "issue_processing",
            {"url": "https://github.com/test/repo/issues/1"}
        )

    @patch('src.agentics.validate_github_url')
    def test_process_issue_invalid_url(self, mock_validate_url, mock_config):
        """Test process_issue with invalid URL."""
        mock_validate_url.return_value = False

        app = AgenticsApp(mock_config)
        app._initialized = True

        with pytest.raises(ValidationError, match="Invalid GitHub issue URL: invalid-url"):
            asyncio.run(app.process_issue("invalid-url"))

    def test_process_issue_not_initialized(self, mock_config, mock_service_manager, mock_workflow_manager):
        """Test process_issue when not initialized."""
        app = AgenticsApp(mock_config)
        app.service_manager = mock_service_manager
        app.workflow_manager = mock_workflow_manager

        # Should call initialize first
        with patch.object(app, 'initialize', new_callable=AsyncMock) as mock_init:
            with patch('src.agentics.validate_github_url', return_value=True):
                mock_workflow_manager.execute_workflow.return_value = {"success": True}

                asyncio.run(app.process_issue("https://github.com/test/repo/issues/1"))

                mock_init.assert_called_once()

    @patch('src.agentics.validate_github_url')
    def test_process_issue_workflow_failure(self, mock_validate_url, mock_config, mock_service_manager, mock_workflow_manager):
        """Test process_issue with workflow failure."""
        mock_validate_url.return_value = True
        mock_workflow_manager.execute_workflow.side_effect = Exception("Workflow failed")

        app = AgenticsApp(mock_config)
        app._initialized = True
        app.service_manager = mock_service_manager
        app.workflow_manager = mock_workflow_manager

        with pytest.raises(AgenticsError, match="Issue processing failed: Workflow failed"):
            asyncio.run(app.process_issue("https://github.com/test/repo/issues/1"))

    @patch('src.agentics.validate_github_url')
    def test_process_issues_batch_success(self, mock_validate_url, mock_config, mock_service_manager, mock_workflow_manager):
        """Test successful batch processing."""
        mock_validate_url.return_value = True
        mock_workflow_manager.execute_workflow.return_value = {
            "success": True,
            "total_issues": 2,
            "successful": 2,
            "failed": 0,
            "results": [{"success": True}, {"success": True}]
        }

        app = AgenticsApp(mock_config)
        app._initialized = True
        app.service_manager = mock_service_manager
        app.workflow_manager = mock_workflow_manager

        urls = ["https://github.com/test/repo/issues/1", "https://github.com/test/repo/issues/2"]
        result = asyncio.run(app.process_issues_batch(urls))

        assert result["success"] is True
        assert result["total_issues"] == 2
        mock_workflow_manager.execute_workflow.assert_called_once_with(
            "batch_issue_processing",
            {"issue_urls": urls}
        )

    @patch('src.agentics.validate_github_url')
    def test_process_issues_batch_validation_error(self, mock_validate_url, mock_config):
        """Test process_issues_batch with validation error."""
        mock_validate_url.side_effect = [True, False]  # First valid, second invalid

        app = AgenticsApp(mock_config)
        app._initialized = True

        urls = ["https://github.com/test/repo/issues/1", "invalid-url"]

        with pytest.raises(ValidationError, match="Invalid GitHub issue URLs: \\['invalid-url'\\]"):
            asyncio.run(app.process_issues_batch(urls))

    def test_process_issues_batch_not_initialized(self, mock_config, mock_service_manager, mock_workflow_manager):
        """Test process_issues_batch when not initialized."""
        app = AgenticsApp(mock_config)
        app.service_manager = mock_service_manager
        app.workflow_manager = mock_workflow_manager

        # Should call initialize first
        with patch.object(app, 'initialize', new_callable=AsyncMock) as mock_init:
            with patch('src.agentics.validate_github_url', return_value=True):
                mock_workflow_manager.execute_workflow.return_value = {"successful": 1, "total_issues": 1}

                urls = ["https://github.com/test/repo/issues/1"]
                asyncio.run(app.process_issues_batch(urls))

                mock_init.assert_called_once()

    def test_get_service_health_success(self, mock_config, mock_service_manager):
        """Test get_service_health success."""
        app = AgenticsApp(mock_config)
        app._initialized = True
        app.service_manager = mock_service_manager

        result = asyncio.run(app.get_service_health())

        assert result == {
            "ollama_reasoning": True,
            "ollama_code": True,
            "github": True,
            "mcp": False
        }
        mock_service_manager.check_services_health.assert_called_once()

    def test_get_service_health_not_initialized(self, mock_config, mock_service_manager):
        """Test get_service_health when not initialized."""
        app = AgenticsApp(mock_config)
        app.service_manager = mock_service_manager

        # Should call initialize first
        with patch.object(app, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_service_manager.check_services_health.return_value = {"service": True}

            result = asyncio.run(app.get_service_health())

            mock_init.assert_called_once()
            assert result == {"service": True}

    def test_shutdown_success(self, mock_config, mock_service_manager):
        """Test successful shutdown."""
        app = AgenticsApp(mock_config)
        app._initialized = True
        app.service_manager = mock_service_manager

        asyncio.run(app.shutdown())

        assert app._initialized is False
        mock_service_manager.close_services.assert_called_once()

    def test_shutdown_not_initialized(self, mock_config):
        """Test shutdown when not initialized."""
        app = AgenticsApp(mock_config)

        asyncio.run(app.shutdown())

        # Should return early without error
        assert app._initialized is False