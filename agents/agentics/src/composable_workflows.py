"""
Composable workflows using AgentComposer for the three-phase architecture:
1. ISSUE PROCESSING
2. CODE GENERATION (COLLABORATIVE)
3. INTEGRATION & TESTING
"""

from typing import Dict, Any
from langchain_core.runnables import Runnable, RunnableParallel, RunnableLambda
from langchain_core.runnables import Runnable, RunnableParallel
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from .agent_composer import AgentComposer, WorkflowConfig
from .state_adapters import AgentAdapter, InitialStateAdapter, FinalStateAdapter, StateToCodeGenerationStateAdapter, CodeGenerationStateToStateAdapter
from .state import CodeGenerationState, State
from .collaborative_generator import CollaborativeGenerator
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .implementation_planner_agent import ImplementationPlannerAgent
from .dependency_analyzer_agent import DependencyAnalyzerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_integrator_agent import CodeIntegratorAgent
from .post_test_runner_agent import PostTestRunnerAgent
from .pre_test_runner_agent import PreTestRunnerAgent
from .code_reviewer_agent import CodeReviewerAgent
from .output_result_agent import OutputResultAgent
from .hitl_node import HITLNode
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

        # Initialize checkpointer for local development
        self.checkpointer = MemorySaver()

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
            "workflows": ["issue_processing", "code_generation", "integration_testing", "hitl", "full_workflow"]
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

        collaborative_gen = CollaborativeGenerator(self.llm_reasoning)
        self.composer.register_agent("collaborative_generator", collaborative_gen)

        # Integration & testing agents
        pre_test_agent = AgentAdapter(PreTestRunnerAgent())
        self.composer.register_agent("pre_test_runner", pre_test_agent)

        integrator_agent = AgentAdapter(CodeIntegratorAgent(self.llm_code))
        self.composer.register_agent("code_integrator", integrator_agent)

        post_test_agent = AgentAdapter(PostTestRunnerAgent(self.llm_code))
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
        """Create INTEGRATION & TESTING workflow: pre-test -> integrate -> test -> review -> output."""
        config = WorkflowConfig(
            agent_names=["pre_test_runner", "code_integrator", "post_test_runner", "code_reviewer", "output_result"],
            tool_names=[tool.name for tool in self.mcp_tools]
        )
        return self.composer.create_workflow("integration_testing", config)

    def _create_full_workflow(self):
        """Create the full three-phase workflow using StateGraph with checkpointer."""
        graph = StateGraph(State)

        # Define node functions that convert between State dict and CodeGenerationState
        def issue_processing_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.issue_processing_workflow.invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def dependency_analysis_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["dependency_analyzer"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def code_generation_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.code_generation_workflow.invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def integration_testing_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.integration_testing_workflow.invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def hitl_node(state: State) -> State:
            hitl = HITLNode()
            return hitl(state)

        # Add nodes
        graph.add_node("issue_processing", issue_processing_node)
        graph.add_node("dependency_analysis", dependency_analysis_node)
        graph.add_node("code_generation", code_generation_node)
        graph.add_node("hitl", hitl_node)
        graph.add_node("integration_testing", integration_testing_node)

        # Define routing function for HITL
        def route_hitl(state: State) -> str:
            score = state.get("validation_score", 0)
            return "hitl" if score < 80 else "integration_testing"

        # Add edges (sequential for now, parallel can be added later)
        graph.add_edge("issue_processing", "dependency_analysis")
        graph.add_edge("dependency_analysis", "code_generation")
        graph.add_conditional_edges("code_generation", route_hitl, {"hitl": "hitl", "integration_testing": "integration_testing"})
        graph.add_edge("hitl", "integration_testing")

        # Set entry point
        graph.set_entry_point("issue_processing")

        # Compile with checkpointer for persistence
        return graph.compile(checkpointer=self.checkpointer)

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
            config = {"configurable": {"thread_id": "test_thread", "checkpoint_ns": "test_ns", "checkpoint_id": "test_id"}}
            result = await self.full_workflow.ainvoke(initial_state, config=config)

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
