"""
Agentics Application - Refactored for modularity, async patterns, and dependency injection.

This module provides the main entry point for the agentics application with improved
architecture following LangChain best practices and modern Python patterns.
"""

import asyncio
import os
import sys
from typing import List, Dict, Any, Optional

from .config import init_config, get_config, AgenticsConfig
from .services import init_services, get_service_manager
from .workflows import init_workflows, get_workflow_manager
from .exceptions import AgenticsError, ServiceUnavailableError, ValidationError
from .utils import log_info, validate_github_url
from .openspec_loader import is_local_change_ref
from .monitoring import structured_log

# Agent imports
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .implementation_planner_agent import ImplementationPlannerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_generator_agent import CodeGeneratorAgent
from .test_generator_agent import GeneratorAgent
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

# Tools
from .tools import (
    read_file_tool,
    list_files_tool,
    check_file_exists_tool,
    npm_search_tool,
    npm_install_tool,
    npm_list_tool,
)

# Prompts
from .prompts import ModularPrompts


# Global configuration and services initialization
_config = None
_service_manager = None
_workflow_manager = None
_monitor = structured_log(__name__)


async def _init_global_services():
    """Initialize global services and clients."""
    global _service_manager, _config

    if _config is None:
        _config = init_config()

    if _service_manager is None:
        _service_manager = await init_services(_config)


async def check_services() -> Dict[str, bool]:
    """
    Check the health status of all services.

    Returns:
        Dictionary mapping service names to health status.
    """
    if _service_manager is None:
        await _init_global_services()

    return _service_manager.check_services_health()


async def create_composable_workflow(
    github_client=None, llm_reasoning=None, llm_code=None
) -> ComposableWorkflows:
    """
    Create and return a ComposableWorkflows instance with all components initialized.

    Args:
        github_client: Optional GitHub client override
        llm_reasoning: Optional reasoning LLM override
        llm_code: Optional code LLM override

    Returns:
        Initialized ComposableWorkflows instance.
    """
    if _service_manager is None:
        await _init_global_services()
    # Use provided overrides or defaults
    llama_reasoning = llm_reasoning or (
        _service_manager.llm_reasoning.client
        if _service_manager and hasattr(_service_manager, "llm_reasoning") and _service_manager.llm_reasoning
        else None
    )
    llama_code = llm_code or (
        _service_manager.llm_code.client
        if _service_manager and hasattr(_service_manager, "llm_code") and _service_manager.llm_code
        else None
    )
    github_client = github_client or (
        _service_manager.github._client
        if _service_manager and hasattr(_service_manager, "github") and _service_manager.github
        else None
    )

    return ComposableWorkflows(
        llm_reasoning=llama_reasoning,
        llm_code=llama_code,
        github_client=github_client,
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
        global _config, _service_manager
        if config is not None:
            # Use the provided config without mutating the global _config
            self.config = config
            # Reset global service manager so a new one is created for this config
            _service_manager = None
        else:
            # Use or initialize the global default config
            if _config is None:
                _config = init_config()
            self.config = _config
        # Always start with None - initialize() will create a fresh service manager
        # This prevents cross-test pollution from cached global _service_manager
        self.service_manager = None
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
            log_info(
                __name__,
                f"Configuration: GitHub token {'set' if self.config.github_token else 'not set'}",
            )
            log_info(__name__, f"LLM host: {self.config.llama_host}")
            log_info(__name__, f"Reasoning model: {self.config.llama_reasoning_model}")
            log_info(__name__, f"Code model: {self.config.llama_code_model}")

            # Always create a fresh service manager (self.service_manager is always None from __init__)
            self.service_manager = await init_services(self.config)
            # Update global reference
            global _service_manager
            _service_manager = self.service_manager
            log_info(
                __name__,
                f"Service manager initialized: {self.service_manager is not None}",
            )
            log_info(
                __name__,
                f"GitHub client present: {self.service_manager.github is not None if self.service_manager else False}",
            )

            # Perform service health checks
            await self._check_services_health()

            # Initialize composable workflows only if LLM clients are available
            if self.composable_workflows is None:
                llama_reasoning_client = (
                    self.service_manager.llm_reasoning.client
                    if self.service_manager.llm_reasoning
                    else None
                )
                llama_code_client = (
                    self.service_manager.llm_code.client
                    if self.service_manager.llm_code
                    else None
                )
                if llama_reasoning_client is not None and llama_code_client is not None:
                    self.composable_workflows = await create_composable_workflow(
                        github_client=self.service_manager.github._client
                        if self.service_manager.github
                        else None,
                        llm_reasoning=llama_reasoning_client,
                        llm_code=llama_code_client,
                    )
                else:
                    self.monitor.info(
                        "Skipping workflow initialization - LLM clients not available"
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
        critical_services = ["llm_reasoning", "llm_code", "github"]
        failed_services = []

        for service in critical_services:
            if not health_results.get(service, False):
                failed_services.append(service)

        if failed_services:
            error_msg = f"Critical services unavailable: {', '.join(failed_services)}"
            self.monitor.error(error_msg)
            raise ServiceUnavailableError(error_msg)

    async def _process_batch_parallel(self, issue_urls: List[str]) -> Dict[str, Any]:
        """Process multiple issues in parallel using composable workflows."""

        async def process_single_issue(issue_url: str) -> Dict[str, Any]:
            """Process a single issue asynchronously."""
            try:
                self.monitor.info("batch_issue_started", {"issue_url": issue_url})
                async with self.lock:
                    result = await self.composable_workflows.process_issue(issue_url)
                self.monitor.info("batch_issue_completed", {"issue_url": issue_url})
                return {"issue_url": issue_url, "success": True, "result": result}
            except Exception as e:
                self.monitor.warning(
                    "batch_issue_failed", {"issue_url": issue_url, "error": str(e)}
                )
                return {"issue_url": issue_url, "success": False, "error": str(e)}

        # Use batch processor for concurrent execution
        results = await self.batch_processor.process_batch(
            items=issue_urls, processor_func=process_single_issue
        )

        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful

        return {
            "total_issues": len(issue_urls),
            "successful": successful,
            "failed": failed,
            "results": results,
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

        if not validate_github_url(issue_url) and not is_local_change_ref(issue_url):
            raise ValidationError(f"Invalid GitHub issue URL or OpenSpec change ref: {issue_url}")

        if self.composable_workflows is None:
            raise AgenticsError(
                "Workflow not initialized - LLM service is required but not available"
            )

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

        Note:
            Invalid URLs are handled gracefully and reported as failed results.
        """
        if not self._initialized:
            await self.initialize()

        self.monitor.info("batch_processing_started", {"issue_count": len(issue_urls)})
        log_info(__name__, f"Starting batch processing of {len(issue_urls)} issues")

        try:
            # Filter to valid URLs, record invalid ones as failures
            valid_urls = []
            invalid_results = []
            for url in issue_urls:
                if validate_github_url(url):
                    valid_urls.append(url)
                else:
                    invalid_results.append(
                        {"issue_url": url, "success": False, "error": f"Invalid GitHub issue URL: {url}"}
                    )

            result = await self._process_batch_parallel(valid_urls)
            result["results"].extend(invalid_results)
            result["total_issues"] = len(issue_urls)
            result["failed"] += len(invalid_results)
            self.monitor.info(
                "batch_processing_completed",
                {
                    "total_issues": result["total_issues"],
                    "successful": result["successful"],
                    "failed": result["failed"],
                },
            )
            log_info(
                __name__,
                f"Batch processing completed: {result['successful']}/{result['total_issues']} successful",
            )
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
        """Main async execution function.

        Accepts either a GitHub issue URL or a local OpenSpec change reference:
          - `URL=https://github.com/.../issues/20` (env) or argv[1]
          - `CHANGE=uuid-modal-agentic-generation` (env) -> becomes `openspec:<change>`
          - `URL=openspec:<change>` (env) or argv[1]
        """
        issue_url = os.getenv("URL")
        if not issue_url and len(sys.argv) > 1:
            issue_url = sys.argv[1]
        change = os.getenv("CHANGE")
        if change and not issue_url:
            issue_url = f"openspec:{change}"
        if not issue_url:
            print(
                "Usage: python -m src.agentics <issue_url|openspec:change> "
                "or set URL=/CHANGE= env var",
                file=sys.stderr,
            )
            sys.exit(1)

        log_info(__name__, f"Processing issue URL: {issue_url}")

        app_instance = AgenticsApp()
        try:
            await app_instance.initialize()
            result = await app_instance.process_issue(issue_url)
            log_info(__name__, "Processing completed successfully")
            print(f"Result keys: {list(result.keys())}")
            if result.get("generated_code"):
                print(f"Generated code length: {len(result['generated_code'])}")
            if result.get("generated_tests"):
                print(f"Generated tests length: {len(result['generated_tests'])}")
        except Exception as e:
            log_info(__name__, f"Processing failed: {str(e)}")
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
        finally:
            await app_instance.shutdown()

    asyncio.run(main())
