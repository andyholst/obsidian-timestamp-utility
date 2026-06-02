"""Agentics package — quality-gated TypeScript code generation for Obsidian plugins."""

from .state import State
from .eval_rubric import score_output, gate_check, record_failure, RegressionTracker, RubricStore
from .test_suite import GoldStandardSuite
from .production_monitor import run_production_check, close_the_loop, ThresholdAlerter
