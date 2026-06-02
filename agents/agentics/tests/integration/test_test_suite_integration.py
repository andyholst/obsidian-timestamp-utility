"""
Integration tests for GoldStandardSuite.

Tests validate the gold standard test case management system:
- CRUD operations (add, get, remove cases)
- Criteria thresholds persistence
- JSON persistence and loading
- Case ID generation
"""

import json
import os
import tempfile

import pytest

from src.test_suite import GoldStandardSuite


class TestGoldStandardSuiteIntegration:
    """Integration tests for GoldStandardSuite CRUD and persistence."""

    @pytest.fixture
    def suite(self):
        tmpdir = tempfile.mkdtemp()
        suite_path = os.path.join(tmpdir, "gold_standard_suite.json")
        suite = GoldStandardSuite(suite_path)
        yield suite
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_add_case_returns_id(self, suite):
        case_id = suite.add_case(
            input_data="Add UUID v7 command",
            expected_output="export function generateUuidV7(): string { ... }",
        )
        assert case_id.startswith("gold_")
        assert len(case_id) > 4

    def test_add_case_persists_to_disk(self, suite):
        suite.add_case("input", "output")
        assert os.path.exists(suite.suite_path)
        with open(suite.suite_path) as f:
            data = json.load(f)
        assert len(data["cases"]) == 1

    def test_get_case_returns_full_record(self, suite):
        case_id = suite.add_case(
            input_data="Generate timestamps",
            expected_output="export function generateTimestamp(): string { return Date.now().toString(); }",
            criteria_thresholds={"has_actionable_output": 1.0, "structural_integrity": 0.9},
        )
        case = suite.get_case(case_id)
        assert case is not None
        assert case["input"] == "Generate timestamps"
        assert case["expected_output"].startswith("export function")
        assert case["criteria_thresholds"]["has_actionable_output"] == 1.0

    def test_get_case_nonexistent_returns_none(self, suite):
        assert suite.get_case("gold_9999") is None

    def test_get_all_cases(self, suite):
        suite.add_case("input1", "output1")
        suite.add_case("input2", "output2")
        cases = suite.get_all_cases()
        assert len(cases) == 2

    def test_remove_case(self, suite):
        case_id = suite.add_case("to remove", "output")
        assert suite.remove_case(case_id) is True
        assert suite.get_case(case_id) is None

    def test_remove_nonexistent_returns_false(self, suite):
        assert suite.remove_case("gold_9999") is False

    def test_default_criteria_thresholds(self, suite):
        case_id = suite.add_case("input", "output")
        case = suite.get_case(case_id)
        assert "criteria_thresholds" in case
        ct = case["criteria_thresholds"]
        assert ct["has_actionable_output"] == 1.0
        assert ct["structural_integrity"] == 0.8
        assert ct["requirement_coverage"] == 0.7
        assert ct["test_validation"] == 0.7

    def test_custom_criteria_thresholds(self, suite):
        custom = {"has_actionable_output": 0.5, "structural_integrity": 0.6,
                  "requirement_coverage": 0.4, "test_validation": 0.3}
        case_id = suite.add_case("input", "output", criteria_thresholds=custom)
        case = suite.get_case(case_id)
        assert case["criteria_thresholds"] == custom

    def test_case_id_sequential(self, suite):
        id1 = suite.add_case("first", "out1")
        id2 = suite.add_case("second", "out2")
        assert id1 == "gold_0000"
        assert id2 == "gold_0001"

    def test_suite_file_created_if_missing(self):
        tmpdir = tempfile.mkdtemp()
        suite_path = os.path.join(tmpdir, "subdir", "suite.json")
        try:
            suite = GoldStandardSuite(suite_path)
            assert os.path.exists(suite_path)
            with open(suite_path) as f:
                data = json.load(f)
            assert data["version"] == "1.0"
            assert data["cases"] == []
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_multiple_suites_isolated(self, tmp_path=None):
        """Two separate suite files don't leak data."""
        import shutil
        tmpdir = tempfile.mkdtemp()
        try:
            path1 = os.path.join(tmpdir, "suite1.json")
            path2 = os.path.join(tmpdir, "suite2.json")
            s1 = GoldStandardSuite(path1)
            s2 = GoldStandardSuite(path2)
            s1.add_case("s1 input", "s1 output")
            s2.add_case("s2 input", "s2 output")
            assert len(s1.get_all_cases()) == 1
            assert len(s2.get_all_cases()) == 1
            assert s1.get_all_cases()[0]["input"] == "s1 input"
            assert s2.get_all_cases()[0]["input"] == "s2 input"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
