"""
Agentics Application - Refactored for LangGraph best practices.

This module provides the main entry point for the agentics application.
Uses a single State TypedDict throughout, direct LLM calls for code generation,
and LangGraph for workflow orchestration with self-correction loops.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from .config import AgenticsConfig, init_config
from .eval_rubric import score_output, gate_check, RubricStore
from .exceptions import AgenticsError, ValidationError
from .monitoring import structured_log
from .production_monitor import run_production_check, close_the_loop
from .services import init_services
from .utils import log_info, validate_github_url
from .workflow import AgenticsWorkflow

_monitor = structured_log(__name__)


class AgenticsApp:
    """
    Main application class for the agentics system.

    Uses AgenticsWorkflow (LangGraph-based) for processing issues through
    the full pipeline: fetch → clarify → plan → extract → generate → validate → integrate → test → output
    """

    def __init__(self, config: Optional[AgenticsConfig] = None):
        self.config = config or init_config()
        self.service_manager = None
        self.workflow: Optional[AgenticsWorkflow] = None
        self.monitor = _monitor
        self._initialized = False
        self.rubric_store = RubricStore()

    async def initialize(self) -> None:
        """Initialize all application components."""
        if self._initialized:
            return

        try:
            log_info(__name__, "Initializing agentics application")
            self.service_manager = await init_services(self.config)

            # Create workflow with LLM clients from service manager
            # Configure LLMs with think=False to prevent qwen3.5 thinking hang
            _raw_reasoning = (
                self.service_manager.ollama_reasoning.client
                if self.service_manager.ollama_reasoning else None
            )
            _raw_code = (
                self.service_manager.ollama_code.client
                if self.service_manager.ollama_code else None
            )
            ollama_reasoning = _raw_reasoning.bind(think=False) if _raw_reasoning else None
            ollama_code = _raw_code.bind(think=False) if _raw_code else None
            github_client = (
                self.service_manager.github._client
                if self.service_manager.github else None
            )

            self.workflow = AgenticsWorkflow(
                llm_reasoning=ollama_reasoning,
                llm_code=ollama_code,
                github_client=github_client,
                config=self.config,
            )

            self._initialized = True
            log_info(__name__, "Agentics application initialized successfully")
        except Exception as e:
            self.monitor.error(f"Failed to initialize: {e}")
            raise AgenticsError(f"Initialization failed: {e}") from e

    async def process_issue(self, issue_url: str) -> Dict[str, Any]:
        """
        Process a GitHub issue through the full workflow.

        Args:
            issue_url: URL of the GitHub issue to process.

        Returns:
            Processing result containing generated code, tests, and metadata.
        """
        if not self._initialized:
            await self.initialize()

        if not validate_github_url(issue_url):
            raise ValidationError(f"Invalid GitHub issue URL: {issue_url}")

        log_info(__name__, f"Processing issue: {issue_url}")

        try:
            if self.workflow is None:
                raise AgenticsError("Workflow not initialized")
            result = await self.workflow.process_issue(issue_url)

            # ── Eval loop ──────────────────────────────────────────
            eval_state = {
                "generated_code": result.get("generated_code", ""),
                "generated_tests": result.get("generated_tests", ""),
                "refined_ticket": result.get("refined_ticket", {}),
                "post_integration_tests_passed": result.get("post_integration_tests_passed"),
                "existing_tests_passed": result.get("existing_tests_passed"),
            }
            eval_scores = score_output(eval_state)
            gate_passed, gate_reason = gate_check(eval_scores)

            self.rubric_store.record({
                "issue_url": issue_url,
                "total": eval_scores["total"],
                "passed": eval_scores["passed"],
                "scores": eval_scores["scores"],
            })

            result["eval_scores"] = eval_scores
            result["eval_passed"] = gate_passed

            log_info(__name__, f"Successfully processed issue: {issue_url}")
            return result
        except Exception as e:
            self.monitor.error(f"Failed to process issue: {e}")
            raise AgenticsError(f"Issue processing failed: {e}") from e

    def get_quality_report(self) -> dict:
        """Return the production_monitor quality report dict."""
        return run_production_check()

    def record_feedback(self, issue_url: str, feedback: str) -> None:
        """Record user feedback for an issue and close the eval loop.

        Validates feedback input, flags the matching rubric entry with
        a timestamp, and closes the eval loop.
        """
        if not feedback or not feedback.strip():
            log_info(__name__, "Empty feedback received, ignoring")
            return

        entries = self.rubric_store._read_all()
        for entry in reversed(entries):
            if entry.get("issue_url") == issue_url:
                entry["feedback"] = feedback
                entry["flagged"] = True
                entry["flagged_at"] = datetime.utcnow().isoformat() + "Z"
                close_the_loop(entry)
                log_info(__name__, f"Feedback recorded for {issue_url}")
                return

        log_info(__name__, f"No matching entry found for {issue_url}")

    async def run_regression_suite(self) -> dict:
        """Run all gold standard cases through the workflow and score them.

        Loads gold standard cases from the GoldStandardSuite, runs each
        through the workflow, and checks scores against case-specific
        thresholds.  Requires the app to be initialized first.
        """
        if not self._initialized:
            await self.initialize()

        try:
            from .test_suite import GoldStandardSuite

            suite = GoldStandardSuite()
            cases = suite.get_all_cases()

            if not cases:
                return {"status": "no_cases", "total": 0, "passed": 0, "failed": 0}

            results = []
            for case in cases:
                try:
                    result = await self.workflow.process_issue(case["input"])
                    eval_scores = result.get("eval_scores", {})

                    # Check against case-specific thresholds
                    thresholds = case.get("criteria_thresholds", {})
                    case_passed = True
                    criterion_results = {}
                    for criterion, threshold in thresholds.items():
                        actual = eval_scores.get("scores", {}).get(criterion, 0)
                        criterion_results[criterion] = {
                            "actual": actual,
                            "threshold": threshold,
                            "passed": actual >= threshold,
                        }
                        if actual < threshold:
                            case_passed = False

                    results.append({
                        "case_id": case["id"],
                        "passed": case_passed,
                        "scores": eval_scores,
                        "criterion_results": criterion_results,
                    })
                except Exception as e:
                    log_info(__name__, f"Regression case {case['id']} failed: {e}")
                    results.append({
                        "case_id": case["id"],
                        "passed": False,
                        "scores": {},
                        "error": str(e),
                    })

            passed_count = sum(1 for r in results if r["passed"])
            return {
                "status": "complete",
                "total": len(cases),
                "passed": passed_count,
                "failed": len(cases) - passed_count,
                "results": results,
            }
        except Exception as e:
            self.monitor.error(f"Regression suite failed: {e}")
            raise AgenticsError(f"Regression suite failed: {e}") from e

    async def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        if not self._initialized:
            return
        log_info(__name__, "Shutting down agentics application")
        if self.service_manager:
            await self.service_manager.close_services()
        self._initialized = False


if __name__ == "__main__":
    async def main():
        issue_url = os.getenv("URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
        if not issue_url:
            print("Usage: python -m src.agentics <issue_url> or set URL env var", file=sys.stderr)
            sys.exit(1)

        app = AgenticsApp()
        try:
            await app.initialize()
            result = await app.process_issue(issue_url)
            print(f"Result keys: {list(result.keys())}")
            if result.get("generated_code"):
                print(f"Generated code length: {len(result['generated_code'])}")
            if result.get("generated_tests"):
                print(f"Generated tests length: {len(result['generated_tests'])}")
            if result.get("eval_scores"):
                print(f"Eval total: {result['eval_scores']['total']:.2f}, passed: {result['eval_passed']}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            await app.shutdown()

    asyncio.run(main())
