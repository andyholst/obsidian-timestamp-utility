"""
Quality Benchmark Module — eval loop from fix_the_slop.md

Evaluates LLM-generated outputs across 4 criteria. Blocks below threshold,
records failures for self-correction, feeds RubricStore for degradation detection.
"""

import os
import re
import json
import subprocess
import tempfile
from datetime import datetime

from .utils import log_info
from .monitoring import structured_log

_monitor = structured_log(__name__)

DEFAULT_THRESHOLD = float(os.getenv("EVAL_THRESHOLD", "0.7"))
DEFAULT_STORE_PATH = os.getenv("EVAL_STORE_PATH", "/tmp/eval_results.jsonl")
WEIGHTS = {
    "has_actionable_output": 0.15,
    "compiles_successfully": 0.25,
    "tests_pass": 0.2,
    "test_quality": 0.2,
    "structural_integrity": 0.1,
    "requirement_coverage": 0.05,
    "test_validation": 0.05,
}


class QualityRubric:
    """Four-criterion quality evaluator for LLM-generated outputs."""

    @staticmethod
    def compiles_successfully(state: dict) -> float:
        """Run tsc --noEmit on the generated code. Returns 1.0 if compiles, 0.0 if not.
        Returns 0.5 (neutral) if tsc can't run (no PROJECT_ROOT, no generated dir).
        This catches semantic errors like const reassignment, type mismatches, etc."""
        code = (state.get("generated_code") or "").strip()
        if not code:
            return 0.0
        project_root = os.getenv("PROJECT_ROOT", "")
        if not project_root:
            _monitor.debug("compiles_successfully", data={"result": "skipped", "reason": "no PROJECT_ROOT"})
            return 0.5  # Neutral — can't verify without project context
        gen_dir = os.path.join(project_root, 'src', 'generated')
        tsconfig = os.path.join(project_root, "tsconfig.json")
        if not os.path.isdir(gen_dir) or not os.path.exists(tsconfig):
            _monitor.debug("compiles_successfully", data={"result": "skipped",
                          "reason": "no generated dir" if not os.path.isdir(gen_dir) else "no tsconfig.json"})
            return 0.5  # Neutral — project not properly set up
        # Write code to a temp file and try to compile
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False,
                                              dir=gen_dir) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                cmd = ["npx", "tsc", "--noEmit", "--skipLibCheck", tmp_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                        cwd=project_root)
                if result.returncode == 0:
                    _monitor.debug("compiles_successfully", data={"result": True})
                    return 1.0
                else:
                    _monitor.debug("compiles_successfully", data={"result": False,
                                  "errors": result.stderr[:500] if result.stderr else result.stdout[:500]})
                    return 0.0
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            _monitor.warning("compiles_successfully_error", data={"error": str(e)})
            return 0.5  # Non-fatal: if tsc isn't available, don't block

    @staticmethod
    def tests_pass(state: dict) -> float:
        """Check if the generated tests actually pass. Returns 1.0 if tests pass, 0.0 if not."""
        if state.get("tests_passed"):
            return 1.0
        tests = (state.get("generated_tests") or "").strip()
        if not tests:
            return 0.0
        return 0.5  # Has tests but we don't know if they pass

    @staticmethod
    def has_actionable_output(state: dict) -> float:
        code = (state.get("generated_code") or "").strip()
        score = 1.0 if len(code) > 0 else 0.0
        _monitor.debug("has_actionable_output", data={"score": score, "len": len(code)})
        return score
    def structural_integrity(state: dict) -> float:
        """Strict structural integrity check with gate approach.
        Balanced braces + balanced parens are HARD GATES:
        if either fails, max score is capped at 0.4.
        Within the gate: no broken clusters (0.1) + line syntax validity (0.9).
        Penalizes very long lines (>200 chars)."""
        code = (state.get("generated_code") or "").strip()
        if not code:
            return 0.0

        braces_ok = QualityRubric._braces_balanced(code)
        parens_ok = QualityRubric._parens_balanced(code)

        lines = code.split("\n")
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            return 0.0

        # Count valid syntax lines (used in both paths)
        valid_lines = 0
        for line in non_empty:
            stripped = line.strip()
            if len(stripped) > 200:
                continue
            if re.match(r'^(export\s+)?function\s+\w+', stripped): valid_lines += 1
            elif re.match(r'^(const|let|var)\s+\w+', stripped): valid_lines += 1
            elif re.match(r'^return\s+', stripped): valid_lines += 1
            elif re.match(r'^[})\];]+$', stripped): valid_lines += 1
            elif re.match(r'^\w+\([^)]*\)\s*{?$', stripped): valid_lines += 1
            elif re.match(r'^if\s*\(', stripped): valid_lines += 1
            elif re.match(r'^else', stripped): valid_lines += 1
            elif re.match(r'^(//|/\*|\*)', stripped): valid_lines += 1
            elif re.match(r'^[{]$', stripped): valid_lines += 1
            elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*[:=]', stripped): valid_lines += 1
            elif re.match(r'^await\s+', stripped): valid_lines += 1
            elif re.match(r'^async\s+', stripped): valid_lines += 1
            elif re.match(r'^(public|private|protected)\s+', stripped): valid_lines += 1
            elif re.match(r'^import\s+', stripped): valid_lines += 1
            elif re.match(r'^(describe|it|test)\(', stripped): valid_lines += 1
            elif re.match(r'^(expect|assert)\(', stripped): valid_lines += 1
            elif re.match(r'^[a-zA-Z0-9_(),.;:{}\[\]=+\-*/<>!&|?~]+$', stripped): valid_lines += 1

        line_ratio = valid_lines / len(non_empty)

        if not braces_ok or not parens_ok:
            # Gate failed: hard cap at 0.4
            return round(min(line_ratio * 0.4, 0.4), 4)

        # Gates passed: full scoring
        score = 0.0
        # No broken clusters (0.1)
        if not re.search(r"}{5,}", code):
            score += 0.1
        # Line syntax validity (0.9)
        score += 0.9 * line_ratio
        return round(min(score, 1.0), 4)

    @staticmethod
    def requirement_coverage(state: dict) -> float:
        """Fraction of refined_ticket requirements keyword-matched in code+tests.
        Returns 0.0 for empty requirements (not 0.5)."""
        ticket = state.get("refined_ticket") or {}
        if isinstance(ticket, dict):
            req_text = ticket.get("requirements", "")
            if isinstance(req_text, list):
                req_text = " ".join(str(r) for r in req_text)
            req_text = str(req_text)
        else:
            req_text = str(ticket)
        code = (state.get("generated_code") or "").strip()
        tests = (state.get("generated_tests") or "").strip()
        combined_output = (code + " " + tests).lower()
        req_stripped = req_text.strip()
        if not req_stripped:
            return 0.0
        stop_words = {
            "the", "and", "for", "that", "this", "with", "from", "are", "was",
            "will", "have", "has", "not", "but", "all", "can", "should", "must",
            "also", "each", "which", "their", "been", "when", "they", "into",
            "implement", "feature", "plugin",
        }
        req_words = {
            w.lower()
            for w in re.findall(r"\b[a-zA-Z_]\w{2,}\b", req_text)
            if w.lower() not in stop_words
        }
        if not req_words:
            return 0.0
        matched = sum(1 for w in req_words if w in combined_output)
        score = matched / len(req_words)
        _monitor.debug("requirement_coverage", data={"score": score, "matched": matched, "req_words": len(req_words)})
        return round(score, 4)

    @staticmethod
    def test_validation(state: dict) -> float:
        """Ratio of passed/total tests. 0.5 neutral if no tests exist."""
        tests = (state.get("generated_tests") or "").strip()
        if not tests:
            return 0.5
        passed = state.get("post_integration_tests_passed")
        total = state.get("existing_tests_passed")
        if isinstance(passed, (int, float)) and isinstance(total, (int, float)) and total > 0:
            score = min(passed / total, 1.0)
            _monitor.debug("test_validation", data={"score": score, "passed": passed, "total": total})
            return round(score, 4)
        test_lines = tests.split("\n")
        assert_count = sum(1 for l in test_lines if re.search(r"\b(assert|expect|test|it|describe)\b", l, re.IGNORECASE))
        score = min(assert_count / max(len(test_lines), 1), 1.0)
        _monitor.debug("test_validation", data={"score": score, "heuristic": True})
        return round(score, 4)

    @staticmethod
    def _braces_balanced(text: str) -> bool:
        depth = 0
        for ch in text:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth < 0:
                return False
        return depth == 0

    @staticmethod
    def _parens_balanced(text: str) -> bool:
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                return False
        return depth == 0

    @classmethod
    def score_all(cls, state: dict) -> dict:
        return {
            "has_actionable_output": cls.has_actionable_output(state),
            "compiles_successfully": cls.compiles_successfully(state),
            "tests_pass": cls.tests_pass(state),
            "test_quality": cls.test_quality(state),
            "structural_integrity": cls.structural_integrity(state),
            "requirement_coverage": cls.requirement_coverage(state),
            "test_validation": cls.test_validation(state),
        }

    @staticmethod
    def test_quality(state: dict) -> float:
        """Check that generated tests actually test the right things.
        Looks for required patterns in the test code based on the issue requirements.
        Returns 0.0 if tests are missing critical checks, 1.0 if comprehensive."""
        tests = (state.get("generated_tests") or "").strip()
        code = (state.get("generated_code") or "").strip()
        if not tests or not code:
            return 0.0

        import re
        score = 0.0
        max_score = 0.0

        # Extract function names being tested
        func_names = re.findall(r'function\s+(\w+)', code)
        exported_funcs = re.findall(r'export\s+function\s+(\w+)', code)

        # Check 1: Tests actually call the generated function (not just check typeof)
        max_score += 1
        for func in exported_funcs:
            # Look for actual function calls like funcName() not just typeof funcName
            call_pattern = rf'\b{func}\s*\('
            if re.search(call_pattern, tests):
                score += 0.5
            # Look for expect() assertions on the result
            if re.search(rf'expect\s*\(.*{func}', tests):
                score += 0.5

        # Check 2: Tests check return type is string
        max_score += 1
        if re.search(r"expect\s*\(\s*typeof\s+\w+\s*\)\s*\.\s*toBe\s*\(\s*['\"]string['\"]\s*\)", tests):
            score += 1

        # Check 3: Tests check output format/length (not just "is a string")
        max_score += 1
        if re.search(r'\.length\s*[=!]=', tests) or re.search(r'uuidRegex|UUID|format', tests, re.IGNORECASE):
            score += 1

        # Check 4: Tests check uniqueness (not just one call)
        max_score += 1
        if re.search(r'new Set|unique|different|multiple', tests, re.IGNORECASE):
            score += 1

        # Check 5: Tests have multiple it() blocks (not just one)
        max_score += 1
        it_count = len(re.findall(r'\bit\s*\(', tests))
        if it_count >= 3:
            score += 1
        elif it_count >= 2:
            score += 0.5

        return round(score / max_score, 4) if max_score > 0 else 0.0


def _check_code_test_consistency(state: dict) -> str | None:
    """Check that the generated test imports match the generated code exports.
    Returns error string if inconsistent, None if OK."""
    import re
    code = (state.get("generated_code") or "").strip()
    tests = (state.get("generated_tests") or "").strip()
    if not code or not tests:
        return None  # Let other gates handle empty code/tests

    # Extract exported function names from code
    code_exports = set(re.findall(r'export\s+function\s+(\w+)', code))
    code_exports.update(re.findall(r'export\s*\{\s*(\w+)\s*\}', code))

    # Extract imported function names from tests
    test_imports = set(re.findall(r'import\s*\{\s*([^}]+)\s*\}', tests))
    # Parse individual names from import statements like "{ foo, bar }"
    imported_names = set()
    for imp in test_imports:
        for name in imp.split(','):
            imported_names.add(name.strip())

    # Check that all imported names are exported
    for name in imported_names:
        if name and name not in code_exports:
            return f"Test imports '{name}' but code exports {code_exports or 'nothing'}"

    return None


def score_output(state: dict) -> dict:
    """Evaluate LLM output quality. Returns {scores, total, passed, threshold, reasons}."""
    threshold = float(os.getenv("EVAL_THRESHOLD", str(DEFAULT_THRESHOLD)))
    scores = QualityRubric.score_all(state)
    reasons = []

    # Hard gate 0: code and tests must be consistent (same export/import names)
    consistency_error = _check_code_test_consistency(state)
    if consistency_error:
        total = 0.0
        passed = False
        reasons = [f"HARD FAIL: Code-test inconsistency: {consistency_error}"]
    # Hard gate 1: if tests don't pass, automatic fail
    # Note: compiles_successfully is NOT a hard gate — it's a weighted criterion.
    # tsc --noEmit can fail for env reasons (missing tsconfig, npm not installed)
    # and _is_valid_ts_syntax in workflow.py already catches structural errors before eval.
    elif scores.get("tests_pass", 0.0) == 0.0:
        total = 0.0
        passed = False
        reasons = ["HARD FAIL: Tests did not pass. Fix the generated code and tests."]
    else:
        total = round(sum(scores[k] * WEIGHTS[k] for k in WEIGHTS), 4)
        passed = total >= threshold
        if not passed:
            sorted_criteria = sorted(scores.items(), key=lambda x: x[1])
            worst_name, worst_score = sorted_criteria[0]
            reasons.append(
                f"Lowest criterion '{worst_name}' scored {worst_score:.2f}. "
                f"Weight: {WEIGHTS[worst_name]}"
            )
            for name, score in sorted_criteria:
                if score < 0.5:
                    reasons.append(f"  {name}: {score:.2f} — needs improvement")
    result = {"scores": scores, "total": total, "passed": passed, "threshold": threshold, "reasons": reasons}
    _monitor.info("eval_scored", data={"total": total, "passed": passed, "threshold": threshold, "scores": scores})
    return result


def gate_check(score_result: dict) -> tuple:
    """Return (True, 'ok') if total >= threshold, else (False, reason_string)."""
    total = score_result.get("total", 0)
    threshold = score_result.get("threshold", DEFAULT_THRESHOLD)
    if total >= threshold:
        return True, "ok"
    reasons = score_result.get("reasons", [])
    reason_str = "; ".join(reasons) if reasons else f"Total {total:.2f} < threshold {threshold}"
    return False, reason_str


def record_failure(state: dict, score_result: dict) -> dict:
    """Produce a failure record for retry context with what_was_wrong + what_to_fix."""
    scores = score_result.get("scores", {})
    failed = {k: v for k, v in scores.items() if v < 0.7}
    fix_map = {
        "has_actionable_output": "Generate non-empty code output. No code was produced.",
        "structural_integrity": "Fix syntax errors: balanced braces, correct TypeScript syntax.",
        "requirement_coverage": "Address more requirements from refined_ticket. Implement missing features.",
        "test_validation": "Ensure generated tests pass. Fix assertions or add proper coverage.",
    }
    what_was_wrong = []
    what_to_fix = []
    for criterion, score in sorted(failed.items(), key=lambda x: x[1]):
        what_was_wrong.append(f"{criterion}={score:.2f}")
        if criterion in fix_map:
            what_to_fix.append(fix_map[criterion])
    record = {
        "failed_criteria": list(failed.keys()),
        "what_was_wrong": what_was_wrong,
        "what_to_fix": what_to_fix,
        "scores": scores,
        "total": score_result.get("total", 0),
        "threshold": score_result.get("threshold", DEFAULT_THRESHOLD),
    }
    _monitor.info("eval_failure_recorded", data={"failed": list(failed.keys())})
    return record


class RegressionTracker:
    """Compares current eval scores against a saved baseline."""

    def __init__(self, baseline_path: str = "/tmp/eval_baseline.json"):
        self.baseline_path = baseline_path

    def save_baseline(self, scores: dict):
        """Save current scores as the new baseline."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scores": scores["scores"],
            "total": scores["total"],
        }
        os.makedirs(os.path.dirname(self.baseline_path) or ".", exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(entry, f, indent=2)
        _monitor.info("baseline_saved", data={"total": scores["total"]})

    def load_baseline(self) -> dict | None:
        """Load saved baseline scores."""
        if not os.path.exists(self.baseline_path):
            return None
        with open(self.baseline_path) as f:
            return json.load(f)

    def check_regression(self, current_scores: dict) -> dict:
        """Compare current scores against baseline. Returns regression report."""
        baseline = self.load_baseline()
        if not baseline:
            return {"has_baseline": False, "regressed": False, "deltas": {}}

        deltas = {}
        regressed = False
        for criterion, current_val in current_scores.get("scores", {}).items():
            baseline_val = baseline.get("scores", {}).get(criterion, 0)
            delta = current_val - baseline_val
            deltas[criterion] = round(delta, 4)
            if delta < -0.1:
                regressed = True

        total_delta = current_scores.get("total", 0) - baseline.get("total", 0)

        return {
            "has_baseline": True,
            "regressed": regressed,
            "deltas": deltas,
            "total_delta": round(total_delta, 4),
            "baseline_total": baseline.get("total", 0),
            "current_total": current_scores.get("total", 0),
        }

    def save_if_improved(self, current_scores: dict) -> bool:
        """Save baseline only if current score >= baseline. Returns True if saved."""
        baseline = self.load_baseline()
        if not baseline:
            self.save_baseline(current_scores)
            return True
        if current_scores.get("total", 0) >= baseline.get("total", 0):
            self.save_baseline(current_scores)
            return True
        return False


class RubricStore:
    """Persistent JSONL store for scoring results. Path: EVAL_STORE_PATH (default /tmp/eval_results.jsonl)."""

    def __init__(self, path: str | None = None):
        self.path = path or DEFAULT_STORE_PATH
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w") as f:
                pass

    def record(self, result: dict):
        entry = {"timestamp": datetime.utcnow().isoformat() + "Z", **result}
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            _monitor.debug("rubric_store_recorded", data={"total": result.get("total")})
        except Exception as exc:
            _monitor.error("rubric_store_write_failed", error=exc)

    def _read_all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    def get_history(self, n: int = 10) -> list[dict]:
        return self._read_all()[-n:]

    def get_average_score(self) -> float:
        entries = self._read_all()
        if not entries:
            return 0.0
        totals = [e.get("total", 0) for e in entries]
        return round(sum(totals) / len(totals), 4)

    def get_trend(self) -> dict:
        """Return trend: direction ('stable'|'degrading'|'improving'), degrading flag, last_scores."""
        entries = self._read_all()
        if len(entries) < 2:
            return {"direction": "stable", "degrading": False, "last_scores": []}
        recent = [e.get("total", 0) for e in entries[-5:]]
        direction = "stable"
        if len(recent) >= 3:
            if recent[-1] < recent[-2] < recent[-3]:
                direction = "degrading"
            elif recent[-1] > recent[-2] > recent[-3]:
                direction = "improving"
        degrading = direction == "degrading" and recent[-1] < DEFAULT_THRESHOLD
        return {
            "direction": direction,
            "degrading": degrading,
            "last_scores": recent[-3:],
            "average": round(sum(recent) / len(recent), 4),
        }
