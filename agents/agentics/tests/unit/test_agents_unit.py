import pytest
import json
import os
import shutil
import logging
import re
from src.agentics import app, fetch_issue_agent, ticket_clarity_agent, pre_test_runner_agent, code_extractor_agent, code_integrator_agent
from src.utils import validate_github_url
from unittest.mock import patch, MagicMock
from github import GithubException
from sentence_transformers import SentenceTransformer, util

# Define paths to fixtures
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

# Real project root
PROJECT_ROOT = '/project'

# Load the sentence transformer model for semantic similarity
model = SentenceTransformer('all-MiniLM-L6-v2')

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

def count_test_methods(content):
    """
    Count the number of test methods in the content using 'test(' or 'it(' patterns.
    """
    return len(re.findall(r'^\s*(test|it)\(', content, re.MULTILINE))

def count_code_entities(content):
    """
    Count the number of functions or classes in the content using 'function' or 'class' keywords.
    """
    return len(re.findall(r'\b(function|class)\b', content))

@pytest.fixture
def temp_project_dir(tmp_path):
    """Fixture to create a temporary project directory by copying the real project."""
    project_dir = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)
    return project_dir

def test_validate_github_url():
    """Test GitHub URL validation."""
    valid_url = "https://github.com/user/repo/issues/1"
    pull_url = "https://github.com/user/repo/pull/1"
    invalid_url = "invalid_url"
    
    assert validate_github_url(valid_url) == True, "Valid issue URL should return True"
    assert validate_github_url(pull_url) == False, "Pull request URL should return False"
    assert validate_github_url(invalid_url) == False, "Invalid URL should return False"

def test_full_workflow_unit(temp_project_dir):
    """Test the full workflow with a mocked GitHub client using a temporary directory and real LLM responses."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(temp_project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)

        # Basic result structure checks
        assert "result" in result, "Result key missing"
        assert "generated_code" in result, "Generated code missing"
        assert "generated_tests" in result, "Generated tests missing"
        assert "existing_tests_passed" in result, "Tests passed missing"
        assert "existing_coverage_all_files" in result, "Coverage missing"
        assert "relevant_files" in result, "Relevant files missing"
        assert isinstance(result["result"], dict), "Result should be a dictionary"
        
        # Semantic similarity check
        similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, result["result"])
        assert similarity >= 70, f"Semantic similarity {similarity:.2f}% is below 70% threshold"
        
        # Content checks for generated code and tests
        assert "UUID" in result["generated_code"], "Generated code should contain 'UUID'"
        assert "command palette" in result["generated_code"].lower(), "Generated code should reference command palette"
        assert "UUID" in result["generated_tests"], "Generated tests should test UUID functionality"
        assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass based on current test output"
        assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% line coverage based on current test output"
        assert isinstance(result["relevant_files"], list), "Relevant files should be a list"
        assert len(result["relevant_files"]) > 0, "At least one relevant file expected"
        
        mock_github.get_repo.assert_called_with("user/repo")

        # Verify file updates with content and structure checks
        for file_data in result["relevant_files"]:
            file_path = os.path.join(temp_project_dir, file_data["file_path"])
            assert os.path.exists(file_path), f"File {file_path} should exist"
            original_content = file_data["content"]
            with open(file_path, 'r') as f:
                new_content = f.read()
            assert len(new_content) > 0, f"File {file_path} should not be empty"
            
            if "test" in file_data["file_path"].lower():
                # Test file checks
                assert "test" in new_content or "describe" in new_content, "Test file should contain test structures"
                assert "UUID" in new_content, "Expected 'UUID' in test file for this ticket"
                new_test_count = count_test_methods(new_content)
                assert new_test_count > 0, f"Test file {file_path} should contain at least one test method"
            else:
                # Code file checks
                assert "function" in new_content or "class" in new_content, "Code file should contain functions or classes"
                assert "UUID" in new_content, "Expected 'UUID' in code file for this ticket"
                original_entity_count = count_code_entities(original_content)
                new_entity_count = count_code_entities(new_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path}"

def test_full_workflow_invalid_url():
    """Test workflow with an invalid GitHub URL."""
    initial_state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)

def test_full_workflow_empty_ticket():
    """Test workflow with an empty ticket."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = ""
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(ValueError, match="Empty ticket content"):
            app.invoke(initial_state)

def test_full_workflow_github_error():
    """Test workflow with a GitHub error."""
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException("Repo not found")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(GithubException, match="Repo not found"):
            app.invoke(initial_state)

def test_full_workflow_tests_fail(tmp_path):
    """Test workflow when existing tests fail, using a temporary directory."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    project_dir = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)
    (project_dir / "src" / "__tests__" / "main.test.ts").write_text("test('fail', () => { throw new Error('Test failed'); });")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_no_relevant_files(tmp_path):
    """
    Test workflow when no relevant TypeScript files exist due to an unclear ticket.
    Adjusted to expect RuntimeError due to no tests being present.
    """
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = UNCLEAR_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    project_dir = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)
    shutil.rmtree(project_dir / "src", ignore_errors=True)
    (project_dir / "src").mkdir()
    (project_dir / "src" / "irrelevant.ts").write_text("function irrelevant() {}")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_file_write_error(temp_project_dir):
    """Test workflow when a file write error occurs, using a temporary directory."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    def raise_exception(*args, **kwargs):
        raise Exception("File write error")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch('src.code_integrator_agent.CodeIntegratorAgent.update_file', side_effect=raise_exception), \
         patch.object(pre_test_runner_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(temp_project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(Exception, match="File write error"):
            app.invoke(initial_state)

def test_full_workflow_npm_install_fail(tmp_path):
    """Test workflow when npm install fails, using a temporary empty dir."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    project_dir = tmp_path / "madeup_dir"
    project_dir.mkdir()
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="npm install failed"):
            app.invoke(initial_state)

def test_full_workflow_no_ts_files(tmp_path):
    """
    Test workflow when no TypeScript files exist initially, using a temporary directory.
    Adjusted to expect RuntimeError due to no tests being present.
    """
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    project_dir = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)
    shutil.rmtree(project_dir / "src", ignore_errors=True)
    (project_dir / "src").mkdir()
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_multiple_relevant_files(temp_project_dir):
    """Test workflow with multiple relevant TypeScript files using a temporary directory."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(temp_project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(temp_project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
        
        assert "relevant_files" in result, "Relevant files key missing"
        assert isinstance(result["relevant_files"], list), "Relevant files should be a list"
        assert len(result["relevant_files"]) >= 1, "At least one file should be updated"
        
        # Verify file updates with content and structure checks
        for file_data in result["relevant_files"]:
            file_path = os.path.join(temp_project_dir, file_data["file_path"])
            assert os.path.exists(file_path), f"File {file_path} should exist"
            original_content = file_data["content"]
            with open(file_path, 'r') as f:
                new_content = f.read()
            assert len(new_content) > 0, f"File {file_path} should not be empty"
            
            if "test" in file_data["file_path"].lower():
                # Test file checks
                assert "test" in new_content or "describe" in new_content, "Test file should contain test structures"
                assert "UUID" in new_content, "Expected 'UUID' in test file for this ticket"
                new_test_count = count_test_methods(new_content)
                assert new_test_count > 0, f"Test file {file_path} should contain at least one test method"
            else:
                # Code file checks
                assert "function" in new_content or "class" in new_content, "Code file should contain functions or classes"
                assert "UUID" in new_content, "Expected 'UUID' in code file for this ticket"
                original_entity_count = count_code_entities(original_content)
                new_entity_count = count_code_entities(new_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path}"
