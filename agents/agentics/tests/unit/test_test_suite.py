"""
Unit tests for GoldStandardSuite class.
Category 2 from tester-plan.md.
"""

import os
import json
import tempfile
import pytest

from src.test_suite import GoldStandardSuite


@pytest.fixture
def tmp_suite():
    with tempfile.TemporaryDirectory() as tmpdir:
        suite_path = os.path.join(tmpdir, "gold_suite.json")
        suite = GoldStandardSuite(suite_path=suite_path)
        yield suite


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestGoldStandardSuite:
    def test_add_case_returns_case_id(self, tmp_suite):
        case_id = tmp_suite.add_case("input_data", "expected_output")
        assert isinstance(case_id, str)
        assert case_id.startswith("gold_")

    def test_add_case_fields_match(self, tmp_suite):
        case_id = tmp_suite.add_case("my_input", "my_output")
        case = tmp_suite.get_case(case_id)
        assert case is not None
        assert case["id"] == case_id
        assert case["input"] == "my_input"
        assert case["expected_output"] == "my_output"
        assert "created_at" in case

    def test_add_case_with_custom_thresholds(self, tmp_suite):
        custom = {"has_actionable_output": 0.9, "structural_integrity": 0.7,
                  "requirement_coverage": 0.6, "test_validation": 0.5}
        case_id = tmp_suite.add_case("inp", "out", criteria_thresholds=custom)
        case = tmp_suite.get_case(case_id)
        assert case["criteria_thresholds"] == custom

    def test_get_case_returns_none_for_missing(self, tmp_suite):
        assert tmp_suite.get_case("gold_9999") is None

    def test_get_all_cases_empty(self, tmp_suite):
        assert tmp_suite.get_all_cases() == []

    def test_get_all_cases_returns_all(self, tmp_suite):
        ids = []
        for i in range(3):
            cid = tmp_suite.add_case(f"input_{i}", f"output_{i}")
            ids.append(cid)
        all_cases = tmp_suite.get_all_cases()
        assert len(all_cases) == 3
        returned_ids = [c["id"] for c in all_cases]
        assert returned_ids == ids

    def test_remove_case_returns_true(self, tmp_suite):
        case_id = tmp_suite.add_case("in", "out")
        assert tmp_suite.remove_case(case_id) is True

    def test_remove_case_actually_removes(self, tmp_suite):
        case_id = tmp_suite.add_case("in", "out")
        tmp_suite.remove_case(case_id)
        assert tmp_suite.get_case(case_id) is None

    def test_remove_case_returns_false_for_nonexistent(self, tmp_suite):
        assert tmp_suite.remove_case("gold_9999") is False

    def test_add_case_increments_ids(self, tmp_suite):
        id1 = tmp_suite.add_case("a", "b")
        id2 = tmp_suite.add_case("c", "d")
        assert id1 == "gold_0000"
        assert id2 == "gold_0001"


class TestGoldStandardPersistence:
    def test_persistence_across_instances(self, tmp_dir):
        suite_path = os.path.join(tmp_dir, "gold_suite.json")
        suite1 = GoldStandardSuite(suite_path=suite_path)
        case_id = suite1.add_case("persist_input", "persist_output")
        suite2 = GoldStandardSuite(suite_path=suite_path)
        case = suite2.get_case(case_id)
        assert case is not None
        assert case["input"] == "persist_input"

    def test_remove_persists_across_instances(self, tmp_dir):
        suite_path = os.path.join(tmp_dir, "gold_suite.json")
        suite1 = GoldStandardSuite(suite_path=suite_path)
        case_id = suite1.add_case("x", "y")
        suite1.remove_case(case_id)
        suite2 = GoldStandardSuite(suite_path=suite_path)
        assert suite2.get_case(case_id) is None

    def test_default_criteria_thresholds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_defaults_gs.json")
            suite = GoldStandardSuite(suite_path=path)
            case_id = suite.add_case("in", "out")
            case = suite.get_case(case_id)
            thresholds = case["criteria_thresholds"]
            assert thresholds == {
                "has_actionable_output": 1.0,
                "structural_integrity": 0.8,
                "requirement_coverage": 0.7,
                "test_validation": 0.7,
            }

    def test_persistence_get_all_cases(self, tmp_dir):
        suite_path = os.path.join(tmp_dir, "gold_suite.json")
        suite = GoldStandardSuite(suite_path=suite_path)
        suite.add_case("a", "1")
        suite.add_case("b", "2")
        suite.add_case("c", "3")
        suite2 = GoldStandardSuite(suite_path=suite_path)
        cases = suite2.get_all_cases()
        assert len(cases) == 3
