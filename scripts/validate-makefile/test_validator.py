#!/usr/bin/env python3
import pytest
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_makefile import MakefileValidator


@pytest.fixture
def validator():
    return MakefileValidator()


def test_parse_targets_clean(validator):
    targets = validator.parse_targets()
    assert len(targets) >= 50, f"Expected ~51 targets, got {len(targets)}"

    blacklist = {
        "been",
        "has",
        "never",
        "not",
        "rule",
        "search",
        "time",
        "updated",
        "done",
        "checked",
        "collect",
        "being",
        "the",
        "and",
    }
    false_positives = [t.name for t in targets if t.name.lower() in blacklist]
    assert not false_positives, f"False positives: {false_positives}"

    key_targets = {"build-app", "test-app", "setup-dev", "lint-python", "help", "clean"}
    missing = key_targets - {t.name for t in targets}
    assert not missing, f"Missing key targets: {missing}"


def test_parse_targets_rule_validation(validator):
    makefile_content = validator.makefile.read_text(encoding="utf-8")
    targets = validator.parse_targets()
    for t in targets:
        rule_match = re.search(
            rf"^\s*{re.escape(t.name)}\s*[:=]", makefile_content, re.MULTILINE
        )
        assert rule_match, f"No rule found for target '{t.name}'"


def test_extract_help_examples(validator):
    content = validator.makefile.read_text(encoding="utf-8")
    # Test for a known target with help
    help_build = validator._extract_help("build-app", content)
    assert len(help_build) > 0

    help_test = validator._extract_help("test-app", content)
    assert len(help_test) > 0
