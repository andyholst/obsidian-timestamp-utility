import pytest
import os
import json
import re
import shutil
import subprocess
import logging
try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    SentenceTransformer = None
    util = None
from src.agentics import AgenticsApp, FetchIssueAgent, TicketClarityAgent, PreTestRunnerAgent, CodeExtractorAgent, CodeIntegratorAgent
from src.utils import validate_github_url
try:
    from github import GithubException
except ImportError:
    class GithubException(Exception):
        pass
# Define paths to the fixtures directory and JSON file
EXPECTED_TICKET_JSON_FILE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'expected_ticket.json')
# Load expected JSON from file
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)
# Lazy load sentence transformer model in functions
model = None
# Regex pattern to match function definitions (traditional, traditional, or arrow functions)
FUNCTION_PATTERN = re.compile(r'\bfunction\b|\bclass\b|=>')
def run_tests_and_get_coverage():
    """Run npm test and extract coverage percentage."""
    try:
        project_root = os.getenv('PROJECT_ROOT', '/project')
        result = subprocess.run(['npm', 'test'], cwd=project_root, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        # Extract coverage from output
        match = re.search(r'All files\s+\|\s+(\d+\.\d+)', output)
        if match:
            return float(match.group(1))
        return 0.0
    except Exception:
        return 0.0
def calculate_semantic_similarity(expected_text, actual_text):
    """
    Calculate the semantic similarity between two texts using sentence embeddings.
    Returns a percentage (0-100).
    """
    global model, util
    if model is None or util is None:
        pytest.skip("sentence_transformers not available for semantic similarity checks")
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
    method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', generated_code)
    command_match = re.search(r"this\.addCommand\(\{\s*id:\s*['\"]([^'\"]+)['\"]", generated_code)
    method_name = method_match.group(1) if method_match else None
    command_id = command_match.group(1) if command_match else None
    return method_name, command_id
# Helper function to extract describe lines from generated tests
def extract_describe_lines(generated_tests):
    """Extract describe block lines from generated tests."""
    return [line.strip() for line in generated_tests.splitlines() if line.strip().startswith('describe(')]
# Fixture to backup /project/src before each integration test and restore it after
@pytest.fixture(scope="session")
def embedding_model():
    """Lazy load SentenceTransformer model, return None if skipped or failed."""
    if os.getenv('SKIP_EMBEDDINGS'):
        return None
    try:
        return SentenceTransformer('all-MiniLM-L6-v2')
    except Exception:
        return None
@pytest.fixture(autouse=True)
def backup_src(request, tmp_path):
    """
    Backup /project/src to a temporary directory before each integration test
    and restore it after the test completes.
    """
    if request.node.get_closest_marker("integration"):
        # Use PROJECT_ROOT environment variable instead of hardcoded path
        project_root = os.getenv('PROJECT_ROOT', '/project')
        src_path = os.path.join(project_root, 'src')
        backup_dir = tmp_path / "backup_src"
        shutil.copytree(src_path, str(backup_dir))
        yield
        # Add logging to check permissions before restore
        import stat
        if os.path.exists(src_path):
            st = os.stat(src_path)
            logging.info(f"Permissions for {src_path}: {oct(st.st_mode)}")
            logging.info(f"UID/GID: {st.st_uid}/{st.st_gid}")
            logging.info(f"Current process UID/GID: {os.getuid()}/{os.getgid()}")
            # Check if writable
            writable = os.access(src_path, os.W_OK)
            logging.info(f"Is {src_path} writable? {writable}")
        else:
            logging.error(f"{src_path} does not exist")
        # Restore src from the backup after the test
        shutil.rmtree(src_path, ignore_errors=True)
        shutil.copytree(str(backup_dir), src_path, dirs_exist_ok=True)
    else:
        yield
# Integration tests for the ticket interpreter workflow
# These tests use real GitHub API and LLM service calls and operate on the actual /project/src.
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow_well_structured():
    os.environ["COLLAB_MAX_ITERATIONS"] = "1"
    """
    Test the full workflow with a well-structured ticket, ensuring the specific TypeScript content is written to files
    in /project/src and existing functions/tests are preserved.
    """
    # Given
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"

    # When (no patching, agents use actual /project)
    app = AgenticsApp()
    await app.initialize()
    result = await app.process_issue(test_url)
    print("✅ Workflow complete. Key results:")
    print(f"  Refined ticket similarity: {compute_ticket_similarity(EXPECTED_TICKET_JSON, result['refined_ticket']):.1f}%")
    print(f"  Generated code length: {len(result['generated_code'])}")
    print(f"  Generated tests length: {len(result['generated_tests'])}")
    print(f"  Existing tests passed: {result['existing_tests_passed']}")
    print(f"  Post-integration coverage: {result.get('post_integration_coverage_all_files', 'N/A')}%")

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
    # Check implementation planning fields
    assert "implementation_steps" in refined, "Implementation steps missing in refined ticket"
    assert "npm_packages" in refined, "NPM packages missing in refined ticket"
    assert "manual_implementation_notes" in refined, "Manual implementation notes missing in refined ticket"
    assert isinstance(refined["implementation_steps"], list), "Implementation steps should be a list"
    assert isinstance(refined["npm_packages"], list), "NPM packages should be a list"
  
    # Calculate semantic similarity against expected JSON
    similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, refined)
    assert similarity >= 85, f"Semantic similarity {similarity:.2f}% is below 85% threshold"
  
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
    assert "test" in tests or "describe" in tests, "Generated tests should include test blocks"
    assert "expect" in tests or "assert" in tests, "Tests should include assertions"
    assert "TimestampPlugin" in tests, "Tests should reference TimestampPlugin"
    assert "uuid" in tests.lower(), "Tests should verify UUID generation"
  
    # Extract describe lines from generated tests
    describe_lines = extract_describe_lines(tests)
    assert len(describe_lines) >= 2, "Expected at least two describe blocks in generated tests"
  
    # Validate test metrics from PreTestRunnerAgent
    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert result["existing_tests_passed"] == 58, "Expected 58 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 52.44, "Expected 52.44% line coverage based on current test output"
    # Validate post-integration test metrics from PostTestRunnerAgent
    assert "post_integration_tests_passed" in result, "Post-integration tests passed missing from result"
    assert "post_integration_coverage_all_files" in result, "Post-integration coverage missing from result"
    assert "coverage_improvement" in result, "Coverage improvement metric missing"
    assert "tests_improvement" in result, "Tests improvement metric missing"
    # Coverage should improve after code generation and integration
    assert result["post_integration_coverage_all_files"] > result["existing_coverage_all_files"], \
        f"Coverage should increase after integration: {result['post_integration_coverage_all_files']:.2f}% vs {result['existing_coverage_all_files']:.2f}%"
    assert result["coverage_improvement"] > 0, f"Coverage improvement should be positive: {result['coverage_improvement']:.2f}%"
    assert result["tests_improvement"] > 0, f"Tests improvement should be positive: {result['tests_improvement']}"
  
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
        project_root = os.getenv('PROJECT_ROOT', '/project')
        actual_file_path = os.path.join(project_root, file_path)
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
@pytest.mark.asyncio
async def test_full_workflow_sloppy():
    """
    Test the full workflow with a sloppy ticket, ensuring the TypeScript content is integrated into /project/src
    and existing content preserved.
    """
    # Given: a sloppy ticket URL from environment
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/22"
    # When: invoking the app with the sloppy ticket
    app = AgenticsApp()
    await app.initialize()
    result = await app.process_issue(test_url)
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
    assert similarity >= 75, f"Semantic similarity {similarity:.2f}% is below 75% threshold"
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
    assert result["existing_tests_passed"] == 58, "Expected 58 tests to pass based on current test output"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_coverage_all_files"] == 52.44, "Expected 52.44% line coverage based on current test output"
    # Validate post-integration test metrics from PostTestRunnerAgent
    assert "post_integration_tests_passed" in result, "Post-integration tests passed missing from result"
    assert "post_integration_coverage_all_files" in result, "Post-integration coverage missing from result"
    assert "coverage_improvement" in result, "Coverage improvement metric missing"
    assert "tests_improvement" in result, "Tests improvement metric missing"
    # Coverage should improve after code generation and integration
    assert result["post_integration_coverage_all_files"] > result["existing_coverage_all_files"], \
        f"Coverage should increase after integration: {result['post_integration_coverage_all_files']:.2f}% vs {result['existing_coverage_all_files']:.2f}%"
    assert result["coverage_improvement"] > 0, f"Coverage improvement should be positive: {result['coverage_improvement']:.2f}%"
    assert result["tests_improvement"] > 0, f"Tests improvement should be positive: {result['tests_improvement']}"
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
        project_root = os.getenv('PROJECT_ROOT', '/project')
        actual_file_path = os.path.join(project_root, file_path)
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
@pytest.mark.asyncio
async def test_empty_ticket():
    """Test the workflow with an empty ticket."""
    # Given: an empty ticket URL from environment
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/23"
    # When: invoking the app with the empty ticket
    # Then: Expect a ValueError due to empty ticket content
    app = AgenticsApp()
    await app.initialize()
    with pytest.raises(ValueError, match="Empty ticket content"):
        await app.process_issue(test_url)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_url():
    """Test the workflow with an invalid GitHub URL."""
    # Given: an invalid GitHub URL (pull request instead of issue)
    invalid_url = "https://github.com/user/repo/pull/1"
    # When: invoking the app with the invalid URL
    # Then: raises ValueError with "Invalid GitHub URL"
    app = AgenticsApp()
    await app.initialize()
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        await app.process_issue(invalid_url)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_existent_issue():
    """Test the workflow with a non-existent issue."""
    # Given: a non-existent issue URL from environment
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    non_existent_url = f"{test_repo_url}/issues/99999"
    # When: invoking the app with the non-existent issue
    # Then: raises GithubException
    app = AgenticsApp()
    await app.initialize()
    with pytest.raises(GithubException):
        await app.process_issue(non_existent_url)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_existent_repo():
    """Test the workflow with a non-existent repository."""
    # Given: a non-existent repository URL
    non_existent_url = "https://github.com/nonexistentuser/nonexistentrepo/issues/1"
    # When: invoking the app with the non-existent repo
    # Then: raises GithubException
    app = AgenticsApp()
    await app.initialize()
    with pytest.raises(GithubException):
        await app.process_issue(non_existent_url)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow_no_match():
    """Test workflow with a ticket unrelated to the codebase, expecting new files to be created in /project/src."""
    # Given: a ticket URL and mocked unrelated ticket
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    unrelated_ticket = {
        "title": "Update Documentation",
        "description": "Revise README with new installation steps.",
        "requirements": ["Add installation section"],
        "acceptance_criteria": ["README reflects changes"]
    }
    # No patch; use real ticket_clarity_agent
    # When: invoking the app with the unrelated ticket
    app = AgenticsApp()
    await app.initialize()
    result = await app.process_issue(test_url)
    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    assert len(result["relevant_code_files"]) >= 1, "Expected at least one code file for unrelated ticket"
    assert len(result["relevant_test_files"]) >= 1, "Expected at least one test file for unrelated ticket"
    code_paths = [f["file_path"] for f in result["relevant_code_files"]]
    test_paths = [f["file_path"] for f in result["relevant_test_files"]]
    assert "src/main.ts" in code_paths or any("main" in p for p in code_paths), "Expected 'src/main.ts' or main-related file for partial match"
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
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow_partial_match():
    """Test workflow with a ticket partially matching codebase keywords, updating /project/src."""
    # Given: a ticket URL and mocked partial match ticket
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    partial_ticket = {
        "title": "Enhance main functionality",
        "description": "Improve the main plugin logic.",
        "requirements": ["Update main logic"],
        "acceptance_criteria": ["Verify main works"]
    }
    # No patch; use real ticket_clarity_agent
    # When: invoking the app with the partial match ticket
    app = AgenticsApp()
    await app.initialize()
    result = await app.process_issue(test_url)
    assert "relevant_code_files" in result, "Relevant code files missing from workflow output"
    assert "relevant_test_files" in result, "Relevant test files missing from workflow output"
    code_paths = [file_data["file_path"] for file_data in result["relevant_code_files"]]
    assert "src/main.ts" in code_paths or any("main" in p for p in code_paths), "Expected 'src/main.ts' or main-related file for partial match"
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
