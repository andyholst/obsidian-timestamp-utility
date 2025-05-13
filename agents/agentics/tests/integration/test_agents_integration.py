import pytest
import os
import json
import re
from sentence_transformers import SentenceTransformer, util
from src.agentics import app
from github import GithubException

# Define paths to the fixtures directory and JSON file
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../fixtures')
EXPECTED_TICKET_JSON_FILE = os.path.join(FIXTURES_DIR, 'expected_ticket.json')

# Load expected JSON from file
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)

# Load the sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Regex pattern to match function definitions (traditional, class, or arrow functions)
FUNCTION_PATTERN = re.compile(r'\bfunction\b|\bclass\b|=>')

def calculate_semantic_similarity(expected_text, actual_text):
    """
    Calculate the semantic similarity between two texts using sentence embeddings.
    Returns a percentage (0-100).
    """
    embeddings = model.encode([expected_text, actual_text], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    return similarity * 100

def compute_ticket_similarity(expected_ticket, refined_ticket):
    """
    Compute the overall semantic similarity between expected and refined tickets by averaging
    similarities across title, description, requirements, and acceptance criteria.
    """
    title_sim = calculate_semantic_similarity(expected_ticket["title"], refined_ticket["title"])
    desc_sim = calculate_semantic_similarity(expected_ticket["description"], refined_ticket["description"])
    expected_reqs = " ".join(expected_ticket["requirements"])
    refined_reqs = " ".join(refined_ticket["requirements"])
    reqs_sim = calculate_semantic_similarity(expected_reqs, refined_reqs)
    expected_ac = " ".join(expected_ticket["acceptance_criteria"])
    refined_ac = " ".join(refined_ticket["acceptance_criteria"])
    ac_sim = calculate_semantic_similarity(expected_ac, refined_ac)
    overall_similarity = (title_sim + desc_sim + reqs_sim + ac_sim) / 4
    return overall_similarity

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
    
    # Then - Validate refined ticket
    assert "refined_ticket" in result, "Refined ticket missing from workflow output"
    assert isinstance(result["refined_ticket"], dict), "Refined ticket must be a dict"
    assert "title" in result["refined_ticket"], "Title missing in refined ticket"
    
    refined = result["refined_ticket"]
    
    # Basic structural checks
    assert "description" in refined, "Description missing in refined ticket"
    assert "requirements" in refined, "Requirements missing in refined ticket"
    assert "acceptance_criteria" in refined, "Acceptance criteria missing in refined ticket"
    assert len(refined["requirements"]) >= 2, "Refined ticket should have at least 2 requirements"
    assert len(refined["acceptance_criteria"]) >= 2, "Refined ticket should have at least 2 acceptance criteria"
    
    # Calculate semantic similarity against expected JSON
    similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, refined)
    assert similarity >= 90, f"Semantic similarity {similarity:.2f}% is below 90% threshold"
    
    # Validate structured JSON output
    assert "result" in result, "Result key missing from workflow output"
    
    # Validate generated code presence and type
    assert "generated_code" in result, "Generated code is missing from the result"
    assert isinstance(result["generated_code"], str), "Generated code must be a string"
    assert len(result["generated_code"]) > 0, "Generated code cannot be empty"
    
    # Extract and validate TypeScript code block
    code_blocks = re.findall(r'```typescript(.*?)```', result["generated_code"], re.DOTALL)
    assert len(code_blocks) > 0, "No TypeScript code block found in generated code"
    code = code_blocks[0].strip()
    assert FUNCTION_PATTERN.search(code), "Generated code should include a function or class for UUID generation"
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
    
    # Validate relevant files from CodeExtractorAgent
    assert "relevant_files" in result, "Relevant files missing from workflow output"
    assert isinstance(result["relevant_files"], list), "Relevant files must be a list"
    assert len(result["relevant_files"]) > 0, "No relevant files found"
    for file_data in result["relevant_files"]:
        assert "file_path" in file_data, "File path missing in relevant file data"
        assert "content" in file_data, "Content missing in relevant file data"
        assert file_data["file_path"].startswith("src/"), "File path should be relative to project root"
        assert file_data["file_path"].endswith(".ts"), "Only TypeScript files should be included"
    
    # Specific file checks for UUID ticket
    relevant_paths = [file_data["file_path"] for file_data in result["relevant_files"]]
    assert "src/main.ts" in relevant_paths, "Expected 'src/main.ts' in relevant files for UUID implementation"
    assert "src/__tests__/main.test.ts" in relevant_paths, "Expected 'src/__tests__/main.test.ts' in relevant files for UUID testing"
    
    # General content checks for relevant files (pre-existing structure, not new feature content)
    for file_data in result["relevant_files"]:
        path = file_data["file_path"]
        content = file_data["content"]
        if path == "src/main.ts":
            assert "export default class" in content or "module.exports" in content, "Main file should define the plugin class"
        if path == "src/__tests__/main.test.ts":
            assert "describe" in content or "test" in content, "Test file should contain test blocks"

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
    
    # Then - Validate refined ticket
    assert "refined_ticket" in result, "Refined ticket missing from workflow output"
    assert isinstance(result["refined_ticket"], dict), "Refined ticket must be a dict"
    assert "title" in result["refined_ticket"], "Title missing in refined ticket"
    
    refined = result["refined_ticket"]
    
    # Basic structural checks
    assert "description" in refined, "Description missing in refined ticket"
    assert "requirements" in refined, "Requirements missing in refined ticket"
    assert "acceptance_criteria" in refined, "Acceptance criteria missing in refined ticket"
    assert len(refined["description"]) > 20, "Refined description should be more detailed than a sloppy ticket"
    assert len(refined["requirements"]) > 0, "Refined ticket should have at least one requirement"
    assert len(refined["acceptance_criteria"]) > 0, "Refined ticket should have at least one acceptance criterion"
    
    # Calculate semantic similarity against expected JSON
    similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, refined)
    assert similarity >= 80, f"Semantic similarity {similarity:.2f}% is below 80% threshold"
    
    # Validate structured JSON output
    assert "result" in result, "Result key missing from workflow output"
    
    # Validate generated code presence and type
    assert "generated_code" in result, "Generated code is missing from the result"
    assert isinstance(result["generated_code"], str), "Generated code must be a string"
    assert len(result["generated_code"]) > 0, "Generated code cannot be empty"
    
    # Extract and validate TypeScript code block
    code_blocks = re.findall(r'```typescript(.*?)```', result["generated_code"], re.DOTALL)
    assert len(code_blocks) > 0, "No TypeScript code block found in generated code"
    code = code_blocks[0].strip()
    assert FUNCTION_PATTERN.search(code), "Generated code should include a function or class for UUID generation"
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
    
    # Validate relevant files from CodeExtractorAgent
    assert "relevant_files" in result, "Relevant files missing from workflow output"
    assert isinstance(result["relevant_files"], list), "Relevant files must be a list"
    assert len(result["relevant_files"]) > 0, "No relevant files found"
    for file_data in result["relevant_files"]:
        assert "file_path" in file_data, "File path missing in relevant file data"
        assert "content" in file_data, "Content missing in relevant file data"
        assert file_data["file_path"].startswith("src/"), "File path should be relative to project root"
        assert file_data["file_path"].endswith(".ts"), "Only TypeScript files should be included"

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

@pytest.mark.integration
def test_full_workflow_no_match(mocker):
    """Test workflow with a ticket unrelated to the codebase, expecting no relevant files."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}
    
    # Mock TicketClarityAgent to return an unrelated ticket
    unrelated_ticket = {
        "title": "Update Documentation",
        "description": "Revise README with new installation steps.",
        "requirements": ["Add installation section"],
        "acceptance_criteria": ["README reflects changes"]
    }
    mocker.patch(
        "src.ticket_clarity_agent.TicketClarityAgent.process",
        return_value={"url": test_url, "refined_ticket": unrelated_ticket}
    )
    
    result = app.invoke(initial_state)
    assert "relevant_files" in result, "Relevant files missing from workflow output"
    assert len(result["relevant_files"]) == 0, "Expected no relevant files for unrelated ticket"

@pytest.mark.integration
def test_full_workflow_partial_match(mocker):
    """Test workflow with a ticket partially matching codebase keywords."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}
    
    # Mock TicketClarityAgent to return a ticket with keywords
    partial_ticket = {
        "title": "Enhance main functionality",
        "description": "Improve the main plugin logic.",
        "requirements": ["Update main logic"],
        "acceptance_criteria": ["Verify main works"]
    }
    mocker.patch(
        "src.ticket_clarity_agent.TicketClarityAgent.process",
        return_value={"url": test_url, "refined_ticket": partial_ticket}
    )
    
    result = app.invoke(initial_state)
    assert "relevant_files" in result, "Relevant files missing from workflow output"
    relevant_paths = [file_data["file_path"] for file_data in result["relevant_files"]]
    assert "src/main.ts" in relevant_paths, "Expected 'src/main.ts' for partial match on 'main'"
