import pytest
import os
import shutil
import re
from src.code_integrator_agent import CodeIntegratorAgent
from src.state import State
from src.agentics import llm

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
    """
    Fixture to create a temporary project directory with src backup and restore,
    without copying the entire project each time.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    src_dir = project_dir / "src"
    src_backup_dir = project_dir / "src_backup"
    original_src = '/project/src'
    
    # Copy only the src directory from the real project
    shutil.copytree(original_src, src_dir)
    shutil.copytree(src_dir, src_backup_dir)
    
    yield project_dir
    
    # Restore src from backup
    shutil.rmtree(src_dir)
    shutil.copytree(src_backup_dir, src_dir)
    shutil.rmtree(src_backup_dir)

def test_code_integrator_agent_update_files(temp_project_dir):
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="function newFunc() {}",
        generated_tests="describe('TimestampPlugin: newFunc', () => {});\ndescribe('TimestampPlugin: new-command', () => {});",
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "import * as obsidian from 'obsidian';\nclass TimestampPlugin extends obsidian.Plugin {\n    onload() {}\n}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {\n    test('example', () => {});\n});"}
        ],
        result={"title": "Add new function", "description": "Add newFunc", "requirements": [], "acceptance_criteria": []}
    )
    result = agent(state)
    updated_code_file = os.path.join(temp_project_dir, "src", "main.ts")
    updated_test_file = os.path.join(temp_project_dir, "src", "__tests__", "main.test.ts")
    assert os.path.exists(updated_code_file), "Updated code file should exist"
    assert os.path.exists(updated_test_file), "Updated test file should exist"
    with open(updated_code_file, 'r') as f:
        code_content = f.read()
        assert "class TimestampPlugin extends obsidian.Plugin" in code_content, "Original class should be preserved"
        assert "onload()" in code_content, "onload method should be preserved"
        assert len(code_content.splitlines()) > 3, "New code should be added"
        check_ts_code_intact(state["relevant_code_files"][0]["content"], code_content)
    with open(updated_test_file, 'r') as f:
        test_content = f.read()
        assert "describe('TimestampPlugin'" in test_content, "Top-level describe block should be preserved"
        assert "test('example'" in test_content or "it('example'" in test_content, "Original test should be preserved"
        assert re.search(r'\b(test|it)\(', test_content), "New test structures should be present"
        check_ts_tests_intact(state["relevant_test_files"][0]["content"], test_content)

def test_code_integrator_agent_create_new_files(temp_project_dir):
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="function newFeature() {}",
        generated_tests="test('newFeature', () => {})",
        relevant_code_files=[],
        relevant_test_files=[],
        result={"title": "New Feature", "description": "Implement new feature", "requirements": [], "acceptance_criteria": []}
    )
    result = agent(state)
    assert "relevant_code_files" in result, "Relevant code files should be updated in state"
    assert "relevant_test_files" in result, "Relevant test files should be updated in state"
    assert len(result["relevant_code_files"]) == 1, "One new code file should be created"
    assert len(result["relevant_test_files"]) == 1, "One new test file should be created"
    new_code_file = os.path.join(temp_project_dir, result["relevant_code_files"][0]["file_path"])
    new_test_file = os.path.join(temp_project_dir, result["relevant_test_files"][0]["file_path"])
    assert os.path.exists(new_code_file), "New code file should exist"
    assert os.path.exists(new_test_file), "New test file should exist"
    with open(new_code_file, 'r') as f:
        code_content = f.read()
        assert "newFeature" in code_content, "New feature should be mentioned in code"
        assert re.search(r'\b(function|class)\b', code_content), "Code should contain functions or classes"
    with open(new_test_file, 'r') as f:
        test_content = f.read()
        assert "newFeature" in test_content, "New feature should be mentioned in tests"
        assert re.search(r'\b(test|it|describe)\b', test_content), "Test file should contain test structures"

def test_code_integrator_agent_missing_describe_block(temp_project_dir):
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="function newFunc() {}",
        generated_tests="describe('TimestampPlugin: newFunc', () => {});\ndescribe('TimestampPlugin: new-command', () => {});",
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "function main() {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "console.log('No describe block');"}
        ],
        result={"title": "Add new function", "description": "Add newFunc", "requirements": [], "acceptance_criteria": []}
    )
    with pytest.raises(ValueError, match="Could not find describe"):
        agent(state)

def test_code_integrator_agent_invalid_llm_filename(temp_project_dir):
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="function invalidFunc() {}",
        generated_tests="describe('TimestampPlugin: invalidFunc', () => {});",
        relevant_code_files=[],
        relevant_test_files=[],
        result={"title": "Invalid Filename Test", "description": "Test invalid filename with spaces and special chars!", "requirements": [], "acceptance_criteria": []}
    )
    result = agent(state)
    code_paths = [f["file_path"] for f in result["relevant_code_files"]]
    assert "invalid" in code_paths[0].lower(), "Fallback filename should use sanitized title"
