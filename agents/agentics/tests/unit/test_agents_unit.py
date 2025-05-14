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
PROJECT_ROOT = '/project'

# Load the sentence transformer model for semantic similarity
model = SentenceTransformer('all-MiniLM-L6-v2')

def calculate_semantic_similarity(expected_text, actual_text):
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
    valid_url = "https://github.com/user/repo/issues/1"
    pull_url = "https://github.com/user/repo/pull/1"
    invalid_url = "invalid_url"
    assert validate_github_url(valid_url) == True, "Valid issue URL should return True"
    assert validate_github_url(pull_url) == False, "Pull request URL should return False"
    assert validate_github_url(invalid_url) == False, "Invalid URL should return False"

def test_full_workflow_unit(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
        assert "result" in result, "Result key missing"
        assert "generated_code" in result, "Generated code missing"
        assert "generated_tests" in result, "Generated tests missing"
        assert "existing_tests_passed" in result, "Tests passed missing"
        assert "existing_coverage_all_files" in result, "Coverage missing"
        assert "relevant_code_files" in result, "Relevant code files missing"
        assert "relevant_test_files" in result, "Relevant test files missing"
        assert isinstance(result["result"], dict), "Result should be a dictionary"
        similarity = compute_ticket_similarity(EXPECTED_TICKET_JSON, result["result"])
        assert similarity >= 70, f"Semantic similarity {similarity:.2f}% is below 70% threshold"
        assert "UUID" in result["generated_code"], "Generated code should contain 'UUID'"
        assert "this.addCommand" in result["generated_code"], "Generated code should include command addition"
        assert "UUID" in result["generated_tests"], "Generated tests should test UUID functionality"
        assert result["existing_tests_passed"] == 20, "Expected 20 tests to pass"
        assert result["existing_coverage_all_files"] == 46.15, "Expected 46.15% coverage"
        assert isinstance(result["relevant_code_files"], list), "Relevant code files should be a list"
        assert isinstance(result["relevant_test_files"], list), "Relevant test files should be a list"
        assert len(result["relevant_code_files"]) > 0 or len(result["relevant_test_files"]) > 0, "At least one relevant file expected"
        mock_github.get_repo.assert_called_with("user/repo")
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
                assert "UUID" in new_content, "Expected 'UUID' in test file"
                new_test_count = count_test_methods(new_content)
                assert new_test_count > 0, f"Test file {file_path} should contain at least one test method"
                original_test_count = count_test_methods(original_content)
                assert new_test_count > original_test_count, f"Number of tests should not decrease in {file_path}"
                check_ts_tests_intact(original_content, new_content)
            else:
                assert "function" in new_content or "class" in new_content, "Code file should contain functions or classes"
                assert "UUID" in new_content, "Expected 'UUID' in code file"
                original_entity_count = count_code_entities(original_content)
                new_entity_count = count_code_entities(new_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path}"
                check_ts_code_intact(original_content, new_content)

def test_full_workflow_invalid_url():
    initial_state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)

def test_full_workflow_empty_ticket():
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = ""
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github):
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(ValueError, match="Empty ticket content"):
            app.invoke(initial_state)

def test_full_workflow_github_error():
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException(404, data={"message": "Not Found"}, headers={})
    
    with patch.object(fetch_issue_agent, 'github', mock_github):
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(GithubException, match="404.*Not Found"):
            app.invoke(initial_state)

def test_full_workflow_tests_fail(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    (project_dir / "src" / "__tests__" / "main.test.ts").write_text("test('fail', () => { throw new Error('Test failed'); });")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_no_relevant_files(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = UNCLEAR_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    shutil.rmtree(project_dir / "src", ignore_errors=True)
    (project_dir / "src").mkdir()
    (project_dir / "src" / "irrelevant.ts").write_text("function irrelevant() {}")
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_file_write_error(src_backup):
    project_dir = src_backup
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
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(Exception, match="File write error"):
            app.invoke(initial_state)

def test_full_workflow_npm_install_fail(tmp_path):
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    project_dir = tmp_path / "madeup_dir"
    project_dir.mkdir()
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Install command failed"):
            app.invoke(initial_state)

def test_full_workflow_no_ts_files(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    shutil.rmtree(project_dir / "src", ignore_errors=True)
    (project_dir / "src").mkdir()
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(RuntimeError, match="Existing tests failed"):
            app.invoke(initial_state)

def test_full_workflow_multiple_relevant_files(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
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
                assert "UUID" in new_content, "Expected 'UUID' in test file"
                new_test_count = count_test_methods(new_content)
                assert new_test_count > 0, f"Test file {file_path} should contain at least one test method"
                original_test_count = count_test_methods(original_content)
                assert new_test_count > original_test_count, f"Number of tests should not decrease in {file_path}"
                check_ts_tests_intact(original_content, new_content)
            else:
                assert "function" in new_content or "class" in new_content, "Code file should contain functions or classes"
                assert "UUID" in new_content, "Expected 'UUID' in code file"
                original_entity_count = count_code_entities(original_content)
                new_entity_count = count_code_entities(new_content)
                assert new_entity_count >= original_entity_count, f"Number of code entities should not decrease in {file_path}"
                check_ts_code_intact(original_content, new_content)

def test_full_workflow_malformed_ticket(src_backup):
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = MALFORMED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
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
    project_dir = src_backup
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    large_content = "# Large Ticket\n" + "Description " * 1000 + "\n- Req1\n- Req2\n- AC1\n- AC2"
    mock_issue.body = large_content
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    
    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(ticket_clarity_agent, 'github', mock_github), \
         patch.object(pre_test_runner_agent, 'project_root', str(project_dir)), \
         patch.object(code_extractor_agent, 'project_root', str(project_dir)), \
         patch.object(code_integrator_agent, 'project_root', str(project_dir)):
        
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
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
