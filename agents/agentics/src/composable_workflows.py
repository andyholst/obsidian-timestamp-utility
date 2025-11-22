"""
Composable workflows using AgentComposer for the three-phase architecture:
1. ISSUE PROCESSING
2. CODE GENERATION (COLLABORATIVE)
3. INTEGRATION & TESTING
"""

from typing import Dict, Any
from langchain_core.runnables import Runnable, RunnableParallel, RunnableLambda
from langchain_core.runnables import Runnable, RunnableParallel
from .agent_composer import AgentComposer, WorkflowConfig
from .state_adapters import AgentAdapter, InitialStateAdapter, FinalStateAdapter
from .state import CodeGenerationState
from .collaborative_generator import CollaborativeGenerator
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .implementation_planner_agent import ImplementationPlannerAgent
from .dependency_analyzer_agent import DependencyAnalyzerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_integrator_agent import CodeIntegratorAgent
from .post_test_runner_agent import PostTestRunnerAgent
from .code_reviewer_agent import CodeReviewerAgent
from .output_result_agent import OutputResultAgent
from .utils import log_info
from .monitoring import structured_log, track_workflow_progress, get_monitoring_data
import logging

logger = logging.getLogger(__name__)


class ComposableWorkflows:
    """Factory for creating the three-phase composable workflows."""

    def __init__(self, llm_reasoning: Runnable, llm_code: Runnable, github_client, mcp_tools=None):
        self.llm_reasoning = llm_reasoning
        self.llm_code = llm_code
        self.github_client = github_client
        self.mcp_tools = mcp_tools or []
        self.monitor = structured_log("composable_workflows")

        # Initialize composer
        self.composer = AgentComposer()

        # Register tools
        for tool in self.mcp_tools:
            self.composer.register_tool(tool.name, tool)

        # Register agents
        self._register_agents()

        # Create workflows
        self.issue_processing_workflow = self._create_issue_processing_workflow()
        self.code_generation_workflow = self._create_code_generation_workflow()
        self.integration_testing_workflow = self._create_integration_testing_workflow()

        # Create full workflow chain
        self.full_workflow = self._create_full_workflow()

        self.monitor.info("workflows_initialized", {
            "workflows": ["issue_processing", "code_generation", "integration_testing", "full_workflow"]
        })

    def _register_agents(self):
        """Register all agents with the composer."""
        # Issue processing agents
        fetch_agent = AgentAdapter(FetchIssueAgent(self.github_client))
        self.composer.register_agent("fetch_issue", fetch_agent)

        ticket_clarity_agent = AgentAdapter(TicketClarityAgent(self.llm_reasoning, self.github_client))
        self.composer.register_agent("ticket_clarity", ticket_clarity_agent)

        planner_agent = AgentAdapter(ImplementationPlannerAgent(self.llm_reasoning))
        self.composer.register_agent("implementation_planner", planner_agent)

        # Dependency analysis agent (can run in parallel with issue processing)
        dependency_agent = AgentAdapter(DependencyAnalyzerAgent(self.llm_reasoning))
        self.composer.register_agent("dependency_analyzer", dependency_agent)

        # Code generation agents
        extractor_agent = AgentAdapter(CodeExtractorAgent(self.llm_reasoning))
        self.composer.register_agent("code_extractor", extractor_agent)

        collaborative_gen = CollaborativeGenerator(self.llm_reasoning, self.llm_code)
        self.composer.register_agent("collaborative_generator", collaborative_gen)

        # Integration & testing agents
        integrator_agent = AgentAdapter(CodeIntegratorAgent(self.llm_code))
        self.composer.register_agent("code_integrator", integrator_agent)

        post_test_agent = AgentAdapter(PostTestRunnerAgent())
        self.composer.register_agent("post_test_runner", post_test_agent)

        reviewer_agent = AgentAdapter(CodeReviewerAgent(self.llm_reasoning))
        self.composer.register_agent("code_reviewer", reviewer_agent)

        output_agent = AgentAdapter(OutputResultAgent())
        self.composer.register_agent("output_result", output_agent)

    def _create_issue_processing_workflow(self) -> Runnable:
        """Create ISSUE PROCESSING workflow: fetch -> clarify -> plan."""
        config = WorkflowConfig(
            agent_names=["fetch_issue", "ticket_clarity", "implementation_planner"],
            tool_names=[tool.name for tool in self.mcp_tools]
        )
        return self.composer.create_workflow("issue_processing", config)

    def _create_code_generation_workflow(self) -> Runnable:
        """Create CODE GENERATION workflow: extract -> collaborative generation."""
        config = WorkflowConfig(
            agent_names=["code_extractor", "collaborative_generator"],
            tool_names=[tool.name for tool in self.mcp_tools]
        )
        return self.composer.create_workflow("code_generation", config)

    def _create_integration_testing_workflow(self) -> Runnable:
        """Create INTEGRATION & TESTING workflow: integrate -> test -> review -> output."""
        config = WorkflowConfig(
            agent_names=["code_integrator", "post_test_runner", "code_reviewer", "output_result"],
            tool_names=[tool.name for tool in self.mcp_tools]
        )
        return self.composer.create_workflow("integration_testing", config)

    def _create_full_workflow(self) -> Runnable:
        """Create the full three-phase workflow chain with parallel processing."""
        # Run issue processing and dependency analysis in parallel for performance
        parallel_phase = RunnableParallel(
            issue_processing=self.issue_processing_workflow,
            dependency_analysis=self.composer.agents["dependency_analyzer"]
        )

        # Chain the workflows: parallel phase -> code generation -> integration/testing
        full_chain = (
            InitialStateAdapter() |
            parallel_phase |
            self.code_generation_workflow |
            self.integration_testing_workflow |
            FinalStateAdapter()
        )
        # Merge parallel outputs and continue with sequential workflows
        merge_outputs = RunnableLambda(self._merge_parallel_outputs)

        # Chain the workflows: parallel phase -> merge -> code generation -> integration/testing
        full_chain = (
            InitialStateAdapter() |
            parallel_phase |
            merge_outputs |
            self.code_generation_workflow |
            self.integration_testing_workflow |
            FinalStateAdapter()
        )
        return full_chain

    def _merge_parallel_outputs(self, parallel_result: Dict[str, Any]) -> CodeGenerationState:
        """Merge outputs from parallel issue processing and dependency analysis."""
        issue_state = parallel_result.get("issue_processing")
        dep_state = parallel_result.get("dependency_analysis")

        if not issue_state:
            raise ValueError("Missing issue_processing result from parallel execution")

        # Start with issue processing state
        merged = issue_state

        # Merge dependency analysis results if available and valid
        if dep_state and isinstance(dep_state, dict) and 'available_dependencies' in dep_state:
            try:
                # Create new state with merged dependencies
                merged = CodeGenerationState(
                    **{k: v for k, v in merged.__dict__.items()},
                    code_spec=merged.code_spec._replace(dependencies=dep_state['available_dependencies'])
                )
                self.monitor.info("dependency_analysis_merged", {
                    "dependencies_count": len(dep_state['available_dependencies'])
                })
            except Exception as e:
                self.monitor.warning("dependency_merge_failed", {
                    "error": str(e),
                    "fallback": "using issue processing state only"
                })
                # Continue with issue_state only if merge fails

        return merged

    @track_workflow_progress("full_workflow", "issue_processing")
    async def process_issue(self, issue_url: str) -> Dict[str, Any]:
        """Process a single issue using the composable workflow."""
        workflow_id = f"workflow_{issue_url.split('/')[-1]}"  # Extract issue number

        self.monitor.info("workflow_started", {
            "workflow_id": workflow_id,
            "issue_url": issue_url,
            "workflow_type": "full_workflow"
        })

        log_info(logger, f"Starting composable workflow for issue: {issue_url}")

        try:
            initial_state = {"url": issue_url}
            result = await self.full_workflow.ainvoke(initial_state)

            self.monitor.info("workflow_completed", {
                "workflow_id": workflow_id,
                "issue_url": issue_url,
                "result_summary": {
                    "has_code": bool(result.get("generated_code")),
                    "has_tests": bool(result.get("generated_tests")),
                    "validation_results": bool(result.get("validation_results"))
                }
            })

            log_info(logger, "Composable workflow completed successfully")
            return result

        except Exception as e:
            self.monitor.error("workflow_failed", {
                "workflow_id": workflow_id,
                "issue_url": issue_url,
                "error": str(e)
            }, error=e)
            raise
    def get_monitoring_data(self) -> Dict[str, Any]:
        """Get monitoring data for all workflows and components."""
        return get_monitoring_data()