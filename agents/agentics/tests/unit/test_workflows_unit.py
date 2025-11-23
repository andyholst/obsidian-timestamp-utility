import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

# Set required environment variables for imports
import os
os.environ.setdefault('PROJECT_ROOT', '/tmp')
os.environ.setdefault('GITHUB_TOKEN', 'dummy')

from src.workflows import (
    Workflow,
    IssueProcessingWorkflow,
    BatchIssueProcessingWorkflow,
    WorkflowManager,
    get_workflow_manager,
    init_workflows,
    WorkflowError,
    BatchProcessingError,
    ValidationError
)
from src.exceptions import ValidationError as BaseValidationError
from src.services import ServiceManager
from src.performance import AsyncTaskManager, BatchProcessor
from src.composable_workflows import ComposableWorkflows
from tests.fixtures.mock_llm_responses import create_mock_llm_response


@pytest.fixture
def mock_service_manager():
    """Create a mock service manager with all required clients."""
    mock_sm = MagicMock(spec=ServiceManager)

    # Mock Ollama clients
    mock_ollama_reasoning = MagicMock()
    mock_ollama_reasoning._client = MagicMock()
    mock_ollama_reasoning._client.invoke.return_value = "mock response"
    mock_ollama_reasoning.is_available.return_value = True

    mock_ollama_code = MagicMock()
    mock_ollama_code._client = MagicMock()
    mock_ollama_code._client.invoke.return_value = "mock code response"
    mock_ollama_code.is_available.return_value = True

    # Mock GitHub client
    mock_github = MagicMock()
    mock_github._client = MagicMock()
    mock_github.is_available.return_value = True

    # Mock MCP client
    mock_mcp = MagicMock()
    mock_mcp.get_tools.return_value = []
    mock_mcp.is_available.return_value = True

    mock_sm.ollama_reasoning = mock_ollama_reasoning
    mock_sm.ollama_code = mock_ollama_code
    mock_sm.github = mock_github
    mock_sm.mcp = mock_mcp

    return mock_sm


@pytest.fixture
def mock_task_manager():
    """Create a mock task manager."""
    return MagicMock(spec=AsyncTaskManager)


@pytest.fixture
def mock_batch_processor():
    """Create a mock batch processor."""
    return MagicMock(spec=BatchProcessor)


@pytest.fixture
def mock_composable_workflow():
    """Create a mock composable workflow."""
    mock_workflow = MagicMock(spec=ComposableWorkflows)
    mock_workflow.process_issue.return_value = {
        "success": True,
        "issue_url": "https://github.com/user/repo/issues/1",
        "result": {"title": "Test Issue", "description": "Test description"}
    }
    return mock_workflow


class TestWorkflowBaseClass:
    """Test the abstract Workflow base class."""

    def test_workflow_abstract_methods(self):
        """Test that Workflow has abstract methods that must be implemented."""
        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            Workflow("test")

    @patch('src.workflows.get_service_manager')
    def test_workflow_instantiation_with_name(self, mock_get_service_manager, mock_service_manager):
        """Test that concrete workflow classes can be instantiated with a name."""
        mock_get_service_manager.return_value = mock_service_manager

        # Test with IssueProcessingWorkflow
        workflow = IssueProcessingWorkflow()
        assert workflow.name == "issue_processing"
        assert hasattr(workflow, 'validate_input')
        assert hasattr(workflow, 'execute')

    @patch('src.workflows.get_service_manager')
    def test_workflow_name_assignment(self, mock_get_service_manager, mock_service_manager):
        """Test that workflow name is properly assigned."""
        mock_get_service_manager.return_value = mock_service_manager

        workflow = IssueProcessingWorkflow()
        assert workflow.name == "issue_processing"


class TestIssueProcessingWorkflow:
    """Test IssueProcessingWorkflow functionality."""

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    def test_init(self, mock_get_batch_processor, mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test IssueProcessingWorkflow initialization."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()

        workflow = IssueProcessingWorkflow()

        assert workflow.name == "issue_processing"
        assert workflow.service_manager == mock_service_manager
        mock_get_service_manager.assert_called_once()

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_valid_url(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test input validation with valid GitHub URL."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_validate_url.return_value = True

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        # Should not raise exception
        workflow.validate_input(input_data)
        mock_validate_url.assert_called_once_with("https://github.com/user/repo/issues/1")

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_missing_url(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test input validation with missing URL."""
        mock_get_service_manager.return_value = mock_service_manager

        workflow = IssueProcessingWorkflow()
        input_data = {}

        with pytest.raises(ValidationError, match="'url' key"):
            workflow.validate_input(input_data)

        mock_validate_url.assert_not_called()

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_invalid_url_type(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test input validation with non-string URL."""
        mock_get_service_manager.return_value = mock_service_manager

        workflow = IssueProcessingWorkflow()
        input_data = {"url": 123}

        with pytest.raises(ValidationError, match="Invalid GitHub issue URL"):
            workflow.validate_input(input_data)

        # validate_github_url should not be called for non-string URLs
        mock_validate_url.assert_not_called()

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_invalid_github_url(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test input validation with invalid GitHub URL."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_validate_url.return_value = False

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "https://github.com/user/repo/pull/1"}

        with pytest.raises(ValidationError, match="Invalid GitHub issue URL"):
            workflow.validate_input(input_data)

        mock_validate_url.assert_called_once_with("https://github.com/user/repo/pull/1")

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.ComposableWorkflows')
    @patch('src.workflows.log_info')
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_log_info, mock_composable_class, mock_validate_url,
                                 mock_get_batch_processor, mock_get_task_manager, mock_get_service_manager,
                                 mock_service_manager, mock_composable_workflow):
        """Test successful execution of issue processing workflow."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()
        mock_validate_url.return_value = True
        mock_composable_class.return_value = mock_composable_workflow

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        result = await workflow.execute(input_data)

        expected_result = {
            "success": True,
            "issue_url": "https://github.com/user/repo/issues/1",
            "result": {
                "success": True,
                "issue_url": "https://github.com/user/repo/issues/1",
                "result": {"title": "Test Issue", "description": "Test description"}
            }
        }

        assert result == expected_result
        mock_composable_workflow.process_issue.assert_called_once_with("https://github.com/user/repo/issues/1")
        assert mock_log_info.call_count == 2  # start and success logs

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.ComposableWorkflows')
    @patch('src.workflows.log_info')
    @pytest.mark.asyncio
    async def test_execute_workflow_failure(self, mock_log_info, mock_composable_class, mock_validate_url,
                                          mock_get_batch_processor, mock_get_task_manager, mock_get_service_manager,
                                          mock_service_manager):
        """Test execution failure handling."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()
        mock_validate_url.return_value = True

        mock_workflow = MagicMock()
        mock_workflow.process_issue.side_effect = Exception("Workflow failed")
        mock_composable_class.return_value = mock_workflow

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        with pytest.raises(WorkflowError, match="Workflow execution failed: Workflow failed"):
            await workflow.execute(input_data)

        assert mock_log_info.call_count == 2  # start and failure logs

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    def test_create_workflow_system(self, mock_get_batch_processor, mock_get_task_manager,
                                   mock_get_service_manager, mock_service_manager):
        """Test creation of composable workflow system."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()

        workflow = IssueProcessingWorkflow()
        composable_workflow = workflow._create_workflow_system()

        # Verify ComposableWorkflows was created with correct parameters
        from src.composable_workflows import ComposableWorkflows
        # This would need more detailed mocking to verify exact parameters
        assert composable_workflow is not None


class TestBatchIssueProcessingWorkflow:
    """Test BatchIssueProcessingWorkflow functionality."""

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    def test_init(self, mock_get_batch_processor, mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test BatchIssueProcessingWorkflow initialization."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()

        workflow = BatchIssueProcessingWorkflow()

        assert workflow.name == "batch_issue_processing"
        assert workflow.service_manager == mock_service_manager

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_valid_urls(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test batch input validation with valid URLs."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_validate_url.return_value = True

        workflow = BatchIssueProcessingWorkflow()
        input_data = {
            "issue_urls": [
                "https://github.com/user/repo/issues/1",
                "https://github.com/user/repo/issues/2"
            ]
        }

        workflow.validate_input(input_data)
        assert mock_validate_url.call_count == 2

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_missing_issue_urls(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test batch input validation with missing issue_urls."""
        mock_get_service_manager.return_value = mock_service_manager

        workflow = BatchIssueProcessingWorkflow()
        input_data = {}

        with pytest.raises(ValidationError, match="'issue_urls' key"):
            workflow.validate_input(input_data)

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_empty_issue_urls(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test batch input validation with empty issue_urls list."""
        mock_get_service_manager.return_value = mock_service_manager

        workflow = BatchIssueProcessingWorkflow()
        input_data = {"issue_urls": []}

        with pytest.raises(ValidationError, match="non-empty list"):
            workflow.validate_input(input_data)

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validate_input_invalid_url_in_list(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test batch input validation with invalid URL in list."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_validate_url.side_effect = [True, False]

        workflow = BatchIssueProcessingWorkflow()
        input_data = {
            "issue_urls": [
                "https://github.com/user/repo/issues/1",
                "invalid-url"
            ]
        }

        with pytest.raises(ValidationError, match="Invalid GitHub issue URL"):
            workflow.validate_input(input_data)

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.log_info')
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_log_info, mock_validate_url, mock_get_batch_processor,
                                 mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test successful batch execution."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_batch_processor = MagicMock()
        mock_get_batch_processor.return_value = mock_batch_processor
        mock_validate_url.return_value = True

        # Mock batch processor to return successful results
        mock_batch_processor.process_batch = AsyncMock(return_value=[
            {"success": True, "issue_url": "https://github.com/user/repo/issues/1", "result": "result1"},
            {"success": True, "issue_url": "https://github.com/user/repo/issues/2", "result": "result2"}
        ])

        workflow = BatchIssueProcessingWorkflow()
        input_data = {
            "issue_urls": [
                "https://github.com/user/repo/issues/1",
                "https://github.com/user/repo/issues/2"
            ]
        }

        result = await workflow.execute(input_data)

        expected_result = {
            "success": True,
            "total_issues": 2,
            "successful": 2,
            "failed": 0,
            "results": [
                {"success": True, "issue_url": "https://github.com/user/repo/issues/1", "result": "result1"},
                {"success": True, "issue_url": "https://github.com/user/repo/issues/2", "result": "result2"}
            ]
        }

        assert result == expected_result
        mock_batch_processor.process_batch.assert_called_once()
        assert mock_log_info.call_count == 2  # start and completion logs

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.log_info')
    @pytest.mark.asyncio
    async def test_execute_with_failures(self, mock_log_info, mock_validate_url, mock_get_batch_processor,
                                       mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test batch execution with some failures."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_batch_processor = MagicMock()
        mock_get_batch_processor.return_value = mock_batch_processor
        mock_validate_url.return_value = True

        # Mock batch processor with mixed results
        mock_batch_processor.process_batch = AsyncMock(return_value=[
            {"success": True, "issue_url": "https://github.com/user/repo/issues/1", "result": "result1"},
            {"success": False, "issue_url": "https://github.com/user/repo/issues/2", "error": "Failed"}
        ])

        workflow = BatchIssueProcessingWorkflow()
        input_data = {
            "issue_urls": [
                "https://github.com/user/repo/issues/1",
                "https://github.com/user/repo/issues/2"
            ]
        }

        result = await workflow.execute(input_data)

        expected_result = {
            "success": True,
            "total_issues": 2,
            "successful": 1,
            "failed": 1,
            "results": [
                {"success": True, "issue_url": "https://github.com/user/repo/issues/1", "result": "result1"},
                {"success": False, "issue_url": "https://github.com/user/repo/issues/2", "error": "Failed"}
            ]
        }

        assert result == expected_result

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.log_info')
    @pytest.mark.asyncio
    async def test_execute_batch_processing_failure(self, mock_log_info, mock_validate_url, mock_get_batch_processor,
                                                  mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test batch execution failure handling."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_batch_processor = MagicMock()
        mock_get_batch_processor.return_value = mock_batch_processor
        mock_validate_url.return_value = True

        # Mock batch processor to raise exception
        mock_batch_processor.process_batch.side_effect = Exception("Batch processing failed")

        workflow = BatchIssueProcessingWorkflow()
        input_data = {
            "issue_urls": [
                "https://github.com/user/repo/issues/1",
                "https://github.com/user/repo/issues/2"
            ]
        }

        with pytest.raises(BatchProcessingError, match="Batch processing failed: Batch processing failed"):
            await workflow.execute(input_data)

        assert mock_log_info.call_count == 2  # start and failure logs

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @pytest.mark.asyncio
    async def test_process_batch_concurrent_execution(self, mock_get_batch_processor, mock_get_task_manager,
                                                    mock_get_service_manager, mock_service_manager):
        """Test that batch processing handles concurrent execution."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_batch_processor = MagicMock()
        mock_get_batch_processor.return_value = mock_batch_processor

        # Mock successful batch processing
        mock_batch_processor.process_batch = AsyncMock(return_value=[
            {"success": True, "issue_url": "https://github.com/user/repo/issues/1"},
            {"success": True, "issue_url": "https://github.com/user/repo/issues/2"}
        ])

        workflow = BatchIssueProcessingWorkflow()
        issue_urls = ["https://github.com/user/repo/issues/1", "https://github.com/user/repo/issues/2"]

        results = await workflow._process_batch(issue_urls)

        assert len(results) == 2
        # Verify process_batch was called with the correct items
        mock_batch_processor.process_batch.assert_called_once()
        call_args = mock_batch_processor.process_batch.call_args
        assert call_args[1]['items'] == issue_urls
        # Verify processor_func is callable (it's the inner process_single_issue function)
        assert callable(call_args[1]['processor_func'])


class TestWorkflowManager:
    """Test WorkflowManager functionality."""

    @patch('src.workflows.get_service_manager')
    def test_init_registers_workflows(self, mock_get_service_manager, mock_service_manager):
        """Test that WorkflowManager initializes with registered workflows."""
        mock_get_service_manager.return_value = mock_service_manager

        manager = WorkflowManager()

        assert "issue_processing" in manager.workflows
        assert "batch_issue_processing" in manager.workflows
        assert isinstance(manager.workflows["issue_processing"], IssueProcessingWorkflow)
        assert isinstance(manager.workflows["batch_issue_processing"], BatchIssueProcessingWorkflow)

    @patch('src.workflows.get_service_manager')
    def test_get_workflow_existing(self, mock_get_service_manager, mock_service_manager):
        """Test getting an existing workflow."""
        mock_get_service_manager.return_value = mock_service_manager

        manager = WorkflowManager()

        workflow = manager.get_workflow("issue_processing")
        assert isinstance(workflow, IssueProcessingWorkflow)
        assert workflow.name == "issue_processing"

    @patch('src.workflows.get_service_manager')
    def test_get_workflow_nonexistent(self, mock_get_service_manager, mock_service_manager):
        """Test getting a nonexistent workflow raises error."""
        mock_get_service_manager.return_value = mock_service_manager

        manager = WorkflowManager()

        with pytest.raises(WorkflowError, match="Workflow 'nonexistent' not found"):
            manager.get_workflow("nonexistent")

    @patch('src.workflows.get_service_manager')
    def test_list_workflows(self, mock_get_service_manager, mock_service_manager):
        """Test listing available workflows."""
        mock_get_service_manager.return_value = mock_service_manager

        manager = WorkflowManager()

        workflows = manager.list_workflows()
        expected_workflows = ["issue_processing", "batch_issue_processing"]

        assert set(workflows) == set(expected_workflows)

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.ComposableWorkflows')
    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, mock_composable_class, mock_validate_url,
                                          mock_get_batch_processor, mock_get_task_manager, mock_get_service_manager,
                                          mock_service_manager, mock_composable_workflow):
        """Test successful workflow execution through manager."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()
        mock_validate_url.return_value = True
        mock_composable_class.return_value = mock_composable_workflow

        manager = WorkflowManager()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        result = await manager.execute_workflow("issue_processing", input_data)

        expected_result = {
            "success": True,
            "issue_url": "https://github.com/user/repo/issues/1",
            "result": {
                "success": True,
                "issue_url": "https://github.com/user/repo/issues/1",
                "result": {"title": "Test Issue", "description": "Test description"}
            }
        }

        assert result == expected_result

    @patch('src.workflows.get_service_manager')
    @pytest.mark.asyncio
    async def test_execute_workflow_nonexistent(self, mock_get_service_manager, mock_service_manager):
        """Test executing nonexistent workflow raises error."""
        mock_get_service_manager.return_value = mock_service_manager

        manager = WorkflowManager()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        with pytest.raises(WorkflowError, match="Workflow 'nonexistent' not found"):
            await manager.execute_workflow("nonexistent", input_data)


class TestGlobalWorkflowFunctions:
    """Test global workflow manager functions."""

    @patch('src.workflows._workflow_manager', None)
    def test_get_workflow_manager_not_initialized(self):
        """Test getting workflow manager when not initialized raises error."""
        with pytest.raises(RuntimeError, match="Workflow manager not initialized"):
            get_workflow_manager()

    @patch('src.workflows._workflow_manager')
    def test_get_workflow_manager_initialized(self, mock_manager):
        """Test getting workflow manager when initialized."""
        mock_manager.is_initialized = True
        result = get_workflow_manager()
        assert result == mock_manager

    @patch('src.workflows.WorkflowManager')
    @patch('src.workflows.log_info')
    def test_init_workflows(self, mock_log_info, mock_workflow_manager_class):
        """Test initializing global workflow manager."""
        mock_manager = MagicMock()
        mock_workflow_manager_class.return_value = mock_manager

        result = init_workflows()

        assert result == mock_manager
        mock_workflow_manager_class.assert_called_once()
        mock_log_info.assert_called_once_with('src.workflows', "Workflow manager initialized")


class TestInputValidationAndErrorPropagation:
    """Test input validation and error propagation across workflows."""

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.validate_github_url')
    def test_validation_error_propagation(self, mock_validate_url, mock_get_service_manager, mock_service_manager):
        """Test that validation errors are properly propagated."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_validate_url.return_value = False

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "invalid-url"}

        with pytest.raises(ValidationError):
            workflow.validate_input(input_data)

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @pytest.mark.asyncio
    async def test_execution_error_propagation(self, mock_validate_url, mock_get_batch_processor,
                                             mock_get_task_manager, mock_get_service_manager, mock_service_manager):
        """Test that execution errors are properly propagated."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()
        mock_validate_url.return_value = True

        workflow = IssueProcessingWorkflow()

        # Mock validation to pass but execution to fail
        with patch.object(workflow, 'validate_input'):
            with patch.object(workflow, '_create_workflow_system') as mock_create:
                mock_workflow = MagicMock()
                mock_workflow.process_issue.side_effect = Exception("Execution failed")
                mock_create.return_value = mock_workflow

                input_data = {"url": "https://github.com/user/repo/issues/1"}

                with pytest.raises(WorkflowError, match="Workflow execution failed: Execution failed"):
                    await workflow.execute(input_data)


class TestAsyncExecutionPatterns:
    """Test async execution patterns and state management."""

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @patch('src.workflows.validate_github_url')
    @patch('src.workflows.ComposableWorkflows')
    @pytest.mark.asyncio
    async def test_async_execution_is_thread_safe(self, mock_composable_class, mock_validate_url,
                                                mock_get_batch_processor, mock_get_task_manager,
                                                mock_get_service_manager, mock_service_manager):
        """Test that async execution handles concurrent calls properly."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_get_batch_processor.return_value = MagicMock()
        mock_validate_url.return_value = True

        mock_workflow = MagicMock()
        mock_workflow.process_issue = AsyncMock(return_value={"result": "success"})
        mock_composable_class.return_value = mock_workflow

        workflow = IssueProcessingWorkflow()
        input_data = {"url": "https://github.com/user/repo/issues/1"}

        # Execute multiple times concurrently
        tasks = [workflow.execute(input_data) for _ in range(3)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for result in results:
            assert result["success"] is True

    @patch('src.workflows.get_service_manager')
    @patch('src.workflows.get_task_manager')
    @patch('src.workflows.get_batch_processor')
    @pytest.mark.asyncio
    async def test_batch_processing_state_isolation(self, mock_get_batch_processor, mock_get_task_manager,
                                                  mock_get_service_manager, mock_service_manager):
        """Test that batch processing maintains state isolation between items."""
        mock_get_service_manager.return_value = mock_service_manager
        mock_get_task_manager.return_value = MagicMock()
        mock_batch_processor = MagicMock()
        mock_get_batch_processor.return_value = mock_batch_processor

        # Mock batch processor to simulate different results for different items
        async def mock_process_batch(items, processor_func):
            results = []
            for item in items:
                if "issues/1" in item:
                    results.append({"success": True, "issue_url": item, "result": "success1"})
                else:
                    results.append({"success": False, "issue_url": item, "error": "failed"})
            return results

        mock_batch_processor.process_batch = AsyncMock(side_effect=mock_process_batch)

        workflow = BatchIssueProcessingWorkflow()
        issue_urls = [
            "https://github.com/user/repo/issues/1",
            "https://github.com/user/repo/issues/2"
        ]

        results = await workflow._process_batch(issue_urls)

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        # Verify each result corresponds to its input URL
        assert results[0]["issue_url"] == "https://github.com/user/repo/issues/1"
        assert results[1]["issue_url"] == "https://github.com/user/repo/issues/2"