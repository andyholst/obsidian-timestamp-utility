"""
Composable workflows using AgentComposer for the three-phase architecture:
1. ISSUE PROCESSING
2. CODE GENERATION (COLLABORATIVE)
3. INTEGRATION & TESTING
"""

import os
import shutil
from datetime import datetime
from typing import Dict, Any
from langchain_core.runnables import Runnable, RunnableParallel, RunnableLambda
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .agent_composer import AgentComposer, WorkflowConfig
from .state_adapters import (
    AgentAdapter,
    FinalStateAdapter,
    StateToCodeGenerationStateAdapter,
    CodeGenerationStateToStateAdapter,
    IntegrationInputAdapter,
)
from .state import CodeGenerationState, State
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .implementation_planner_agent import ImplementationPlannerAgent
from .dependency_analyzer_agent import DependencyAnalyzerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_integrator_agent import CodeIntegratorAgent
from .post_test_runner_agent import PostTestRunnerAgent, MAX_SELF_CORRECT_ATTEMPTS
from .pre_test_runner_agent import PreTestRunnerAgent
from .code_reviewer_agent import CodeReviewerAgent
from .output_result_agent import OutputResultAgent
from .error_recovery_agent import ErrorRecoveryAgent
from .exceptions import TestRecoveryNeeded
from .dependency_installer_agent import DependencyInstallerAgent
from .hitl_node import HITLNode
from .code_generator_agent import CodeGeneratorAgent
from .collaborative_generator import CollaborativeGenerator
from .feedback_agent import FeedbackAgent
from .process_llm_agent import ProcessLLMAgent
from .test_generator_agent import GeneratorAgent
from .utils import log_info, remove_thinking_tags
from .monitoring import structured_log, track_workflow_progress, get_monitoring_data
import logging
import asyncio
import json
import subprocess

logger = logging.getLogger(__name__)


def _find_class_insert_point(code: str) -> int:
    """Find the line number of the final closing brace of the TimestampPlugin class."""
    lines = code.split("\n")
    brace_depth = 0
    last_class_brace_line = -1
    in_class = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "class TimestampPlugin" in stripped:
            in_class = True
        if in_class:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth == 0 and i > 0:
                last_class_brace_line = i
                break
    return last_class_brace_line


def _validate_method_inside_class(code: str, method_name: str) -> str:
    """Validate that the generated method is inside the TimestampPlugin class.
    If the method is found outside the class, move it inside before the closing brace."""
    lines = code.split("\n")

    # Check if method is outside the class
    class_end = -1
    brace_depth = 0
    in_class = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "class TimestampPlugin" in stripped:
            in_class = True
        if in_class:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth == 0 and i > 0:
                class_end = i
                break

    if class_end < 0:
        return code

    # Check if the method appears after the class closing brace
    method_line_idx = -1
    for i in range(class_end + 1, len(lines)):
        if f"public {method_name}(" in lines[i] or f"private {method_name}(" in lines[i]:
            method_line_idx = i
            break

    if method_line_idx < 0:
        return code  # Method not found outside class, assume it's correct

    # Extract the method lines (from method start to its closing brace)
    method_lines = []
    brace_depth = 0
    started = False
    for i in range(method_line_idx, len(lines)):
        line = lines[i]
        brace_depth += line.count("{") - line.count("}")
        if not started and "{" in line:
            started = True
        method_lines.append(line)
        if started and brace_depth <= 0:
            break

    if not method_lines:
        return code

    # Remove the method from its current position
    new_lines = lines[:method_line_idx] + lines[method_line_idx + len(method_lines):]

    # Re-find the class end (indices shifted after removal)
    class_end = -1
    brace_depth = 0
    in_class = False
    for i, line in enumerate(new_lines):
        stripped = line.strip()
        if "class TimestampPlugin" in stripped:
            in_class = True
        if in_class:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth == 0 and i > 0:
                class_end = i
                break

    if class_end < 0:
        return code

    # Insert method inside the class, before the closing brace
    base_indent = "    "
    indented_method = [base_indent + l.strip() if l.strip() else l for l in method_lines]
    for j, ml in enumerate(indented_method):
        new_lines.insert(class_end + j, ml)

    return "\n".join(new_lines)


def _find_onload_insert_point(code: str) -> int:
    """Find the line number just BEFORE the closing } of onload() method."""
    lines = code.split("\n")
    in_onload = False
    brace_depth = 0
    onload_close_brace = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "async onload()" in stripped or "onload()" in stripped:
            in_onload = True
            brace_depth = lines[i].count("{") - lines[i].count("}")
            continue
        if in_onload:
            brace_depth += lines[i].count("{") - lines[i].count("}")
            if brace_depth <= 0:
                onload_close_brace = i
                break
    return onload_close_brace - 1 if onload_close_brace > 0 else -1


def _find_test_insert_point(code: str) -> int:
    """Find the line number in the test file where we should insert new tests.
    Finds the last }); that closes a describe block."""
    lines = code.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "});":
            return i
    return max(0, len(lines) - 1)


def _strip_indent(lines):
    """Remove common leading whitespace from lines."""
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return lines
    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
    return [l[min_indent:] if l.strip() else l for l in lines]


def _strip_onload_block(lines):
    """Remove any async onload() { ... } block from generated code lines."""
    result = []
    in_onload = False
    brace_depth = 0
    for line in lines:
        stripped = line.strip()
        if ("async onload()" in stripped or "onload() {" in stripped) and not in_onload:
            in_onload = True
            brace_depth = line.count("{") - line.count("}")
            if brace_depth <= 0:
                in_onload = False
            continue
        if in_onload:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                in_onload = False
            continue
        result.append(line)
    return result


def _strip_generated_methods(lines, method_names):
    """Remove any existing methods with the given names to avoid duplicates."""
    result = []
    in_method = False
    brace_depth = 0
    for line in lines:
        stripped = line.strip()
        if not in_method:
            for name in method_names:
                if (stripped.startswith("public " + name + "(") or
                    stripped.startswith("private " + name + "(") or
                    stripped.startswith("async " + name + "(") or
                    stripped.startswith(name + "(")):
                    in_method = True
                    brace_depth = line.count("{") - line.count("}")
                    if brace_depth <= 0:
                        in_method = False
                    break
            else:
                result.append(line)
        else:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                in_method = False
    return result


def _insert_code_into_class(existing_code: str, generated_code: str) -> str:
    """Insert generated method + command into the correct positions in existing code."""
    lines = existing_code.split("\n")
    generated_lines = generated_code.split("\n")

    # Strip any onload() block the LLM may have generated
    generated_lines = _strip_onload_block(generated_lines)

    # Strip any existing generated methods to avoid duplicates
    # Extract method names from generated code
    method_names = []
    for line in generated_lines:
        stripped = line.strip()
        for prefix in ["public ", "private ", "protected "]:
            if stripped.startswith(prefix) and "(" in stripped:
                name_part = stripped[len(prefix):].split("(")[0].strip()
                if name_part and " " not in name_part:
                    method_names.append(name_part)
                    break
    if method_names:
        lines = _strip_generated_methods(lines, method_names)

    # Find where this.addCommand starts in the generated code
    addcommand_start = -1
    for i, line in enumerate(generated_lines):
        if "this.addCommand" in line:
            addcommand_start = i
            break

    method_lines = generated_lines[:addcommand_start] if addcommand_start >= 0 else generated_lines
    command_lines = generated_lines[addcommand_start:] if addcommand_start >= 0 else []

    # Clean up empty lines
    while method_lines and not method_lines[0].strip():
        method_lines.pop(0)
    while method_lines and not method_lines[-1].strip():
        method_lines.pop()
    while command_lines and not command_lines[0].strip():
        command_lines.pop(0)
    while command_lines and not command_lines[-1].strip():
        command_lines.pop()

    # Strip existing indentation so we can apply consistent indentation
    method_lines = _strip_indent(method_lines)
    command_lines = _strip_indent(command_lines)

    class_insert = _find_class_insert_point(existing_code)
    onload_insert = _find_onload_insert_point(existing_code)

    result_lines = list(lines)

    # Insert method lines before the class closing brace (4 spaces for class member)
    if class_insert >= 0 and method_lines:
        base_indent = "    "
        indented_method = [base_indent + line if line.strip() else line for line in method_lines]
        for j, ml in enumerate(indented_method):
            result_lines.insert(class_insert + j, ml)

    # Insert command lines inside onload(), after the last existing addCommand (8 spaces)
    if onload_insert >= 0 and command_lines:
        adjusted_onload_insert = onload_insert
        if class_insert >= 0 and method_lines and onload_insert > class_insert:
            adjusted_onload_insert += len(method_lines)
        adjusted_onload_insert += 1
        base_indent = "        "
        indented_command = [base_indent + line if line.strip() else line for line in command_lines]
        for j, cl in enumerate(indented_command):
            result_lines.insert(adjusted_onload_insert + j, cl)

    return "\n".join(result_lines)


def _insert_tests_into_file(existing_tests: str, generated_tests: str) -> str:
    """Insert generated tests into the correct position in the existing test file."""
    lines = existing_tests.split("\n")
    test_lines = generated_tests.split("\n")
    while test_lines and not test_lines[0].strip():
        test_lines.pop(0)
    while test_lines and not test_lines[-1].strip():
        test_lines.pop()
    insert_point = _find_test_insert_point(existing_tests)
    result_lines = list(lines)
    for j, tl in enumerate(test_lines):
        result_lines.insert(insert_point + j, tl)
    return "\n".join(result_lines)


def _filter_tests_for_existing_methods(test_code: str, plugin_code: str) -> str:
    """Remove describe blocks for methods that don't exist in the plugin.
    This prevents test failures when the LLM generates tests for methods
    that weren't successfully inserted into the plugin."""
    import re

    # Extract all public method names from the plugin
    plugin_methods = set()
    for m in re.finditer(r'public\s+(\w+)\s*\(', plugin_code):
        plugin_methods.add(m.group(1))
    # Also include private methods
    for m in re.finditer(r'private\s+(\w+)\s*\(', plugin_code):
        plugin_methods.add(m.group(1))
    # Also include methods without access modifier
    for m in re.finditer(r'^\s+(\w+)\s*\(\w*\)\s*:\s*\w+', plugin_code, re.MULTILINE):
        plugin_methods.add(m.group(1))

    if not plugin_methods:
        return test_code

    # Find all describe blocks and check if they reference non-existent methods
    lines = test_code.split("\n")
    result_lines = []
    skip_block = False
    brace_depth = 0
    in_describe = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect describe block start
        describe_match = re.match(r"describe\(['\"](.+?)['\"]", stripped)
        if describe_match and not in_describe:
            block_name = describe_match.group(1)
            # Check if this describe block references a method that doesn't exist
            # Look ahead to find method references in the block
            block_end = i
            temp_depth = 0
            found_method_call = False
            has_nonexistent_method = False
            for j in range(i, min(i + 50, len(lines))):
                block_lines = lines[j]
                temp_depth += block_lines.count("(") - block_lines.count(")")
                # Check for method calls like plugin.someMethod()
                for method in re.finditer(r'plugin\.(\w+)\s*\(', block_lines):
                    found_method_call = True
                    if method.group(1) not in plugin_methods:
                        has_nonexistent_method = True
                        break
                if temp_depth <= 0 and j > i:
                    block_end = j
                    break
                if has_nonexistent_method:
                    break

            if has_nonexistent_method:
                # Skip this entire describe block
                skip_depth = 0
                while i < len(lines):
                    skip_depth += lines[i].count("(") - lines[i].count(")")
                    i += 1
                    if skip_depth <= 0:
                        continue
                continue
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

        i += 1

    return "\n".join(result_lines)


def _backup_project_files(project_root: str):
    """Back up generated TypeScript code and test files for inspection."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_dir = os.path.join(project_root, "backups", timestamp)
        os.makedirs(backup_dir, exist_ok=True)

        files_to_backup = [
            "src/main.ts",
            "src/__tests__/main.test.ts",
            "package.json",
            "tsconfig.json",
            "jest.config.js",
            "manifest.json",
            "package-lock.json",
        ]

        for fname in files_to_backup:
            src_path = os.path.join(project_root, fname)
            if os.path.exists(src_path):
                dst_path = os.path.join(backup_dir, fname.replace("/", "_"))
                shutil.copy2(src_path, dst_path)

        log_info("Backup", f"Backed up generated files to {backup_dir}")
    except Exception as e:
        log_info("Backup", f"Backup failed (non-fatal): {e}")


class ComposableWorkflows:
    """Factory for creating the three-phase composable workflows."""

    def __init__(
        self, llm_reasoning: Runnable, llm_code: Runnable, github_client
    ):
        self.llm_reasoning = llm_reasoning
        self.llm_code = llm_code
        self.github_client = github_client
        self.monitor = structured_log("composable_workflows")
        # Disable langsmith tracing by default to prevent hangs
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        os.environ.setdefault("LANGCHAIN_PROJECT", "agentics")

        # Initialize checkpointer for local development
        self.checkpointer = MemorySaver()

        # Initialize composer
        self.composer = AgentComposer()
        self.recovery_agent = ErrorRecoveryAgent(llm_reasoning=self.llm_reasoning)

        # Register tools (service-backed tools only; no MCP)
        # (No external MCP tool registry — tool integration is via service clients.)

        # Register agents
        self._register_agents()

        # Create workflows
        self.issue_processing_workflow = self._create_issue_processing_workflow()
        self.code_generation_workflow = self._create_code_generation_workflow()
        self.integration_testing_workflow = self._create_integration_testing_workflow()

        # Create full workflow chain
        self.full_workflow = self._create_full_workflow()

        self.monitor.info(
            "workflows_initialized",
            {
                "workflows": [
                    "issue_processing",
                    "code_generation",
                    "integration_testing",
                    "hitl",
                    "full_workflow",
                ]
            },
        )

    def _register_agents(self):
        """Register all agents with the composer."""
        # Issue processing agents
        fetch_agent = AgentAdapter(FetchIssueAgent(self.github_client))
        self.composer.register_agent("fetch_issue", fetch_agent)

        ticket_clarity_agent = AgentAdapter(
            TicketClarityAgent(self.llm_reasoning, self.github_client)
        )
        self.composer.register_agent("ticket_clarity", ticket_clarity_agent)

        planner_agent = AgentAdapter(ImplementationPlannerAgent(self.llm_reasoning))
        self.composer.register_agent("implementation_planner", planner_agent)

        # Dependency analysis agent (can run in parallel with issue processing)
        dependency_agent = AgentAdapter(DependencyAnalyzerAgent(self.llm_reasoning))
        self.composer.register_agent("dependency_analyzer", dependency_agent)

        # Code generation agents
        extractor_agent = AgentAdapter(CodeExtractorAgent(self.llm_reasoning))
        self.composer.register_agent("code_extractor", extractor_agent)

        collaborative_gen = AgentAdapter(
            CollaborativeGenerator(self.llm_reasoning, self.llm_code)
        )
        self.composer.register_agent("collaborative_generator", collaborative_gen)

        # Integration & testing agents
        pre_test_agent = AgentAdapter(PreTestRunnerAgent())
        self.composer.register_agent("pre_test_runner", pre_test_agent)

        integrator_agent = AgentAdapter(CodeIntegratorAgent(self.llm_code))
        self.composer.register_agent("code_integrator", integrator_agent)

        dependency_installer_agent = AgentAdapter(DependencyInstallerAgent())
        self.composer.register_agent("dependency_installer", dependency_installer_agent)

        post_test_agent = AgentAdapter(PostTestRunnerAgent(self.llm_code))
        self.composer.register_agent("post_test_runner", post_test_agent)

        reviewer_agent = AgentAdapter(CodeReviewerAgent(self.llm_reasoning))
        self.composer.register_agent("code_reviewer", reviewer_agent)

        output_agent = AgentAdapter(OutputResultAgent())
        self.composer.register_agent("output_result", output_agent)

        error_recovery_agent = AgentAdapter(
            ErrorRecoveryAgent(llm_reasoning=self.llm_reasoning)
        )
        self.composer.register_agent("error_recovery", error_recovery_agent)

    def _create_issue_processing_workflow(self) -> Runnable:
        """Create ISSUE PROCESSING workflow: fetch -> clarify -> plan."""
        config = WorkflowConfig(
            agent_names=["fetch_issue", "ticket_clarity", "implementation_planner"],
            tool_names=[],
        )
        raw_workflow = self.composer.create_workflow("issue_processing", config)
        return (
            StateToCodeGenerationStateAdapter()
            | raw_workflow
            | CodeGenerationStateToStateAdapter()
        )

    def _create_code_generation_workflow(self) -> Runnable:
        """Create CODE GENERATION workflow: extract -> collaborative generation."""
        config = WorkflowConfig(
            agent_names=["code_extractor", "collaborative_generator"],
            tool_names=[],
        )
        return self.composer.create_workflow("code_generation", config)

    def _create_integration_testing_workflow(self) -> Runnable:
        """Create INTEGRATION & TESTING workflow: pre-test -> integrate -> **install deps** -> test -> review -> output.

        New: dependency_installer handles refined_ticket.npm_packages: updates package.json, installs via npm_install_tool."""

        def code_integrator_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.composer.agents["code_integrator"].invoke(state)

        def dependency_installer_node(
            state: CodeGenerationState,
        ) -> CodeGenerationState:
            return self.composer.agents["dependency_installer"].invoke(state)

        def pre_test_runner_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.composer.agents["pre_test_runner"].invoke(state)

        def post_test_runner_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.composer.agents["post_test_runner"].invoke(state)

        def code_reviewer_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.composer.agents["code_reviewer"].invoke(state)

        def output_result_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.composer.agents["output_result"].invoke(state)

        def error_recovery_node(state: CodeGenerationState) -> CodeGenerationState:
            return self.recovery_agent.invoke(state)

        def hitl_node(state: CodeGenerationState) -> CodeGenerationState:
            hitl = HITLNode()
            return hitl.invoke(state)

        def recovery_router(state: CodeGenerationState) -> str:
            # Handle both dict and CodeGenerationState
            if isinstance(state, dict):
                attempts = state.get("recovery_attempt", 0) or 0
                confidence = state.get("recovery_confidence", 0.0) or 0.0
            else:
                attempts = getattr(state, "recovery_attempt", 0) or 0
                confidence = getattr(state, "recovery_confidence", 0.0) or 0.0
            # §5.2 Bounded self-correction: allow up to MAX_SELF_CORRECT_ATTEMPTS re-runs of
            # post_test_runner -> error_recovery -> code_integrator. After the bound, escalate
            # to hitl (human) instead of looping forever on real LLM calls.
            if int(attempts) < MAX_SELF_CORRECT_ATTEMPTS and float(confidence) > 50:
                return "error_recovery"
            return "hitl"

        graph = StateGraph(CodeGenerationState)

        # --- INTEGRATION & TESTING loop (docs/openspec-engineering-loop-harness.md §6 loop
        #     engineering; AGENTS.md Phase 6). Node order below IS the canonical flow the
        #     python-agentic-slim-refactor change pins (tasks.md §3A) — do not reorder/drop. ---
        # Harness B7/B10/B11: code_integrator (CodeIntegratorAgent) is the SOLE writer of TS.
        graph.add_node("code_integrator", code_integrator_node)
        graph.add_node("dependency_installer", dependency_installer_node)
        graph.add_node("pre_test_runner", pre_test_runner_node)
        graph.add_node("post_test_runner", post_test_runner_node)
        graph.add_node("error_recovery", error_recovery_node)
        graph.add_node("hitl", hitl_node)
        graph.add_node("code_reviewer", code_reviewer_node)
        graph.add_node("output_result", output_result_node)

        graph.set_entry_point("code_integrator")

        graph.add_edge("code_integrator", "dependency_installer")
        graph.add_edge("dependency_installer", "pre_test_runner")
        graph.add_edge("pre_test_runner", "post_test_runner")
        # Loop engineering (AGENTS.md B6 bounded self-correct): post_test_runner ->
        # error_recovery -> back to code_integrator, else escalate to hitl. Bound in recovery_router.
        graph.add_conditional_edges(
            "post_test_runner",
            recovery_router,
            {"error_recovery": "error_recovery", "hitl": "hitl"},
        )
        graph.add_edge("error_recovery", "code_integrator")
        graph.add_edge("hitl", "code_reviewer")
        graph.add_edge("code_reviewer", "output_result")
        graph.add_edge("output_result", END)

        raw_workflow = graph.compile()
        return IntegrationInputAdapter() | raw_workflow | FinalStateAdapter()

    @staticmethod
    def recovery_router(state: State) -> str:
        cg_state = StateToCodeGenerationStateAdapter().invoke(state)
        attempts = getattr(cg_state, "recovery_attempt", 0)
        confidence = getattr(cg_state, "recovery_confidence", 0.0)
        # Limit recovery attempts to prevent infinite loops with real LLM calls
        return "error_recovery" if attempts < 1 and confidence > 50 else "hitl"

    @staticmethod
    def route_hitl(state: "State") -> str:
        """Route after code_generation.

        Fast mode (`TEST_FAST_MODE=1`, set by the integration-test conftest to skip the
        *npm-test* phase) MUST still run the deterministic sole-writer floor: it routes to
        `code_integrator` (which injects the spec contract) then -> `output_result`. This is a
        B7/B10/B11 guarantee — the floor is the ONLY writer of main.ts and must run in every
        mode. Slow mode runs the full integration_testing sub-graph (or `hitl` if the validation
        score is low). See python-agentic-slim-refactor tasks.md #9.4/#10 and AGENTS.md B7.1.
        """
        if os.getenv("TEST_FAST_MODE") == "1":
            return "code_integrator"
        score = state.get("validation_score", 0) if isinstance(state, dict) else getattr(
            state, "validation_score", 0
        )
        return "hitl" if score < 80 else "integration_testing"

    def _create_full_workflow(self):
        """Create the full three-phase workflow using StateGraph with checkpointer."""
        graph = StateGraph(State)

        # Define node functions that convert between State dict and CodeGenerationState
        def _get_new_keys(state: State, result_state: State) -> State:
            """Extract only keys that were added/modified by a sub-workflow."""
            new_keys = {}
            for key, value in result_state.items():
                if key not in state:
                    new_keys[key] = value
                elif value and value != state.get(key):
                    # Only include if meaningfully different (non-empty)
                    if isinstance(value, (list, dict)) and len(value) > 0:
                        new_keys[key] = value
                    elif isinstance(value, str) and value.strip():
                        new_keys[key] = value
            return new_keys

        def issue_processing_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_state = self.issue_processing_workflow.invoke(cg_state)
            return _get_new_keys(state, result_state)

        def dependency_analysis_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["dependency_analyzer"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return _get_new_keys(state, result_state)

        def code_generation_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.code_generation_workflow.invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            new_keys = _get_new_keys(state, result_state)
            return new_keys

        def integration_testing_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_state = self.integration_testing_workflow.invoke(cg_state)
            return result_state

        def hitl_node(state: State) -> State:
            hitl = HITLNode()
            return hitl(state)

        def error_recovery_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            state_dict = CodeGenerationStateToStateAdapter().invoke(cg_state)
            recovered_state = self.recovery_agent.recover(
                state_dict, TestRecoveryNeeded("Triggered recovery")
            )
            return recovered_state

        def post_test_runner_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["post_test_runner"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def code_integrator_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["code_integrator"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def code_reviewer_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["code_reviewer"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            return result_state

        def output_result_node(state: State) -> State:
            cg_state = StateToCodeGenerationStateAdapter().invoke(state)
            result_cg = self.composer.agents["output_result"].invoke(cg_state)
            result_state = CodeGenerationStateToStateAdapter().invoke(result_cg)
            # Merge result_state into existing state to avoid LangGraph key conflicts
            # Only update keys that are new or have been modified
            merged = dict(state)
            for key, value in result_state.items():
                if key not in merged or value:
                    merged[key] = value
            # Back up generated TypeScript code and tests for inspection
            project_root = os.getenv("PROJECT_ROOT", "/tmp/obsidian-project")
            _backup_project_files(project_root)
            return merged

        # Add nodes
        # --- THREE-PHASE full workflow (AGENTS.md Phases 2-6). Canonical flow pinned by
        #     python-agentic-slim-refactor tasks.md §3A — do not reorder/drop nodes. ---
        # OpenSpec engineering (AGENTS.md B15): issue_processing -> FetchIssueAgent seeds a LOCAL
        #   OpenSpec change via `openspec new change ticket<N>` (openspec_loader.create_change_from_issue).
        graph.add_node("issue_processing", issue_processing_node)
        graph.add_node("dependency_analysis", dependency_analysis_node)
        # Generate (single path): CollaborativeGenerator -> CodeGeneratorAgent (LLM proposes only).
        graph.add_node("code_generation", code_generation_node)
        graph.add_node("hitl", hitl_node)
        # Integration & testing sub-graph (harness B7 sole-writer + loop engineering self-correct).
        graph.add_node("integration_testing", integration_testing_node)
        graph.add_node("code_reviewer", code_reviewer_node)
        graph.add_node("output_result", output_result_node)
        graph.add_node("error_recovery", error_recovery_node)
        # Fast-mode floor: the deterministic sole-writer (B7/B10/B11) MUST run even in fast mode.
        # Fast mode's intent (conftest comment) is to skip the *npm test* phase, NOT the
        # contract-injection floor. Previously fast mode routed straight to `output_result`,
        # bypassing `code_integrator` entirely -> the OpenSpec spec contract was never injected
        # (exposed by the greetings e2e: its modal is absent from the committed baseline, while
        # uuid passed only because the baseline already ships the uuid modal). See python-agentic
        # -slim-refactor tasks.md #9.4/#10.
        graph.add_node("code_integrator", code_integrator_node)

        # Add edges - canonical flow (harness B7 sole-writer + loop engineering self-correct).
        # `integration_testing` contains the `code_integrator` node (CodeIntegratorAgent
        # deterministic floor), the ONLY writer of src/main.ts / src/__tests__/main.test.ts.
        # No TEST_ULTRA_FAST_MODE shortcut: the deterministic floor is always the writer.
        graph.add_edge("issue_processing", "dependency_analysis")
        graph.add_edge("dependency_analysis", "code_generation")
        graph.add_conditional_edges(
            "code_generation",
            ComposableWorkflows.route_hitl,
            {"hitl": "hitl", "integration_testing": "integration_testing", "code_integrator": "code_integrator"},
        )
        graph.add_edge("hitl", "integration_testing")
        graph.add_edge("integration_testing", END)
        # Fast-mode floor path: deterministically inject the spec contract, then finish.
        graph.add_edge("code_integrator", "output_result")
        graph.add_edge("output_result", END)

        # Set entry point
        graph.set_entry_point("issue_processing")

        # Compile with checkpointer for persistence
        compiled = graph.compile(checkpointer=self.checkpointer)
        compiled.graph = graph
        return compiled

    def _merge_parallel_outputs(
        self, parallel_result: Dict[str, Any]
    ) -> CodeGenerationState:
        """Merge outputs from parallel issue processing and dependency analysis."""
        issue_state = parallel_result.get("issue_processing")
        dep_state = parallel_result.get("dependency_analysis")

        if not issue_state:
            raise ValueError("Missing issue_processing result from parallel execution")

        # Start with issue processing state
        merged = issue_state

        # Merge dependency analysis results if available and valid
        if (
            dep_state
            and isinstance(dep_state, dict)
            and "available_dependencies" in dep_state
        ):
            try:
                # Create new state with merged dependencies
                from dataclasses import replace
                merged = replace(
                    merged,
                    code_spec=replace(
                        merged.code_spec,
                        dependencies=dep_state["available_dependencies"]
                    ),
                )
                self.monitor.info(
                    "dependency_analysis_merged",
                    {"dependencies_count": len(dep_state["available_dependencies"])},
                )
            except Exception as e:
                self.monitor.warning(
                    "dependency_merge_failed",
                    {"error": str(e), "fallback": "using issue processing state only"},
                )
                # Continue with issue_state only if merge fails

        return merged

    @track_workflow_progress("full_workflow", "issue_processing")
    async def process_issue(self, issue_url: str) -> Dict[str, Any]:
        """Process a single issue using the composable workflow."""
        workflow_id = f"workflow_{issue_url.split('/')[-1]}"  # Extract issue number

        self.monitor.info(
            "workflow_started",
            {
                "workflow_id": workflow_id,
                "issue_url": issue_url,
                "workflow_type": "full_workflow",
            },
        )

        log_info(logger, f"Starting composable workflow for issue: {issue_url}")

        try:
            initial_state = {"url": issue_url}
            config = {"configurable": {"thread_id": workflow_id}, "recursion_limit": 500}
            result = await self.full_workflow.ainvoke(initial_state, config)

            self.monitor.info(
                "workflow_completed",
                {
                    "workflow_id": workflow_id,
                    "issue_url": issue_url,
                    "result_summary": {
                        "has_code": bool(result.get("generated_code")),
                        "has_tests": bool(result.get("generated_tests")),
                        "validation_results": bool(result.get("validation_results")),
                    },
                },
            )

            log_info(logger, "Composable workflow completed successfully")
            return result

        except Exception as e:
            self.monitor.error(
                "workflow_failed",
                {"workflow_id": workflow_id, "issue_url": issue_url, "error": str(e)},
                error=e,
            )
            return {
                "url": issue_url,
                "error": str(e),
                "error_type": type(e).__name__,
                "workflow_id": workflow_id,
                "success": False,
            }

    def get_monitoring_data(self) -> Dict[str, Any]:
        """Get monitoring data for all workflows and components."""
        return get_monitoring_data()
