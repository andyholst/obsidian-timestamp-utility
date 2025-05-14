import pytest
import os
import json
import re
import shutil
from unittest.mock import patch
from sentence_transformers import SentenceTransformer, util
from src.agentics import app, pre_test_runner_agent, code_extractor_agent, code_integrator_agent
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
    similarities across title, description, requirements, and acceptance_criteria.
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

def extract_content(text):
    """
    Extract content from markdown code blocks, with optional TypeScript marker.
    Returns the first block found or the entire text if no blocks exist.
    """
    pattern = r'```(?:typescript)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[0].strip() if matches else text.strip()

# Helper function to extract method name and command ID from generated code
def extract_method_and_command(generated_code):
    """Extract method name and command ID from generated code using regex."""
    method_match = re.search(r'public\s+(\w+)\s*\(', generated_code)
    command_match = re.search(r"this\.addCommand\(\{\s*id:\s*['\"]([^'\"]+)['\"]", generated_code)
    method_name = method_match.group(1) if method_match else None
    command_id = command_match.group(1) if command_match else None
    return method_name, command_id

# Helper function to extract describe lines from generated tests
def extract_describe_lines(generated_tests):
    """Extract describe block lines from generated tests."""
    return [line.strip() for line in generated_tests.split('\n') if line.strip().startswith('describe(')]

# Fixture to backup /project/src before each integration test and restore it after
@pytest.fixture(autouse=True)
def backup_src(request, tmp_path):
    """
    Backup /project/src to a temporary directory before each integration test
    and restore it after the test completes.
    """
    if request.node.get_closest_marker("integration"):
        backup_dir = tmp_path / "backup_src"
        shutil.copytree('/project/src', str(backup_dir))
        yield
        # Restore /project/src from the backup after the test
        shutil.rmtree('/project/src')
        shutil.copytree(str(backup_dir), '/project/src')
    else:
        yield

# Integration tests for the ticket interpreter workflow
# These tests use real GitHub API and LLM service calls and operate on the actual /project/src.

@pytest.mark.integration
def test_full_workflow_well_structured():
    """
    Test the full workflow with a well-structured ticket, ensuring the specific TypeScript content is written to files
    in /project/src and existing functions/tests are preserved.
    """
    # Given
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}
    
    # When (no patching, agents use actual /project)
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
    code = extract_content(result["generated_code"])
    assert FUNCTION_PATTERN.search(code), "Generated code should include functions or classes"
    assert "uuid" in code.lower(), "Code should include UUID generation logic"
    assert "command" in code or "addCommand" in code, "Code should register an Obsidian command"
    
    # Extract method name and command ID from generated code
    method_name, command_id = extract_method_and_command(code)
    assert method_name is not None, "Could not find method name in generated code"
    assert command_id is not None, "Could not find command ID in generated code"
    
    # Validate generated tests presence and type
    assert "generated_tests" in result, "Generated tests are missing from the result"
    assert isinstance(result["generated_tests"], str), "Generated tests must be a string"
    assert len(result["generated_tests"]) > 0, "Generated tests cannot be empty"
    
    # Extract and validate TypeScript test block
    tests = extract_content(result["generated_tests"])
    assert "test" in tests or "describe" in tests, "Generated tests should include a test block"
    assert "expect" in tests or "assert" in tests, "Tests should include assertions"
    assert "TimestampPlugin" in tests, "Tests should reference TimestampPlugin"
    assert "uuid" in tests.lower(), "Tests should verify UUID generation"
    
    # Extract describe lines from generated tests
    describe_lines = extract_describe_lines(tests)
    assert len(describe_lines) >= 2, "Expected at least two describe blocks in generated tests"
    
    # Validate test metrics from PreTestRunnerAgent
    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% line coverage based on current test output"
    
    # Validate relevant code and test files from CodeExtractorAgent
    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    assert isinstance(result["relevant_code_files"], list), "Relevant code files must be a list"
    assert isinstance(result["relevant_test_files"], list), "Relevant test files must be a list"
    assert len(result["relevant_code_files"]) + len(result["relevant_test_files"]) > 0, "No relevant files found"
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        assert "file_path" in file_data, "File path missing in relevant file data"
        assert "content" in file_data, "Content missing in relevant file data"
        assert file_data["file_path"].startswith("src/"), "File path should be relative to project root"
        assert file_data["file_path"].endswith(".ts"), "Only TypeScript files should be included"
    
    # Specific file checks for UUID ticket
    code_paths = [file_data["file_path"] for file_data in result["relevant_code_files"]]
    test_paths = [file_data["file_path"] for file_data in result["relevant_test_files"]]
    assert "src/main.ts" in code_paths, "Expected 'src/main.ts' in relevant code files for UUID implementation"
    assert "src/__tests__/main.test.ts" in test_paths, "Expected 'src/__tests__/main.test.ts' in relevant test files for UUID testing"
    
    # General content checks for relevant files (pre-existing structure, not new feature content)
    for file_data in result["relevant_code_files"]:
        path = file_data["file_path"]
        content = file_data["content"]
        if path == "src/main.ts":
            assert "export default class" in content or "module.exports" in content, "Main file should define the plugin class"
    for file_data in result["relevant_test_files"]:
        path = file_data["file_path"]
        content = file_data["content"]
        if path == "src/__tests__/main.test.ts":
            assert "describe" in content or "test" in content, "Test file should contain test blocks"
    
    # Validate CodeIntegratorAgent integration in actual /project directory
    generated_code = extract_content(result['generated_code'])
    generated_tests = extract_content(result['generated_tests'])
    original_sizes = {f['file_path']: len(f['content']) for f in result["relevant_code_files"] + result["relevant_test_files"]}
    
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        file_path = file_data['file_path']
        actual_file_path = os.path.join('/project', file_path)
        assert os.path.exists(actual_file_path), f"{file_path} should exist in project directory"
        with open(actual_file_path, 'r') as f:
            content = f.read()
            new_size = len(content)
            if file_path in test_paths:
                for describe_line in describe_lines:
                    assert describe_line in content, f"Describe block '{describe_line}' not found in {file_path}"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing test stuff we expect to still be there
                assert "TimestampPlugin" in content, "Test file should reference TimestampPlugin"
                assert "describe" in content, "Test file should contain describe blocks"
                assert "generateTimestamp" in content, "Test file should test generateTimestamp"
                assert "insert-timestamp" in content, "Test file should test insert-timestamp command"
                assert "rename-with-timestamp" in content, "Test file should test rename-with-timestamp command"
            else:
                assert method_name in content, f"Method {method_name} not found in {file_path}"
                assert command_id in content, f"Command ID {command_id} not found in {file_path}"
                assert "//" in content or "/*" in content, "Integrated code file should include comments from existing code"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing code stuff we expect to still be there
                assert "parseDateString" in content, "Code file should contain parseDateString"
                assert "DateRangeModal" in content, "Code file should contain DateRangeModal"
                assert "TimestampPlugin" in content, "Code file should contain TimestampPlugin"
                assert "generateTimestamp" in content, "Code file should contain generateTimestamp"
                assert "renameFile" in content, "Code file should contain renameFile"

@pytest.mark.integration
def test_full_workflow_sloppy():
    """
    Test the full workflow with a sloppy ticket, ensuring the TypeScript content is integrated into /project/src
    and existing content preserved.
    """
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/22"
    initial_state = {"url": test_url}

    result = app.invoke(initial_state)

    assert "refined_ticket" in result, "Refined ticket missing from workflow output"
    assert isinstance(result["refined_ticket"], dict), "Refined ticket must be a dict"
    assert "title" in result["refined_ticket"], "Title missing in refined ticket"

    refined = result["refined_ticket"]
    assert "description" in refined, "Description missing in refined ticket"
    assert "requirements" in refined, "Requirements missing in refined ticket"
    assert "acceptance_criteria" in refined, "Acceptance criteria missing in refined ticket"
    assert len(refined["description"]) > 20, "Refined description should be more detailed than a sloppy ticket"
    assert len(refined["requirements"]) > 0, "Refined ticket should have at least one requirement"
    assert len(refined["acceptance_criteria"]) > 0, "Refined ticket should have at least one acceptance criterion"

    similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, refined)
    assert similarity >= 80, f"Semantic similarity {similarity:.2f}% is below 80% threshold"

    assert "result" in result, "Result key missing from workflow output"
    assert "generated_code" in result, "Generated code is missing from the result"
    assert isinstance(result["generated_code"], str), "Generated code must be a string"
    assert len(result["generated_code"]) > 0, "Generated code cannot be empty"

    code = extract_content(result["generated_code"])
    assert FUNCTION_PATTERN.search(code), "Generated code should include a function or class"
    assert "uuid" in code.lower(), "Code should include UUID generation logic"
    assert "command" in code or "addCommand" in code, "Code should register an Obsidian command"

    # Extract method name and command ID from generated code
    method_name, command_id = extract_method_and_command(code)
    assert method_name is not None, "Could not find method name in generated code"
    assert command_id is not None, "Could not find command ID in generated code"

    assert "generated_tests" in result, "Generated tests are missing from the result"
    assert isinstance(result["generated_tests"], str), "Generated tests must be a string"
    assert len(result["generated_tests"]) > 0, "Generated tests cannot be empty"

    tests = extract_content(result["generated_tests"])
    assert "test" in tests or "describe" in tests, "Generated tests should include a test block"
    assert "expect" in tests or "assert" in tests, "Tests should include assertions"
    assert "TimestampPlugin" in tests, "Tests should reference TimestampPlugin"
    assert "uuid" in tests.lower(), "Tests should verify UUID generation"

    # Extract describe lines from generated tests
    describe_lines = extract_describe_lines(tests)
    assert len(describe_lines) >= 2, "Expected at least two describe blocks in generated tests"

    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% line coverage based on current test output"

    # Validate relevant code and test files from CodeExtractorAgent
    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    assert isinstance(result["relevant_code_files"], list), "Relevant code files must be a list"
    assert isinstance(result["relevant_test_files"], list), "Relevant test files must be a list"
    assert len(result["relevant_code_files"]) + len(result["relevant_test_files"]) > 0, "No relevant files found"
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        assert "file_path" in file_data, "File path missing in relevant file data"
        assert "content" in file_data, "Content missing in relevant file data"
        assert file_data["file_path"].startswith("src/"), "File path should be relative to project root"
        assert file_data["file_path"].endswith(".ts"), "Only TypeScript files should be included"

    generated_code = extract_content(result['generated_code'])
    generated_tests = extract_content(result['generated_tests'])
    original_sizes = {f['file_path']: len(f['content']) for f in result["relevant_code_files"] + result["relevant_test_files"]}

    test_paths = [file_data["file_path"] for file_data in result["relevant_test_files"]]
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        file_path = file_data['file_path']
        actual_file_path = os.path.join('/project', file_path)
        assert os.path.exists(actual_file_path), f"{file_path} should exist in project directory"
        with open(actual_file_path, 'r') as f:
            content = f.read()
            new_size = len(content)
            if file_path in test_paths:
                for describe_line in describe_lines:
                    assert describe_line in content, f"Describe block '{describe_line}' not found in {file_path}"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing test stuff we expect to still be there
                assert "TimestampPlugin" in content, "Test file should reference TimestampPlugin"
                assert "describe" in content, "Test file should contain describe blocks"
                assert "generateTimestamp" in content, "Test file should test generateTimestamp"
                assert "insert-timestamp" in content, "Test file should test insert-timestamp command"
                assert "rename-with-timestamp" in content, "Test file should test rename-with-timestamp command"
            else:
                assert method_name in content, f"Method {method_name} not found in {file_path}"
                assert command_id in content, f"Command ID {command_id} not found in {file_path}"
                assert "//" in content or "/*" in content, "Integrated code file should include comments from existing code"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing code stuff we expect to still be there
                assert "parseDateString" in content, "Code file should contain parseDateString"
                assert "DateRangeModal" in content, "Code file should contain DateRangeModal"
                assert "TimestampPlugin" in content, "Code file should contain TimestampPlugin"
                assert "generateTimestamp" in content, "Code file should contain generateTimestamp"
                assert "renameFile" in content, "Code file should contain renameFile"

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
    """Test workflow with a ticket unrelated to the codebase, expecting new files to be created in /project/src."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}

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

    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    assert len(result["relevant_code_files"]) == 1, "Expected one new code file for unrelated ticket"
    assert len(result["relevant_test_files"]) == 1, "Expected one new test file for unrelated ticket"
    assert result["relevant_code_files"][0]["file_path"] == "src/update.ts", "Expected new code file 'src/update.ts'"
    assert result["relevant_test_files"][0]["file_path"] == "src/__tests__/update.test.ts", "Expected new test file 'src/__tests__/update.test.ts'"

    generated_code = extract_content(result['generated_code'])
    generated_tests = extract_content(result['generated_tests'])
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        file_path = file_data['file_path']
        actual_file_path = os.path.join('/project', file_path)
        assert os.path.exists(actual_file_path), f"{file_path} should exist in project directory"
        with open(actual_file_path, 'r') as f:
            content = f.read()
            if file_data['file_path'] in result["relevant_test_files"][0]["file_path"]:
                assert generated_tests in content, f"Generated tests not found in {file_data['file_path']}"
            else:
                assert generated_code in content, f"Generated code not found in {file_data['file_path']}"

@pytest.mark.integration
def test_full_workflow_partial_match(mocker):
    """Test workflow with a ticket partially matching codebase keywords, updating /project/src."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}

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

    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    code_paths = [file_data["file_path"] for file_data in result["relevant_code_files"]]
    assert "src/main.ts" in code_paths, "Expected 'src/main.ts' for partial match on 'main'"

    generated_code = extract_content(result['generated_code'])
    generated_tests = extract_content(result['generated_tests'])

    # Extract method name and command ID from generated code
    method_name, command_id = extract_method_and_command(generated_code)
    assert method_name is not None, "Could not find method name in generated code"
    assert command_id is not None, "Could not find command ID in generated code"

    # Extract describe lines from generated tests
    describe_lines = extract_describe_lines(generated_tests)
    assert len(describe_lines) >= 2, "Expected at least two describe blocks in generated tests"

    original_sizes = {f['file_path']: len(f['content']) for f in result["relevant_code_files"] + result["relevant_test_files"]}

    test_paths = [file_data["file_path"] for file_data in result["relevant_test_files"]]
    for file_data in result["relevant_code_files"] + result["relevant_test_files"]:
        file_path = file_data['file_path']
        actual_file_path = os.path.join('/project', file_path)
        assert os.path.exists(actual_file_path), f"{file_path} should exist in project directory"
        with open(actual_file_path, 'r') as f:
            content = f.read()
            new_size = len(content)
            if file_path in test_paths:
                for describe_line in describe_lines:
                    assert describe_line in content, f"Describe block '{describe_line}' not found in {file_path}"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing test stuff we expect to still be there
                assert "TimestampPlugin" in content, "Test file should reference TimestampPlugin"
                assert "describe" in content, "Test file should contain describe blocks"
                assert "generateTimestamp" in content, "Test file should test generateTimestamp"
                assert "insert-timestamp" in content, "Test file should test insert-timestamp command"
                assert "rename-with-timestamp" in content, "Test file should test rename-with-timestamp command"
            else:
                assert method_name in content, f"Method {method_name} not found in {file_path}"
                assert command_id in content, f"Command ID {command_id} not found in {file_path}"
                assert "//" in content or "/*" in content, "Integrated code file should include comments from existing code"
                assert new_size >= original_sizes.get(file_path, 0), f"{file_path} size should not decrease"
                # Existing code stuff we expect to still be there
                assert "parseDateString" in content, "Code file should contain parseDateString"
                assert "DateRangeModal" in content, "Code file should contain DateRangeModal"
                assert "TimestampPlugin" in content, "Code file should contain TimestampPlugin"
                assert "generateTimestamp" in content, "Code file should contain generateTimestamp"
                assert "renameFile" in content, "Code file should contain renameFile"
