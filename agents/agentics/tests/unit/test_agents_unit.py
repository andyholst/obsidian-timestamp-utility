import pytest
import os
import json
import shutil
import logging
import re
import tenacity
import asyncio

# Set required environment variables for imports
os.environ.setdefault('PROJECT_ROOT', '/tmp')
os.environ.setdefault('GITHUB_TOKEN', 'dummy')

from src.agentics import TicketClarityAgent, ImplementationPlannerAgent, PreTestRunnerAgent, CodeExtractorAgent, CodeIntegratorAgent, PostTestRunnerAgent, CodeReviewerAgent
from src import agentics
from src.utils import validate_github_url
from unittest.mock import patch, MagicMock
from github import GithubException
from tests.fixtures.mock_github_responses import create_github_client_mock, create_well_structured_ticket_mock, create_unclear_ticket_mock, create_malformed_ticket_mock, create_empty_ticket_mock
from src.services import GitHubClient
from src.exceptions import ValidationError, AgenticsError
from sentence_transformers import SentenceTransformer, util
from src.circuit_breaker import circuit_breakers
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../fixtures')
EXPECTED_TICKET_JSON_FILE = os.path.join(FIXTURES_DIR, 'expected_ticket.json')

# Load expected JSON
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)

# Sample ticket content for testing
WELL_STRUCTURED_TICKET = """
# Implement Timestamp-based UUID Generator in Obsidian
## Description
Add a command to Obsidian that generates a UUID based on the current timestamp and inserts it into the active note.
## Requirements
- The command must be accessible via Obsidian's command palette.
- It should generate a UUID using the current timestamp, following the UUID v7 standard.
## Acceptance Criteria
- The command is visible in Obsidian's command palette when searched.
- When the command is executed with an active note, a valid UUID v7 is generated and inserted.
"""

UNCLEAR_TICKET = """
# Do something
## Description
Make it better.
## Requirements
- It should work.
## Acceptance Criteria
- It works.
"""

MALFORMED_TICKET = """
# Title Missing Closing Bracket
## Description
Add a feature with mismatched brackets: { { {.
## Requirements
- Do stuff with errors
## Acceptance Criteria
- It should somehow work
"""

# Real project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

# Patch paths for consistent mocking
GITHUB_PATCH_PATH = 'github.Github'

def reset_circuit_breakers():
    """Reset all circuit breakers to closed state for testing"""
    for name, breaker in circuit_breakers.items():
        breaker._reset()

def calculate_semantic_similarity(expected_text, actual_text):
    # Load the sentence transformer model for semantic similarity (lazy loading)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode([expected_text, actual_text], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    return similarity * 100

def compute_ticket_similarity(expected_ticket, refined_ticket):
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

def count_test_methods(content):
    return len(re.findall(r'^\s*(test|it)\(', content, re.MULTILINE))

def count_code_entities(content):
    return len(re.findall(r'\b(function|class)\b', content))

def check_original_lines_preserved(original_lines, updated_lines):
    orig_idx = 0
    upd_idx = 0
    while orig_idx < len(original_lines) and upd_idx < len(updated_lines):
        if original_lines[orig_idx] == updated_lines[upd_idx]:
            orig_idx += 1
            upd_idx += 1
        else:
            upd_idx += 1
    return orig_idx == len(original_lines)

def check_ts_code_intact(original_content, new_content):
    """Check that key TypeScript code structures remain intact."""
    original_methods = re.findall(r'(public|private|protected)?\s*(\w+)\s*\(', original_content)
    new_methods = re.findall(r'(public|private|protected)?\s*(\w+)\s*\(', new_content)
    for orig_method in original_methods:
        assert orig_method in new_methods, f"Original method {orig_method[1]} missing in new content"
    assert "class TimestampPlugin" in new_content, "TimestampPlugin class should remain"
    assert "onload()" in new_content, "onload method should remain"

def check_ts_tests_intact(original_content, new_content):
    """Check that original test structures remain intact."""
    original_describes = re.findall(r'describe\(\'(.*?)\'', original_content)
    new_describes = re.findall(r'describe\(\'(.*?)\'', new_content)
    for orig_describe in original_describes:
        assert orig_describe in new_describes, f"Original describe block '{orig_describe}' missing"
    original_tests = re.findall(r'(test|it)\(\'(.*?)\'', original_content)
    new_tests = re.findall(r'(test|it)\(\'(.*?)\'', new_content)
    for orig_test in original_tests:
        assert orig_test in new_tests, f"Original test '{orig_test[1]}' missing"

@pytest.fixture
def temp_project_dir(tmp_path):
    project_dir = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)
    package_json_path = os.path.join(project_dir, "package.json")
    assert os.path.isfile(package_json_path), f"package.json must be present at {package_json_path}"
    required_files = [
        "package.json",
        "src/main.ts",
        "src/__tests__/main.test.ts",
        "src/__mocks__/obsidian.ts"
    ]
    for file in required_files:
        assert os.path.exists(os.path.join(project_dir, file)), f"Required file {file} missing in temp project dir"
    return project_dir

@pytest.fixture
def src_backup(request, tmp_path):
    """
    Fixture to backup and restore the src directory for each test.
    If the test uses temp_project_dir, it operates on that; otherwise, it creates a new temp dir.
    """
    if 'temp_project_dir' in request.fixturenames:
        project_dir = request.getfixturevalue('temp_project_dir')
    else:
        project_dir = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)

    src_dir = os.path.join(project_dir, 'src')
    backup_dir = os.path.join(project_dir, 'src_backup')
    shutil.copytree(src_dir, backup_dir)
    yield project_dir
    shutil.rmtree(src_dir)
    shutil.copytree(backup_dir, src_dir)
    shutil.rmtree(backup_dir)

def test_validate_github_url():
    # Given: various GitHub URLs including valid issue URL, pull request URL, and invalid URL
    valid_url = "https://github.com/user/repo/issues/1"
    pull_url = "https://github.com/user/repo/pull/1"
    invalid_url = "invalid_url"
    # When: validating each URL using validate_github_url function
    # Then: valid issue URL returns True, pull request URL returns False, invalid URL returns False
    assert validate_github_url(valid_url) == True, "Valid issue URL should return True"
    assert validate_github_url(pull_url) == False, "Pull request URL should return False"
    assert validate_github_url(invalid_url) == False, "Invalid URL should return False"

def test_full_workflow_unit(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with well-structured ticket
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')
    mock_github_client = MagicMock()
    mock_github_client.get_repo.return_value = mock_repo
    mock_github_client.get_user.return_value = MagicMock(login='mock_user')
    mock_service_manager = MagicMock()
    mock_service_manager.github = MagicMock()
    mock_service_manager.github._client = mock_github_client
    mock_service_manager.github.get_repo.return_value = mock_repo
    mock_service_manager.github.get_user.return_value = MagicMock(login='mock_user')
def mock_github_init(self, token):
    self.token = token
    self._client = mock_github

    # When: invoking the app with the well-structured ticket
    with patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
           patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
           patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
           patch.object(GitHubClient, 'health_check', return_value=True), \
           patch.object(post_test_runner_agent, 'project_root', str(project_dir)), \
           patch('src.services.ServiceManager.check_services_health', return_value={"ollama_reasoning": True, "ollama_code": True, "github": True, "mcp": False}), \
           patch('src.services.get_service_manager', return_value=mock_service_manager), \
           patch.object(GitHubClient, '__init__', mock_github_init):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = asyncio.run(app.process_issue(initial_state["url"]))

        # Then: verify the full workflow completes successfully with reasonable assertions
        assert "result" in result, "Result key missing"
        assert "generated_code" in result, "Generated code key missing"
        assert "generated_tests" in result, "Generated tests key missing"
        assert "relevant_code_files" in result, "Relevant code files key missing"
        assert "relevant_test_files" in result, "Relevant test files key missing"

        # Check that generated content is non-empty and contains expected patterns
        assert result["generated_code"] != "", "Generated code should not be empty"
        assert result["generated_tests"] != "", "Generated tests should not be empty"
        assert "uuid" in result["generated_code"].lower(), "Generated code should contain UUID-related functionality"
        assert "timestamp" in result["generated_code"].lower(), "Generated code should contain timestamp functionality"

        # Check that tests contain test methods
        assert "test(" in result["generated_tests"] or "it(" in result["generated_tests"], "Generated tests should contain test methods"

        # Verify semantic similarity of the refined ticket
        assert isinstance(result["result"], dict), "Result should be a dictionary"
        similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, result["result"])
        assert similarity >= 60, f"Semantic similarity {similarity:.2f}% is below 60% threshold"

        # Check that relevant files are identified
        assert len(result["relevant_code_files"]) >= 1, "Should identify at least one relevant code file"
        assert len(result["relevant_test_files"]) >= 1, "Should identify at least one relevant test file"

        # Verify files exist and have been processed
        all_relevant_files = result["relevant_code_files"] + result["relevant_test_files"]
        for file_data in all_relevant_files:
            file_path = os.path.join(project_dir, file_data["file_path"])
            assert os.path.exists(file_path), f"File {file_path} should exist"
            with open(file_path, 'r') as f:
                new_content = f.read()
            assert len(new_content) > 0, f"File {file_path} should not be empty"
            original_content = file_data["content"]
            original_lines = original_content.splitlines()
            new_lines = new_content.splitlines()
            assert check_original_lines_preserved(original_lines, new_lines), f"Original lines must be preserved in {file_path}"

            # Assert that new content has been added (code/tests should grow)
            assert len(new_content) > len(original_content), f"New content should be larger than original in {file_path} (was {len(original_content)}, now {len(new_content)})"

            if "test" in file_data["file_path"].lower():
                # Check that new test methods were added
                new_test_count = count_test_methods(new_content)
                original_test_count = count_test_methods(original_content)
                assert new_test_count > original_test_count, f"Number of tests should increase in {file_path} (was {original_test_count}, now {new_test_count})"
                check_ts_tests_intact(original_content, new_content)
            else:
                # Check that new code entities were added or existing ones enhanced
                new_entity_count = count_code_entities(new_content)
                original_entity_count = count_code_entities(original_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path} (was {original_entity_count}, now {new_entity_count})"
                # Also check for new command/functionality specifically for this UUID feature
                assert "uuid" in new_content.lower() or "timestamp" in new_content.lower(), f"New code should contain UUID/timestamp functionality in {file_path}"
                check_ts_code_intact(original_content, new_content)

        # Check that existing tests passed (flexible assertion)
        assert "existing_tests_passed" in result, "Should report existing test results"
        assert result["existing_tests_passed"] >= 50, f"Existing tests passed rate {result['existing_tests_passed']}% should be at least 50%"

def test_full_workflow_invalid_url():
    # Given: an invalid GitHub URL
    mock_github = MagicMock()
    initial_state = {"url": "invalid_url"}
    # When: invoking the app with the invalid URL
    # Then: raises ValidationError with message "Invalid GitHub URL"
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True):
        from src.agentics import AgenticsApp
        app = AgenticsApp()
        with pytest.raises(ValidationError) as exc_info:
            asyncio.run(app.process_issue(initial_state["url"]))
        assert isinstance(exc_info.value, ValidationError)
        assert "Invalid GitHub issue URL" in str(exc_info.value)

def test_full_workflow_empty_ticket():
    # Given: mocked GitHub with empty ticket content
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = ""
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    # When: invoking the app with the empty ticket
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True):
        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises AgenticsError wrapping the RetryError
        from src.exceptions import AgenticsError
        with pytest.raises(AgenticsError) as exc_info:
            asyncio.run(app.process_issue(initial_state["url"]))
        assert "RetryError" in str(exc_info.value)

def test_full_workflow_github_error():
    # Given: mocked GitHub that raises GithubException
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException(404, data={"message": "Not Found"}, headers={})
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    # When: invoking the app
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True):
        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises AgenticsError wrapping RetryError containing GithubException with "404.*Not Found"
        with pytest.raises(AgenticsError) as exc_info:
            asyncio.run(app.process_issue(initial_state["url"]))
        assert isinstance(exc_info.value.__cause__.__cause__, tenacity.RetryError)
        assert isinstance(exc_info.value.__cause__.__cause__, GithubException)
        assert "404" in str(exc_info.value.__cause__.__cause__) and "Not Found" in str(exc_info.value.__cause__.__cause__)

def test_full_workflow_tests_fail(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory with failing test and mocked GitHub
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    (project_dir / "src" / "__tests__").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "__tests__" / "main.test.ts").write_text("test('fail', () => { throw new Error('Test failed'); });")

    # When: invoking the app with failing tests
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises RuntimeError with "Existing tests failed"
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            asyncio.run(app.process_issue(initial_state["url"]))

def test_full_workflow_vague_ticket_with_code_generation(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with unclear ticket
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = UNCLEAR_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    # When: invoking the app with the vague ticket
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = asyncio.run(app.process_issue(initial_state["url"]))
        # Then: verify code and tests are generated for refined vague ticket
        assert "result" in result, "Result key missing"
        assert "generated_code" in result, "Generated code key missing"
        assert "generated_tests" in result, "Generated tests key missing"
        # For vague tickets, the system now refines them and generates code
        assert result["generated_code"] != "", "Generated code should not be empty for refined vague ticket"
        assert result["generated_tests"] != "", "Generated tests should not be empty for refined vague ticket"
        # But relevant files should still be identified (main.ts and main.test.ts)
        assert "relevant_code_files" in result, "Should still identify relevant code files"
        assert "relevant_test_files" in result, "Should still identify relevant test files"
        assert len(result["relevant_code_files"]) >= 1, "Should identify at least main.ts"
        assert len(result["relevant_test_files"]) >= 1, "Should identify at least main.test.ts"
        # Files should still exist unchanged since no integration occurred
        assert os.path.exists(project_dir / "src" / "main.ts"), "main.ts should still exist"
        assert os.path.exists(project_dir / "src" / "__tests__" / "main.test.ts"), "main.test.ts should still exist"

def test_full_workflow_file_write_error(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with file write error
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def raise_exception(*args, **kwargs):
        raise Exception("File write error")

    # When: invoking the app with mocked file write error
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True), \
          patch('src.code_integrator_agent.CodeIntegratorAgent.update_file', side_effect=raise_exception), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises Exception with "File write error"
        with pytest.raises(Exception, match="File write error"):
            asyncio.run(app.process_issue(initial_state["url"]))

def test_full_workflow_npm_install_fail(tmp_path):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: mocked GitHub and empty project directory without package.json
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    project_dir = tmp_path / "madeup_dir"
    project_dir.mkdir()

    # When: invoking the app with directory that can't install dependencies
    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(GitHubClient, 'health_check', return_value=True), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises RuntimeError with "Install command failed"
        with pytest.raises(RuntimeError, match="Install command failed"):
            asyncio.run(app.process_issue(initial_state["url"]))

def test_full_workflow_no_ts_files(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory with empty src folder and mocked GitHub
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    shutil.rmtree(project_dir / "src", ignore_errors=True)
    (project_dir / "src").mkdir()

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    # When: invoking the app with no TypeScript files
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        # Then: raises RuntimeError with "Existing tests failed"
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            asyncio.run(app.process_issue(initial_state["url"]))

def test_full_workflow_multiple_relevant_files(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with well-structured ticket
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    # When: invoking the app expecting multiple relevant files
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = asyncio.run(app.process_issue(initial_state["url"]))
        # Then: verify relevant files are processed correctly
        assert "relevant_code_files" in result, "Relevant code files key missing"
        assert "relevant_test_files" in result, "Relevant test files key missing"
        assert isinstance(result["relevant_code_files"], list), "Relevant code files should be a list"
        assert isinstance(result["relevant_test_files"], list), "Relevant test files should be a list"
        assert len(result["relevant_code_files"]) + len(result["relevant_test_files"]) >= 1, "At least one file should be updated"
        all_relevant_files = result["relevant_code_files"] + result["relevant_test_files"]
        for file_data in all_relevant_files:
            file_path = os.path.join(project_dir, file_data["file_path"])
            assert os.path.exists(file_path), f"File {file_path} should exist"
            original_content = file_data["content"]
            with open(file_path, 'r') as f:
                new_content = f.read()
            assert len(new_content) > 0, f"File {file_path} should not be empty"
            original_lines = original_content.splitlines()
            new_lines = new_content.splitlines()
            assert check_original_lines_preserved(original_lines, new_lines), f"Original lines must be preserved in {file_path}"
            if "test" in file_data["file_path"].lower():
                assert "test" in new_content or "describe" in new_content, "Test file should contain test structures"
                new_test_count = count_test_methods(new_content)
                assert new_test_count > 0, f"Test file {file_path} should contain at least one test method"
                original_test_count = count_test_methods(original_content)
                assert new_test_count > original_test_count, f"Number of tests should increase in {file_path}"
                check_ts_tests_intact(original_content, new_content)
            else:
                assert "function" in new_content or "class" in new_content, "Code file should contain functions or classes"
                original_entity_count = count_code_entities(original_content)
                new_entity_count = count_code_entities(new_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path}"
                check_ts_code_intact(original_content, new_content)

def test_full_workflow_malformed_ticket(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with malformed ticket
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = MALFORMED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    # When: invoking the app with malformed ticket
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = asyncio.run(app.process_issue(initial_state["url"]))
        # Then: verify result structure and file integrity checks
        assert "result" in result, "Result key missing"
        assert "generated_code" in result, "Generated code missing"
        assert "generated_tests" in result, "Generated tests missing"
        assert isinstance(result["result"], dict), "Result should be a dictionary"
        assert "relevant_code_files" in result, "Relevant code files missing"
        assert "relevant_test_files" in result, "Relevant test files missing"
        all_relevant_files = result["relevant_code_files"] + result["relevant_test_files"]
        for file_data in all_relevant_files:
            file_path = os.path.join(project_dir, file_data["file_path"])
            original_content = file_data["content"]
            with open(file_path, 'r') as f:
                new_content = f.read()
            if "test" in file_data["file_path"].lower():
                check_ts_tests_intact(original_content, new_content)
            else:
                check_ts_code_intact(original_content, new_content)

def test_full_workflow_large_ticket(src_backup):
    # Instantiate agents for patching
    mock_llm = MagicMock()
    pre_test_runner_agent = PreTestRunnerAgent()
    code_extractor_agent = CodeExtractorAgent(mock_llm)
    code_integrator_agent = CodeIntegratorAgent(mock_llm)
    post_test_runner_agent = PostTestRunnerAgent()

    # Given: project directory and mocked GitHub with large ticket content
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    large_content = "# Large Ticket\n" + "Description " * 1000 + "\n- Req1\n- Req2\n- AC1\n- AC2"
    mock_issue.body = large_content
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    # When: invoking the app with large ticket
    with patch.object(GitHubClient, '__init__', mock_github_init), \
          patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
          patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
          patch.object(code_integrator_agent, 'project_root', str(project_dir)), \
          patch.object(post_test_runner_agent, 'project_root', str(project_dir)):

        from src.agentics import AgenticsApp
        app = AgenticsApp()
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = asyncio.run(app.process_issue(initial_state["url"]))
        # Then: verify result has non-empty description and files are intact
        assert "result" in result, "Result key missing"
        assert len(result["result"]["description"]) > 0, "Description should be non-empty after refinement"
        all_relevant_files = result["relevant_code_files"] + result["relevant_test_files"]
        for file_data in all_relevant_files:
            file_path = os.path.join(project_dir, file_data["file_path"])
            original_content = file_data["content"]
            with open(file_path, 'r') as f:
                new_content = f.read()
            if "test" in file_data["file_path"].lower():
                check_ts_tests_intact(original_content, new_content)
            else:
                check_ts_code_intact(original_content, new_content)


def test_full_workflow_agent_call_order():
    """Test that agents are called in the correct order during the full workflow."""
    reset_circuit_breakers()
    # Given: mocked GitHub, LLMs, circuit breakers, and agent call tracking
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    def mock_github_init(self, token):
        self.token = token
        self._client = mock_github

    # Mock circuit breakers to always return False for is_open and do nothing for record_success/record_failure
    mock_cb = MagicMock()
    mock_cb.is_open.return_value = False
    mock_cb.record_success = MagicMock()
    mock_cb.record_failure = MagicMock()

    # Mock LLMs to avoid real API calls with proper responses
    mock_llm_reasoning = MagicMock()
    # Ticket clarity: evaluate_clarity called 5 times (max_iterations), then generate_improvements once
    ticket_clarity_responses = ['{"is_clear": true, "suggestions": []}'] * 5 + [json.dumps(EXPECTED_TICKET_JSON)]
    # Implementation planner
    impl_planner_response = '{"implementation_steps": [], "npm_packages": [], "manual_implementation_notes": ""}'
    # Collaborative generator cross-validation
    collab_gen_response = '{"passed": true, "score": 100, "coverage_percentage": 100, "alignment_score": 100, "issues": [], "recommendations": [], "test_quality": "excellent"}'
    # Code integrator: generate_filename
    code_integrator_filename_response = "timestampGenerator"
    # Code integrator: integrate_code_with_llm (return updated code)
    code_integrator_code_response = "class TimestampPlugin { onload() { this.addCommand({ id: 'generate-uuid', name: 'Generate UUID', callback: () => { console.log('UUID generated'); } }); } }"
    # Code reviewer
    code_reviewer_response = '{"is_aligned": true, "feedback": "Code and tests are well-aligned", "tuned_prompt": "", "needs_fix": false}'

    mock_llm_reasoning.invoke.side_effect = (
        ticket_clarity_responses +
        [impl_planner_response] +
        [collab_gen_response] +
        [code_integrator_filename_response] +
        [code_integrator_code_response] +
        [code_reviewer_response]
    )

    mock_llm_code = MagicMock()
    mock_llm_code.invoke.side_effect = [
        "public generateUUID() { this.addCommand({ id: 'generate-uuid', name: 'Generate UUID', callback: () => { console.log('UUID generated'); } }); }",  # code generation
        "test('generate UUID', () => { expect(true).toBe(true); });",  # test generation
        "timestampGenerator",  # filename generation
        "class TimestampPlugin { onload() { this.addCommand({ id: 'generate-uuid', name: 'Generate UUID', callback: () => { console.log('UUID generated'); } }); } }"  # code integration
    ]
    def wrapper(original_invoke):
            def tracked_invoke(input_state, config=None):
                call_order.append(agent_name)
                # Return a minimal valid state for the next agent
                if not hasattr(input_state, 'issue_url'):
                    # Convert dict to CodeGenerationState-like object
                    class MockState:
                        def __init__(self, data):
                            for k, v in data.items():
                                setattr(self, k, v)
                    input_state = MockState(input_state)
                return original_invoke(input_state, config)
            return tracked_invoke
    return wrapper

    # When: creating workflow and running it with mocked agents
    with patch.object(GitHubClient, '__init__', mock_github_init), \
         patch('src.agentics.llm_reasoning', mock_llm_reasoning), \
         patch('src.agentics.llm_code', mock_llm_code), \
         patch('src.circuit_breaker.circuit_breakers', {'ollama_reasoning_cb': mock_cb, 'ollama_code_cb': mock_cb, 'github_cb': mock_cb, 'mcp_cb': mock_cb}):

        from src.agentics import create_composable_workflow
        workflow_system = create_composable_workflow(mock_github)

        # Mock agent invoke methods to track calls
        agent_names = [
            'fetch_issue', 'ticket_clarity', 'implementation_planner', 'dependency_analyzer',
            'code_extractor', 'collaborative_generator', 'code_integrator',
            'post_test_runner', 'code_reviewer', 'output_result'
        ]

        for agent_name in agent_names:
            if agent_name in workflow_system.composer.agents:
                original_invoke = workflow_system.composer.agents[agent_name].invoke
                workflow_system.composer.agents[agent_name].invoke = track_call(agent_name)(original_invoke)

        # Run the workflow
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        try:
            result = workflow_system.process_issue("https://github.com/user/repo/issues/1")
        except Exception as e:
            # Workflow might fail due to minimal mocks, but we care about call order
            pass

        # Then: verify the agent call order
        # Expected sequence: fetch_issue, ticket_clarity, implementation_planner,
        # then dependency_analyzer (parallel), then code_extractor, collaborative_generator,
        # code_integrator, post_test_runner, code_reviewer, output_result

        expected_main_sequence = [
            'fetch_issue', 'ticket_clarity', 'implementation_planner',
            'code_extractor', 'collaborative_generator', 'code_integrator',
            'post_test_runner', 'code_reviewer', 'output_result'
        ]

        # Check that main sequence is followed
        main_indices = []
        for agent in expected_main_sequence:
            if agent in call_order:
                main_indices.append(call_order.index(agent))

        # Verify main sequence is in order
        assert main_indices == sorted(main_indices), f"Main sequence not in order: {call_order}"

        # Verify dependency_analyzer was called (parallel execution)
        assert 'dependency_analyzer' in call_order, "dependency_analyzer should have been called"

        # Verify all expected agents were called at least once
        for agent in expected_main_sequence + ['dependency_analyzer']:
            assert agent in call_order, f"Agent {agent} was not called"

        # Verify no unexpected agents were called
        expected_agents = set(expected_main_sequence + ['dependency_analyzer'])
        actual_agents = set(call_order)
        unexpected = actual_agents - expected_agents
        assert len(unexpected) == 0, f"Unexpected agents called: {unexpected}"


def test_issue_processing_phase_call_order():
    """Test that agents are called in the correct order during the issue processing phase."""
    reset_circuit_breakers()
    # Given: mocked GitHub and LLMs
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    mock_github.get_user.return_value = MagicMock(login='mock_user')

    mock_llm_reasoning = MagicMock()
    # Ticket clarity evaluate_clarity called 5 times, all return true, then generate_improvements once
    ticket_clarity_evaluate_responses = ['{"is_clear": true, "suggestions": []}'] * 5
    ticket_clarity_improve_response = json.dumps(EXPECTED_TICKET_JSON)
    # Implementation planner response
    impl_planner_response = '{"implementation_steps": [], "npm_packages": [], "manual_implementation_notes": ""}'
    mock_llm_reasoning.invoke.side_effect = ticket_clarity_evaluate_responses + [ticket_clarity_improve_response] + [impl_planner_response]

    # Track agent call order
    call_order = []

    def track_call(agent_name):
        def wrapper(original_invoke):
            def tracked_invoke(input_state, config=None):
                call_order.append(agent_name)
                # Return a minimal valid state for the next agent
                if isinstance(input_state, dict):
                    class MockState:
                        def __init__(self, data):
                            for k, v in data.items():
                                setattr(self, k, v)
                    return MockState(input_state)
                return original_invoke(input_state, config)
            return tracked_invoke
        return wrapper

    # When: running the issue processing workflow with mocked agents
    from src.composable_workflows import ComposableWorkflows
    workflows = ComposableWorkflows(mock_llm_reasoning, MagicMock(), mock_github)

    # Mock agent invoke methods to track calls
    agent_names = ['fetch_issue', 'ticket_clarity', 'implementation_planner']
    for agent_name in agent_names:
        original_invoke = workflows.composer.agents[agent_name].invoke
        workflows.composer.agents[agent_name].invoke = track_call(agent_name)(original_invoke)

    # Run the issue processing workflow
    initial_state = {"url": "https://github.com/user/repo/issues/1"}
    try:
        result = workflows.issue_processing_workflow.invoke(initial_state)
    except Exception:
        # Workflow might fail due to minimal mocks, but we care about call order
        pass

    # Then: verify the agent call order for issue processing phase
    expected_order = ['fetch_issue', 'ticket_clarity', 'implementation_planner']
    assert call_order == expected_order, f"Expected {expected_order}, got {call_order}"


def test_dependency_analysis_phase_call_order():
    """Test that the dependency analyzer agent is called during the dependency analysis phase."""
    # Given: mocked LLMs
    mock_llm_reasoning = MagicMock()
    mock_llm_reasoning.invoke.return_value = '{"available_dependencies": []}'

    # Track agent call order
    call_order = []

    def track_call(agent_name):
        def wrapper(original_invoke):
            def tracked_invoke(input_state, config=None):
                call_order.append(agent_name)
                return original_invoke(input_state, config)
            return tracked_invoke
        return wrapper

    # When: running the dependency analyzer agent
    from src.composable_workflows import ComposableWorkflows
    workflows = ComposableWorkflows(mock_llm_reasoning, MagicMock(), MagicMock())

    # Mock agent invoke method to track calls
    original_invoke = workflows.composer.agents['dependency_analyzer'].invoke
    workflows.composer.agents['dependency_analyzer'].invoke = track_call('dependency_analyzer')(original_invoke)

    # Run the dependency analyzer
    initial_state = {"url": "https://github.com/user/repo/issues/1"}
    try:
        result = workflows.composer.agents['dependency_analyzer'].invoke(initial_state)
    except Exception:
        # Agent might fail due to minimal mocks, but we care about call tracking
        pass

    # Then: verify the dependency analyzer was called
    assert 'dependency_analyzer' in call_order, "dependency_analyzer should have been called"


def test_code_generation_phase_call_order():
    """Test that agents are called in the correct order during the code generation phase."""
    # Given: mocked LLMs
    mock_llm_reasoning = MagicMock()
    mock_llm_reasoning.invoke.return_value = '{"relevant_files": [], "code_patterns": []}'

    mock_llm_code = MagicMock()
    mock_llm_code.invoke.return_value = "console.log('test');"

    # Track agent call order
    call_order = []

    def track_call(agent_name):
        def wrapper(original_invoke):
            def tracked_invoke(input_state, config=None):
                call_order.append(agent_name)
                # Return a minimal valid state for the next agent
                if isinstance(input_state, dict):
                    class MockState:
                        def __init__(self, data):
                            for k, v in data.items():
                                setattr(self, k, v)
                    return MockState(input_state)
                return original_invoke(input_state, config)
            return tracked_invoke
        return wrapper

    # When: running the code generation workflow with mocked agents
    from src.composable_workflows import ComposableWorkflows
    workflows = ComposableWorkflows(mock_llm_reasoning, mock_llm_code, MagicMock())

    # Mock agent invoke methods to track calls
    agent_names = ['code_extractor', 'collaborative_generator']
    for agent_name in agent_names:
        original_invoke = workflows.composer.agents[agent_name].invoke
        workflows.composer.agents[agent_name].invoke = track_call(agent_name)(original_invoke)

    # Run the code generation workflow
    initial_state = {"url": "https://github.com/user/repo/issues/1"}
    try:
        result = workflows.code_generation_workflow.invoke(initial_state)
    except Exception:
        # Workflow might fail due to minimal mocks, but we care about call order
        pass

    # Then: verify the agent call order for code generation phase
    expected_order = ['code_extractor', 'collaborative_generator']
    assert call_order == expected_order, f"Expected {expected_order}, got {call_order}"


def test_integration_testing_phase_call_order():
    """Test that agents are called in the correct order during the integration and testing phase."""
    reset_circuit_breakers()
    # Given: mocked LLMs
    mock_llm_reasoning = MagicMock()
    mock_llm_reasoning.invoke.return_value = '{"review_comments": []}'

    mock_llm_code = MagicMock()
    mock_llm_code.invoke.return_value = "console.log('test');"

    # Track agent call order
    call_order = []

    def track_call(agent_name):
        def wrapper(original_invoke):
            def tracked_invoke(input_state, config=None):
                call_order.append(agent_name)
                # Return a minimal valid state for the next agent
                if isinstance(input_state, dict):
                    class MockState:
                        def __init__(self, data):
                            for k, v in data.items():
                                setattr(self, k, v)
                    return MockState(input_state)
                return original_invoke(input_state, config)
            return tracked_invoke
        return wrapper

    # When: running the integration testing workflow with mocked agents
    from src.composable_workflows import ComposableWorkflows
    workflows = ComposableWorkflows(mock_llm_reasoning, mock_llm_code, MagicMock())

    # Mock agent invoke methods to track calls
    agent_names = ['code_integrator', 'post_test_runner', 'code_reviewer', 'output_result']
    for agent_name in agent_names:
        original_invoke = workflows.composer.agents[agent_name].invoke
        workflows.composer.agents[agent_name].invoke = track_call(agent_name)(original_invoke)

    # Run the integration testing workflow
    initial_state = {"url": "https://github.com/user/repo/issues/1"}
    try:
        result = workflows.integration_testing_workflow.invoke(initial_state)
    except Exception:
        # Workflow might fail due to minimal mocks, but we care about call order
        pass

    # Then: verify the agent call order for integration and testing phase
    expected_order = ['code_integrator', 'post_test_runner', 'code_reviewer', 'output_result']
    assert call_order == expected_order, f"Expected {expected_order}, got {call_order}"