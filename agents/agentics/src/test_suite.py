"""Gold standard test case management for regression testing."""

import json
import os
from datetime import datetime
from typing import Optional


class GoldStandardSuite:
    """Manages gold standard test cases: input + expected output pairs."""

    def __init__(self, suite_path: str = "/tmp/gold_standard_suite.json"):
        self.suite_path = suite_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.suite_path):
            os.makedirs(os.path.dirname(self.suite_path) or ".", exist_ok=True)
            with open(self.suite_path, "w") as f:
                json.dump({"cases": [], "version": "1.0"}, f)

    def add_case(self, input_data: str, expected_output: str,
                 criteria_thresholds: Optional[dict] = None) -> str:
        """Add a gold standard test case. Returns case_id."""
        cases = self._load_all()
        case_id = f"gold_{len(cases['cases']):04d}"
        entry = {
            "id": case_id,
            "input": input_data,
            "expected_output": expected_output,
            "criteria_thresholds": criteria_thresholds or {
                "has_actionable_output": 1.0,
                "structural_integrity": 0.8,
                "requirement_coverage": 0.7,
                "test_validation": 0.7,
            },
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        cases["cases"].append(entry)
        self._save_all(cases)
        return case_id

    def get_case(self, case_id: str) -> Optional[dict]:
        cases = self._load_all()
        for c in cases["cases"]:
            if c["id"] == case_id:
                return c
        return None

    def get_all_cases(self) -> list:
        return self._load_all()["cases"]

    def remove_case(self, case_id: str) -> bool:
        cases = self._load_all()
        original_len = len(cases["cases"])
        cases["cases"] = [c for c in cases["cases"] if c["id"] != case_id]
        self._save_all(cases)
        return len(cases["cases"]) < original_len

    def _load_all(self) -> dict:
        with open(self.suite_path) as f:
            return json.load(f)

    def _save_all(self, data: dict):
        with open(self.suite_path, "w") as f:
            json.dump(data, f, indent=2)
