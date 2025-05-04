import pytest
import os
import json
import re
from src.agentics import app
from github import GithubException

# Define paths to the fixtures directory and JSON file
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../fixtures')
EXPECTED_TICKET_JSON_FILE = os.path.join(FIXTURES_DIR, 'expected_ticket.json')

# Load expected JSON from file
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)

# Integration tests for the ticket interpreter workflow
# These tests use real GitHub API and LLM service calls.

@pytest.mark.integration
def test_full_workflow_well_structured():
    """Test the full workflow with a well-structured ticket, including code, test generation, and existing test metrics."""
    # Given
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}
    
    # When
    result = app.invoke(initial_state)
    
    # Then - Validate structured JSON output
    assert "result" in result, "Result key missing from workflow output"
    assert result["result"] == EXPECTED_TICKET_JSON, "Structured JSON does not match expected output"
    
    # Validate generated code presence and type
    assert "generated_code" in result, "Generated code is missing from the result"
    assert isinstance(result["generated_code"], str), "Generated code must be a string"
    assert len(result["generated_code"]) > 0, "Generated code cannot be empty"
    
    # Extract and validate TypeScript code block
    code_blocks = re.findall(r'```typescript(.*?)```', result["generated_code"], re.DOTALL)
    assert len(code_blocks) > 0, "No TypeScript code block found in generated code"
    code = code_blocks[0].strip()
    assert "function" in code or "class" in code, "Generated code should define a function or class for UUID generation"
    assert "uuid" in code.lower(), "Code should include UUID generation logic"
    assert "command" in code or "addCommand" in code, "Code should register an Obsidian command"
    assert "//" in code or "/*" in code, "Code should include comments"
    
    # Validate generated tests presence and type
    assert "generated_tests" in result, "Generated tests are missing from the result"
    assert isinstance(result["generated_tests"], str), "Generated tests must be a string"
    assert len(result["generated_tests"]) > 0, "Generated tests cannot be empty"
    
    # Extract and validate TypeScript test block
    test_blocks = re.findall(r'```typescript(.*?)```', result["generated_tests"], re.DOTALL)
    assert len(test_blocks) > 0, "No TypeScript test block found in generated tests"
    tests = test_blocks[0].strip()
    assert "test" in tests or "describe" in tests, "Generated tests should include a test block"
    assert "expect" in tests or "assert" in tests, "Tests should include assertions"
    assert "uuid" in tests.lower(), "Tests should verify UUID generation"
    
    # Validate test metrics from PreTestRunnerAgent
    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% line coverage based on current test output"

@pytest.mark.integration
def test_full_workflow_sloppy():
    """Test the full workflow with a sloppy ticket, including code, test generation, and existing test metrics."""
    # Given
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/22"
    initial_state = {"url": test_url}
    
    # When
    result = app.invoke(initial_state)
    
    # Then - Validate structured JSON output
    assert "result" in result, "Result key missing from workflow output"
    assert result["result"] == EXPECTED_TICKET_JSON, "Structured JSON does not match expected output"
    
    # Validate generated code presence and type
    assert "generated_code" in result, "Generated code is missing from the result"
    assert isinstance(result["generated_code"], str), "Generated code must be a string"
    assert len(result["generated_code"]) > 0, "Generated code cannot be empty"
    
    # Extract and validate TypeScript code block
    code_blocks = re.findall(r'```typescript(.*?)```', result["generated_code"], re.DOTALL)
    assert len(code_blocks) > 0, "No TypeScript code block found in generated code"
    code = code_blocks[0].strip()
    assert "function" in code or "class" in code, "Generated code should define a function or class for UUID generation"
    assert "uuid" in code.lower(), "Code should include UUID generation logic"
    assert "command" in code or "addCommand" in code, "Code should register an Obsidian command"
    assert "//" in code or "/*" in code, "Code should include comments"
    
    # Validate generated tests presence and type
    assert "generated_tests" in result, "Generated tests are missing from the result"
    assert isinstance(result["generated_tests"], str), "Generated tests must be a string"
    assert len(result["generated_tests"]) > 0, "Generated tests cannot be empty"
    
    # Extract and validate TypeScript test block
    test_blocks = re.findall(r'```typescript(.*?)```', result["generated_tests"], re.DOTALL)
    assert len(test_blocks) > 0, "No TypeScript test block found in generated tests"
    tests = test_blocks[0].strip()
    assert "test" in tests or "describe" in tests, "Generated tests should include a test block"
    assert "expect" in tests or "assert" in tests, "Tests should include assertions"
    assert "uuid" in tests.lower(), "Tests should verify UUID generation"
    
    # Validate test metrics from PreTestRunnerAgent
    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% line coverage based on current test output"

@pytest.mark.integration
def test_empty_ticket():
    """Test the workflow with an empty ticket."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/23"
    initial_state = {"url": test_url}
    with pytest.raises(ValueError, match="Empty ticket content"):
        app.invoke(initial_state)

@pytest.mark.integration
def test_invalid_url():
    """Test the workflow with an invalid GitHub URL."""
    invalid_url = "https://github.com/user/repo/pull/1"
    initial_state = {"url": invalid_url}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)

@pytest.mark.integration
def test_non_existent_issue():
    """Test the workflow with a non-existent issue."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    non_existent_url = f"{test_repo_url}/issues/99999"
    initial_state = {"url": non_existent_url}
    with pytest.raises(GithubException):
        app.invoke(initial_state)

@pytest.mark.integration
def test_non_existent_repo():
    """Test the workflow with a non-existent repository."""
    non_existent_url = "https://github.com/nonexistentuser/nonexistentrepo/issues/1"
    initial_state = {"url": non_existent_url}
    with pytest.raises(GithubException):
        app.invoke(initial_state)
