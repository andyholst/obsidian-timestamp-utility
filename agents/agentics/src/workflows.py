"""Workflow orchestration and management."""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

from .exceptions import WorkflowError, BatchProcessingError, ValidationError
from .services import get_service_manager
from .performance import get_task_manager, get_batch_processor
from .composable_workflows import ComposableWorkflows
from .utils import log_info, validate_github_url


class Workflow(ABC):
    """Abstract base class for workflows."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow with input data."""
        pass

    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input data for the workflow."""
        pass


class IssueProcessingWorkflow(Workflow):
    """Workflow for processing GitHub issues."""

    def __init__(self):
        super().__init__("issue_processing")
        self.service_manager = get_service_manager()
        self.task_manager = get_task_manager()
        self.batch_processor = get_batch_processor()

    def validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input for issue processing."""
        if 'url' not in input_data:
            raise ValidationError("Input must contain 'url' key")

        url = input_data['url']
        if not isinstance(url, str) or not validate_github_url(url):
            raise ValidationError("Invalid GitHub issue URL")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute issue processing workflow."""
        self.validate_input(input_data)

        issue_url = input_data['url']
        log_info(__name__, f"Processing issue: {issue_url}")

        try:
            # Create composable workflow instance
            workflow_system = self._create_workflow_system()

            # Execute the workflow
            result = await workflow_system.process_issue(issue_url)

            log_info(__name__, f"Successfully processed issue: {issue_url}")
            return {
                "success": True,
                "issue_url": issue_url,
                "result": result
            }

        except Exception as e:
            log_info(__name__, f"Failed to process issue {issue_url}: {str(e)}")
            raise WorkflowError(f"Workflow execution failed: {str(e)}") from e

    def _create_workflow_system(self) -> ComposableWorkflows:
        """Create a composable workflow system instance."""
        github_client = self.service_manager.github._client if self.service_manager.github else None
        mcp_tools = self.service_manager.mcp.get_tools() if self.service_manager.mcp else []

        return ComposableWorkflows(
            llm_reasoning=self.service_manager.ollama_reasoning._client,
            llm_code=self.service_manager.ollama_code._client,
            github_client=github_client,
            mcp_tools=mcp_tools
        )


class BatchIssueProcessingWorkflow(Workflow):
    """Workflow for batch processing multiple GitHub issues."""

    def __init__(self):
        super().__init__("batch_issue_processing")
        self.service_manager = get_service_manager()
        self.task_manager = get_task_manager()
        self.batch_processor = get_batch_processor()

    def validate_input(self, input_data: Dict[str, Any]) -> None:
        """Validate input for batch processing."""
        if 'issue_urls' not in input_data:
            raise ValidationError("Input must contain 'issue_urls' key")

        issue_urls = input_data['issue_urls']
        if not isinstance(issue_urls, list) or not issue_urls:
            raise ValidationError("'issue_urls' must be a non-empty list")

        for url in issue_urls:
            if not isinstance(url, str) or not validate_github_url(url):
                raise ValidationError(f"Invalid GitHub issue URL: {url}")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute batch issue processing workflow."""
        self.validate_input(input_data)

        issue_urls = input_data['issue_urls']
        log_info(__name__, f"Starting batch processing of {len(issue_urls)} issues")

        try:
            # Process issues in batch
            results = await self._process_batch(issue_urls)

            successful = sum(1 for r in results if r.get('success', False))
            failed = len(results) - successful

            log_info(__name__, f"Batch processing completed: {successful} successful, {failed} failed")

            return {
                "success": True,
                "total_issues": len(issue_urls),
                "successful": successful,
                "failed": failed,
                "results": results
            }

        except Exception as e:
            log_info(__name__, f"Batch processing failed: {str(e)}")
            raise BatchProcessingError(f"Batch processing failed: {str(e)}") from e

    async def _process_batch(self, issue_urls: List[str]) -> List[Dict[str, Any]]:
        """Process multiple issues concurrently."""
        async def process_single_issue(issue_url: str) -> Dict[str, Any]:
            """Process a single issue asynchronously."""
            try:
                # Create a fresh workflow for each issue to avoid state conflicts
                workflow = IssueProcessingWorkflow()
                result = await workflow.execute({"url": issue_url})
                return result
            except Exception as e:
                log_info(__name__, f"Failed to process issue {issue_url}: {str(e)}")
                return {
                    "issue_url": issue_url,
                    "success": False,
                    "error": str(e)
                }

        # Use batch processor for concurrent execution
        return await self.batch_processor.process_batch(
            items=issue_urls,
            processor_func=process_single_issue
        )


class WorkflowManager:
    """Manager for workflow orchestration."""

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self._register_workflows()

    def _register_workflows(self) -> None:
        """Register available workflows."""
        self.workflows["issue_processing"] = IssueProcessingWorkflow()
        self.workflows["batch_issue_processing"] = BatchIssueProcessingWorkflow()

    def get_workflow(self, name: str) -> Workflow:
        """Get a workflow by name."""
        if name not in self.workflows:
            raise WorkflowError(f"Workflow '{name}' not found. Available workflows: {list(self.workflows.keys())}")
        return self.workflows[name]

    async def execute_workflow(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow by name."""
        workflow = self.get_workflow(name)
        return await workflow.execute(input_data)

    def list_workflows(self) -> List[str]:
        """List available workflows."""
        return list(self.workflows.keys())


# Global workflow manager instance
_workflow_manager: Optional[WorkflowManager] = None


def get_workflow_manager() -> WorkflowManager:
    """Get the global workflow manager instance."""
    if _workflow_manager is None:
        raise RuntimeError("Workflow manager not initialized. Call init_workflows() first.")
    return _workflow_manager


def init_workflows() -> WorkflowManager:
    """Initialize the global workflow manager."""
    global _workflow_manager
    _workflow_manager = WorkflowManager()
    log_info(__name__, "Workflow manager initialized")
    return _workflow_manager