"""
Agentics Application - Refactored for modularity, async patterns, and dependency injection.

This module provides the main entry point for the agentics application with improved
architecture following LangChain best practices and modern Python patterns.
"""

import asyncio
import sys
from typing import List, Dict, Any, Optional

from .config import init_config, get_config, AgenticsConfig
from .services import init_services, get_service_manager
from .workflows import init_workflows, get_workflow_manager
from .exceptions import AgenticsError, ServiceUnavailableError, ValidationError
from .utils import log_info, validate_github_url
from .monitoring import structured_log

# Agent imports
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .implementation_planner_agent import ImplementationPlannerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_generator_agent import CodeGeneratorAgent
from .test_generator_agent import TestGeneratorAgent
from .code_integrator_agent import CodeIntegratorAgent
from .post_test_runner_agent import PostTestRunnerAgent
from .code_reviewer_agent import CodeReviewerAgent
from .output_result_agent import OutputResultAgent
from .error_recovery_agent import ErrorRecoveryAgent
from .feedback_agent import FeedbackAgent
from .dependency_analyzer_agent import DependencyAnalyzerAgent
from .pre_test_runner_agent import PreTestRunnerAgent
from .process_llm_agent import ProcessLLMAgent
from .tool_integrated_agent import ToolIntegratedAgent

# Workflow and composition imports
from .composable_workflows import ComposableWorkflows
from .collaborative_generator import CollaborativeGenerator
from .agent_composer import AgentComposer
from .performance import get_batch_processor

# Circuit breaker and monitoring
from .circuit_breaker import get_circuit_breaker, CircuitBreaker, ServiceHealthMonitor
from .monitoring import structured_log

# MCP and tools
from .mcp_client import get_mcp_client, init_mcp_client
from .tools import read_file_tool, list_files_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool

# MCP tools list for agent integration
mcp_tools = [read_file_tool, list_files_tool, check_file_exists_tool, npm_search_tool, npm_install_tool, npm_list_tool]

# Prompts
from .prompts import ModularPrompts


# Global configuration and services initialization
_config = None
_service_manager = None
_workflow_manager = None
_monitor = structured_log(__name__)

# MCP client
_mcp_client = None


async def _init_global_services():
    """Initialize global services and clients."""
    global _service_manager, _mcp_client, _config

    if _config is None:
        _config = init_config()

    if _service_manager is None:
        _service_manager = await init_services(_config)

    if _mcp_client is None:
        _mcp_client = init_mcp_client()


async def check_services() -> Dict[str, bool]:
    """
    Check the health status of all services.

    Returns:
        Dictionary mapping service names to health status.
    """
    if _service_manager is None:
        await _init_global_services()

    return _service_manager.check_services_health()


async def create_composable_workflow(github_client=None, llm_reasoning=None, llm_code=None, mcp_tools=None) -> ComposableWorkflows:
    """
    Create and return a ComposableWorkflows instance with all components initialized.

    Args:
        github_client: Optional GitHub client override
        llm_reasoning: Optional reasoning LLM override
        llm_code: Optional code LLM override
        mcp_tools: Optional MCP tools override

    Returns:
        Initialized ComposableWorkflows instance.
    """
    if _service_manager is None:
        await _init_global_services()
    # Use provided overrides or defaults
    ollama_reasoning = llm_reasoning or (_service_manager.ollama_reasoning._client if _service_manager and hasattr(_service_manager, 'ollama_reasoning') else None)
    ollama_code = llm_code or (_service_manager.ollama_code._client if _service_manager and hasattr(_service_manager, 'ollama_code') else None)
    github_client = github_client or (_service_manager.github._client if _service_manager and hasattr(_service_manager, 'github') else None)

    # Get MCP tools if available and not overridden
    if mcp_tools is None and _mcp_client:
        try:
            mcp_tools = await _mcp_client.get_tools()
        except Exception:
            mcp_tools = []
    elif mcp_tools is None:
        mcp_tools = []

    return ComposableWorkflows(
        llm_reasoning=ollama_reasoning,
        llm_code=ollama_code,
        github_client=github_client,
        mcp_tools=mcp_tools
    )


class AgenticsApp:
    """
    Main application class for the agentics system.

    This class manages the lifecycle of the application, including initialization
    of services, workflows, and provides the main API for processing issues.
    """

    def __init__(self, config: Optional[AgenticsConfig] = None):
        """
        Initialize the agentics application.

        Args:
            config: Optional configuration. If None, loads from environment.
        """
        global _config
        if _config is None:
            _config = init_config()
        self.config = config or _config
        self.service_manager = _service_manager
        self.composable_workflows = None
        self.batch_processor = get_batch_processor()
        self.monitor = _monitor
        self.lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize all application components asynchronously.

        This method sets up service clients, workflows, and performs health checks.
        """
        if self._initialized:
            return

        try:
            log_info(__name__, "Initializing agentics application")
            log_info(__name__, f"Configuration: GitHub token {'set' if self.config.github_token else 'not set'}")
            log_info(__name__, f"Ollama host: {self.config.ollama_host}")
            log_info(__name__, f"Reasoning model: {self.config.ollama_reasoning_model}")
            log_info(__name__, f"Code model: {self.config.ollama_code_model}")

            # Initialize services if not already done
            if self.service_manager is None:
                self.service_manager = await init_services(self.config)
                # Update global reference
                global _service_manager
                _service_manager = self.service_manager
            log_info(__name__, f"Service manager initialized: {self.service_manager is not None}")
            log_info(__name__, f"GitHub client present: {self.service_manager.github is not None if self.service_manager else False}")


            # Perform service health checks
            await self._check_services_health()

            # Initialize composable workflows if not already done
            if self.composable_workflows is None:
                self.composable_workflows = await create_composable_workflow(
                    github_client=self.service_manager.github._client if self.service_manager.github else None,
                    llm_reasoning=self.service_manager.ollama_reasoning._client if self.service_manager.ollama_reasoning else None,
                    llm_code=self.service_manager.ollama_code._client if self.service_manager.ollama_code else None,
                    mcp_tools=await self._get_mcp_tools()
                )

            self._initialized = True
            log_info(__name__, "Agentics application initialized successfully")

        except Exception as e:
            self.monitor.error(f"Failed to initialize application: {str(e)}")
            raise AgenticsError(f"Application initialization failed: {str(e)}") from e

    async def _check_services_health(self) -> None:
        """
        Perform comprehensive health checks on all services.

        Raises:
            ServiceUnavailableError: If critical services are unavailable.
        """
        log_info(__name__, "Performing service health checks")

        health_results = await self.service_manager.check_services_health()

        # Check critical services
        critical_services = ["ollama_reasoning", "ollama_code", "github"]
        failed_services = []

        for service in critical_services:
            if not health_results.get(service, False):
                failed_services.append(service)

        if failed_services:
            error_msg = f"Critical services unavailable: {', '.join(failed_services)}"
            self.monitor.error(error_msg)
            raise ServiceUnavailableError(error_msg)

        # Log MCP status (not critical)
        if health_results.get("mcp", False):
            log_info(__name__, "MCP service available")
        else:
            log_info(__name__, "MCP service not available, proceeding without MCP functionality")


    async def _get_mcp_tools(self) -> List[Any]:
        """Get MCP tools from the service manager."""
        if self.service_manager and hasattr(self.service_manager, 'mcp') and self.service_manager.mcp:
            try:
                return await self.service_manager.mcp.get_tools()
            except Exception:
                pass

    async def _process_batch_parallel(self, issue_urls: List[str]) -> Dict[str, Any]:
        """Process multiple issues in parallel using composable workflows."""
        async def process_single_issue(issue_url: str) -> Dict[str, Any]:
            """Process a single issue asynchronously."""
            try:
                self.monitor.info("batch_issue_started", {"issue_url": issue_url})
                async with self.lock:
                    result = await self.composable_workflows.process_issue(issue_url)
                self.monitor.info("batch_issue_completed", {"issue_url": issue_url})
                return {
                    "issue_url": issue_url,
                    "success": True,
                    "result": result
                }
            except Exception as e:
                self.monitor.warning("batch_issue_failed", {"issue_url": issue_url, "error": str(e)})
                return {
                    "issue_url": issue_url,
                    "success": False,
                    "error": str(e)
                }

        # Use batch processor for concurrent execution
        results = await self.batch_processor.process_batch(
            items=issue_urls,
            processor_func=process_single_issue
        )

        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful

        return {
            "total_issues": len(issue_urls),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    async def process_issue(self, issue_url: str) -> Dict[str, Any]:
        """
        Process a single GitHub issue.

        Args:
            issue_url: URL of the GitHub issue to process.

        Returns:
            Processing result containing generated code, tests, and metadata.

        Raises:
            ValidationError: If the issue URL is invalid.
            AgenticsError: If processing fails.
        """
        if not self._initialized:
            await self.initialize()

        if not validate_github_url(issue_url):
            raise ValidationError(f"Invalid GitHub issue URL: {issue_url}")

        self.monitor.info("issue_processing_started", {"issue_url": issue_url})
        log_info(__name__, f"Processing issue: {issue_url}")

        try:
            async with self.lock:
                result = await self.composable_workflows.process_issue(issue_url)
            self.monitor.info("issue_processing_completed", {"issue_url": issue_url})
            log_info(__name__, f"Successfully processed issue: {issue_url}")
            return result

        except Exception as e:
            self.monitor.error(f"Failed to process issue {issue_url}: {str(e)}")
            raise AgenticsError(f"Issue processing failed: {str(e)}") from e

    async def process_issues_batch(self, issue_urls: List[str]) -> Dict[str, Any]:
        """
        Process multiple GitHub issues concurrently.

        Args:
            issue_urls: List of GitHub issue URLs to process.

        Returns:
            Batch processing results with success/failure counts and individual results.

        Raises:
            ValidationError: If any issue URL is invalid.
            AgenticsError: If batch processing fails.
        """
        if not self._initialized:
            await self.initialize()

        # Validate all URLs
        invalid_urls = [url for url in issue_urls if not validate_github_url(url)]
        if invalid_urls:
            raise ValidationError(f"Invalid GitHub issue URLs: {invalid_urls}")

        self.monitor.info("batch_processing_started", {"issue_count": len(issue_urls)})
        log_info(__name__, f"Starting batch processing of {len(issue_urls)} issues")

        try:
            result = await self._process_batch_parallel(issue_urls)
            self.monitor.info("batch_processing_completed", {"total_issues": result["total_issues"], "successful": result["successful"], "failed": result["failed"]})
            log_info(__name__, f"Batch processing completed: {result['successful']}/{result['total_issues']} successful")
            return result

        except Exception as e:
            self.monitor.error(f"Batch processing failed: {str(e)}")
            raise AgenticsError(f"Batch processing failed: {str(e)}") from e

    async def get_service_health(self) -> Dict[str, bool]:
        """
        Get the current health status of all services.

        Returns:
            Dictionary mapping service names to health status.
        """
        if not self._initialized:
            await self.initialize()

        return await self.service_manager.check_services_health()

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the application and clean up resources.
        """
        if not self._initialized:
            return

        log_info(__name__, "Shutting down agentics application")

        try:
            if self.service_manager:
                await self.service_manager.close_services()

            self._initialized = False
            log_info(__name__, "Agentics application shutdown complete")

        except Exception as e:
            self.monitor.error(f"Error during shutdown: {str(e)}")


# Main execution
if __name__ == "__main__":
    async def main():
        """Main async execution function."""
        if len(sys.argv) != 2:
            print("Usage: python agentics.py <issue_url>", file=sys.stderr)
            sys.exit(1)

        issue_url = sys.argv[1]
        log_info(__name__, f"Processing issue URL: {issue_url}")

        app_instance = AgenticsApp()
        try:
            await app_instance.initialize()
            result = await app_instance.process_issue(issue_url)
            log_info(__name__, "Processing completed successfully")
            print(f"Result: {result}")
        except Exception as e:
            log_info(__name__, f"Processing failed: {str(e)}")
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
        finally:
            await app_instance.shutdown()

    # Run the async main function
    asyncio.run(main())


