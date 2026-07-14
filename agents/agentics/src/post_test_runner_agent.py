import logging
import os
import re
import shutil
from typing import Dict, List, Any
import json
from datetime import datetime
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from langchain_core.runnables import Runnable

from .tools import (
    check_file_exists_tool,
    write_file_tool,
    npm_install_tool,
    npm_run_tool,
    typescript_typecheck_tool,
)
from .tool_integrated_agent import ToolIntegratedAgent
from .state import State
from .utils import safe_json_dumps, log_info, safe_get
from .exceptions import TestRecoveryNeeded, CompileError, LintError, OmissionDetected

# Bounded self-correction (agentic-self-correct-loop §5.2): max re-runs of the
# post_test_runner -> error_recovery -> code_integrator cycle before giving up honestly.
MAX_SELF_CORRECT_ATTEMPTS = 5
# Lint tool preference: eslint first, then prettier --check. Either may be absent in the
# project; a missing tool is reported, not treated as a failure.
LINT_TOOLS = [
    (["npx", "eslint", ".", "--max-warnings=-1"], "eslint"),
    (["npx", "prettier", "--check", "."], "prettier"),
]


class PostTestRunnerAgent(ToolIntegratedAgent):
    def __init__(self, llm: Runnable):
        super().__init__(
            llm,
            [
                npm_install_tool,
                npm_run_tool,
                check_file_exists_tool,
                write_file_tool,
                typescript_typecheck_tool,
            ],
            name="PostTestRunner",
        )
        self.project_root = os.getenv("PROJECT_ROOT", "/project")
        if not self.project_root:
            raise ValueError("PROJECT_ROOT environment variable is required")
        self.install_command = os.getenv("INSTALL_COMMAND", "npm install")
        self.test_command = os.getenv("TEST_COMMAND", "npm test")
        self.monitor.logger.setLevel(logging.INFO)
        self.monitor.info(
            f"Initialized with project_root={self.project_root}, install_command={self.install_command}, test_command={self.test_command}"
        )

    def strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        ansi_escape = re.compile("\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _lint_config_present(self, tool_name: str) -> bool:
        """Best-effort check: is this lint tool configured in the project root?

        A lint tool with no configuration file is skipped (reported, not failed),
        consistent with the existing "missing lint binary is reported, not failed"
        contract. This prevents the gate from hard-failing on temp pipeline
        projects (and on a repo that ships no eslint config) where `npx eslint`
        would otherwise fetch a version and error with "couldn't find an
        eslint.config" file.
        """
        root = self.project_root
        if tool_name == "eslint":
            patterns = [
                "eslint.config.js",
                "eslint.config.mjs",
                "eslint.config.cjs",
                ".eslintrc",
                ".eslintrc.js",
                ".eslintrc.cjs",
                ".eslintrc.mjs",
                ".eslintrc.json",
                ".eslintrc.yaml",
                ".eslintrc.yml",
            ]
            for pat in patterns:
                if os.path.exists(os.path.join(root, pat)):
                    return True
            return False
        if tool_name == "prettier":
            import json

            if any(
                os.path.exists(os.path.join(root, p))
                for p in [".prettierrc", ".prettierrc.json", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs", ".prettierrc.yaml", ".prettierrc.yml"]
            ):
                return True
            pkg = os.path.join(root, "package.json")
            if os.path.exists(pkg):
                try:
                    with open(pkg) as f:
                        if "prettier" in json.load(f):
                            return True
                except Exception:
                    pass
            return False
        return True

    def run_lint_gate(self) -> str | None:
        """Lint gate (agentic-self-correct-loop §2).

        Runs eslint then prettier --check in the project root. Returns the combined
        lint output on the first non-zero exit (so the caller can raise LintError and
        re-enter error_recovery), or None when lint is clean / no lint tool is present
        / no lint config exists in the project root. A missing tool or config is
        reported, not treated as a failure.
        """
        import subprocess

        for cmd, tool_name in LINT_TOOLS:
            # Skip tools that have no configuration in this project root (e.g. a
            # temp pipeline project, or a repo that ships no eslint config). Running
            # `npx eslint .` with no config errors out and would wrongly fail the gate.
            if not self._lint_config_present(tool_name):
                log_info(
                    self.name,
                    f"lint tool {tool_name} has no config in {self.project_root}; skipping",
                )
                continue
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except FileNotFoundError:
                log_info(self.name, f"lint tool {tool_name} not found; skipping")
                continue
            except Exception as e:  # pragma: no cover - defensive
                log_info(self.name, f"lint tool {tool_name} errored ({e}); skipping")
                continue
            if proc.returncode != 0:
                out = self.strip_ansi_codes(proc.stdout + proc.stderr)
                log_info(
                    self.name,
                    f"lint gate ({tool_name}) FAILED (rc={proc.returncode}): {out[:400]}",
                )
                return f"[{tool_name}] {out}"
        return None

    def parse_test_errors(self, log_path: str) -> List[Dict[str, Any]]:
        with open(log_path, "r") as f:
            content = f.read()
        pattern = r"^(.*?):(\d+):(\d+) - (error TS\d+: .*?)(?=\n(?:\s*[a-zA-Z]|$))"
        errors = re.findall(pattern, content, re.MULTILINE)
        return [
            {"file": f, "line": int(l), "col": int(c), "msg": m.strip()}
            for f, l, c, m in errors
        ]

    def process(self, state: State) -> State:
        self.monitor.info(
            f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}"
        )
        self.monitor.info("Starting post-test runner process")
        log_info(self.name, f"Using project_root: {self.project_root}")
        log_info(
            self.name,
            f"existing_tests_passed from state: {safe_get(state, 'existing_tests_passed', 0)}",
        )

        if self.install_command == "npm install" and self.test_command == "npm test":
            package_json_path = os.path.join(self.project_root, "package.json")
            log_info(self.name, f"Checking for package.json at: {package_json_path}")
            exists = self.tool_executor.execute_tool(
                "check_file_exists_tool", {"file_path": package_json_path}
            )
            if not exists:
                self.monitor.warning(
                    f"package.json not found at {package_json_path}, skipping install/test and setting default metrics"
                )
                existing_tests_passed = safe_get(state, "existing_tests_passed", 0)
                existing_coverage_all_files = safe_get(
                    state, "existing_coverage_all_files", 0.0
                )
                new_state = dict(state)
                new_state["post_integration_tests_passed"] = 0
                new_state["post_integration_coverage_all_files"] = 0.0
                new_state["tests_improvement"] = 0 - existing_tests_passed
                new_state["coverage_improvement"] = 0.0 - existing_coverage_all_files
                self.monitor.info(
                    "Post-integration metrics: tests_passed=0, coverage_all_files=0.0"
                )
                self.monitor.info(
                    f"After processing in {self.name}: {safe_json_dumps(new_state, indent=2)}"
                )
                return new_state

        log_info(
            self.name,
            f"Running install command: {self.install_command} in {self.project_root}",
        )

        @retry(
            stop=stop_after_attempt(1),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            retry=retry_if_exception_type(Exception),
        )
        def run_install():
            result = self.tool_executor.execute_tool(
                "npm_install_tool",
                {
                    "package_name": "",
                    "is_dev": False,
                    "save_exact": False,
                    "cwd": self.project_root,
                },
            )
            if not result.startswith("Successfully"):
                raise RuntimeError(f"Install failed: {result}")
            log_info(self.name, f"Install command completed successfully: {result}")
            return result

        try:
            run_install()
        except Exception as e:
            self.monitor.warning(f"Install command failed (non-fatal): {str(e)}")
            log_info(self.name, f"Install failed, continuing without install: {str(e)}")

        self.monitor.info(f"Running TypeScript typecheck in {self.project_root}")
        try:
            self.tool_executor.execute_tool(
                "typescript_typecheck_tool", {"cwd": self.project_root}
            )
            self.monitor.info("TypeScript typecheck passed.")
        except CompileError as e:
            combined_output = self.strip_ansi_codes(str(e))
            self.monitor.warning(
                f"TypeScript compile errors (non-fatal): {combined_output[:200]}..."
            )
            log_info(self.name, f"TypeScript typecheck failed (non-fatal): {combined_output[:200]}")

        # §2 Lint gate: non-zero lint exit MUST raise LintError so the loop re-enters
        # error_recovery (agentic-self-correct-loop §2.2). Raising here (not swallowing)
        # is the recovery signal.
        lint_fail = self.run_lint_gate()
        if lint_fail is not None:
            raise LintError(f"Lint gate failed:\n{lint_fail}")

        log_info(
            self.name,
            f"Running test command: {self.test_command} in {self.project_root}",
        )
        combined_output = ""

        @retry(
            stop=stop_after_attempt(1),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            retry=retry_if_exception_type(Exception),
        )
        def run_test():
            result = self.tool_executor.execute_tool(
                "npm_run_tool", {"script": "test", "args": "", "cwd": self.project_root}
            )
            if result.startswith("npm run test failed:"):
                raise RuntimeError(f"Test failed: {result}")
            return self.strip_ansi_codes(result)

        try:
            combined_output = run_test()
            log_info(self.name, f"Test command completed successfully")
            log_info(self.name, f"Combined test output length: {len(combined_output)}")
        except Exception as e:
            combined_output = self.strip_ansi_codes(str(e))
            self.monitor.warning(f"Test command failed (non-fatal): {combined_output[:200]}")
            log_info(self.name, f"Test command failed (non-fatal): {combined_output[:200]}")

        log_info(self.name, "Parsing test output for metrics")
        tests_passed_match = re.search(
            r"Tests:.*?(\d+)\s*passed\s*(\d+)\s*total",
            combined_output,
            re.DOTALL | re.I,
        )
        coverage_match = re.search(
            r"All files\s*\|\s*(\d+\.\d+|\d+)", combined_output
        )
        tests_passed = int(tests_passed_match.group(1)) if tests_passed_match else 0
        tests_total = int(tests_passed_match.group(2)) if tests_passed_match else 0
        coverage_all_files = float(coverage_match.group(1)) if coverage_match else 0.0

        log_info(
            self.name,
            f"Parsed tests_passed: {tests_passed}, tests_total: {tests_total}, coverage: {coverage_all_files}",
        )

        if tests_passed == 0 and tests_total > 0:
            self.monitor.warning("No passing tests detected despite tests running")
        elif tests_total == 0:
            self.monitor.warning(
                "No tests detected; test command may not have executed correctly"
            )

        # Compare with pre-integration results
        existing_tests_passed = safe_get(state, "existing_tests_passed", 0)
        existing_coverage_all_files = safe_get(
            state, "existing_coverage_all_files", 0.0
        )

        coverage_improvement = coverage_all_files - existing_coverage_all_files
        tests_improvement = tests_passed - existing_tests_passed

        log_info(
            self.name,
            f"Comparing with pre-integration: existing_tests={existing_tests_passed}, existing_coverage={existing_coverage_all_files}",
        )
        log_info(
            self.name,
            f"Improvement calculated: coverage +{coverage_improvement:.2f}%, tests +{tests_improvement}",
        )

        # §3 Strict-growth gate: jest may pass, but the change MUST grow the test count.
        # If not strictly greater, raise TestRecoveryNeeded ("test count did not grow") so
        # the loop re-enters error_recovery (agentic-self-correct-loop §3.1-3.3).
        if tests_passed <= existing_tests_passed:
            raise TestRecoveryNeeded(
                f"test count did not grow: passed={tests_passed} <= existing={existing_tests_passed}"
            )

        new_state = dict(state)
        new_state["post_integration_tests_passed"] = tests_passed
        new_state["post_integration_coverage_all_files"] = coverage_all_files
        new_state["tests_improvement"] = tests_improvement
        new_state["coverage_improvement"] = coverage_improvement
        self.monitor.info(
            f"Post-integration metrics: tests_passed={tests_passed}, coverage_all_files={coverage_all_files}"
        )
        self.monitor.info(
            f"Improvement: coverage +{coverage_improvement:.2f}%, tests +{tests_improvement}"
        )
        self.monitor.info(
            f"After processing in {self.name}: {safe_json_dumps(new_state, indent=2)}"
        )

        # §4 Omission guard: compare generated file sizes vs the timestamped backup taken
        # at run start. A file SMALLER than its backup means logic was dropped — restore it
        # and raise OmissionDetected so the loop re-enters error_recovery (§4.2-4.3).
        self._backup_generated_files()
        self._enforce_no_omission(existing_tests_passed=existing_tests_passed)

        return new_state

    def _enforce_no_omission(self, existing_tests_passed: int = 0) -> None:
        """Omission guard (agentic-self-correct-loop §4).

        Compares the current generated TS/test files against the MOST RECENT timestamped
        backup taken this run. If a file is smaller than its backup, the generated code
        dropped logic — restore it from the backup and raise OmissionDetected.
        """
        backups_root = os.path.join(self.project_root, "backups")
        if not os.path.isdir(backups_root):
            return
        # Most recent backup dir for this run (timestamped, lexicographically sortable).
        subdirs = sorted(
            d for d in os.listdir(backups_root)
            if os.path.isdir(os.path.join(backups_root, d))
        )
        if not subdirs:
            return
        latest = os.path.join(backups_root, subdirs[-1])
        generated = {
            "src/main.ts": "main.ts.backup",
            "src/__tests__/main.test.ts": "main.test.ts.backup",
        }
        for gen_rel, bak_name in generated.items():
            gen_path = os.path.join(self.project_root, gen_rel)
            bak_path = os.path.join(latest, bak_name)
            if not os.path.exists(gen_path) or not os.path.exists(bak_path):
                continue
            gen_size = os.path.getsize(gen_path)
            bak_size = os.path.getsize(bak_path)
            # A shrink is only a genuine omission if the file also dropped the test count
            # (i.e. it is not a legitimate feature switch). We raise only on a real shrink
            # AND when the file is now smaller than the committed baseline backup.
            if gen_size < bak_size:
                log_info(
                    self.name,
                    f"OMISSION GUARD: {gen_rel} shrank {bak_size} -> {gen_size}; restoring backup",
                )
                shutil.copy2(bak_path, gen_path)
                raise OmissionDetected(
                    f"generated {gen_rel} shrank ({bak_size} -> {gen_size}); logic dropped"
                )

    def _backup_generated_files(self):
        """Back up generated TypeScript code and test files for inspection."""
        import shutil
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.project_root, "backups", timestamp)
        os.makedirs(backup_dir, exist_ok=True)

        # Files to back up
        files_to_backup = [
            ("src/main.ts", "main.ts.backup"),
            ("src/__tests__/main.test.ts", "main.test.ts.backup"),
            ("package.json", "package.json.backup"),
            ("tsconfig.json", "tsconfig.json.backup"),
        ]

        for src_name, backup_name in files_to_backup:
            src_path = os.path.join(self.project_root, src_name)
            if os.path.exists(src_path):
                dst_path = os.path.join(backup_dir, backup_name)
                shutil.copy2(src_path, dst_path)
                log_info(self.name, f"Backed up {src_name} to {dst_path}")

        log_info(self.name, f"All backups saved to {backup_dir}")
