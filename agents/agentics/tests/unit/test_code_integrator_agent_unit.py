import pytest
import os
import shutil
import re
from src.code_integrator_agent import CodeIntegratorAgent
from src.state import State
from src.agentics import llm

@pytest.fixture
def temp_project_dir(tmp_path):
    """
    Fixture to create a temporary project directory by copying the real project structure.
    """
    project_dir = tmp_path / "project"
    # Copy the entire project structure from /project to the temporary directory
    shutil.copytree('/project', str(project_dir), dirs_exist_ok=True)
    return project_dir

def test_code_integrator_agent_update_files(temp_project_dir):
    """
    Test that the agent updates existing files correctly in the isolated environment.
    """
    # Given: Existing files and generated code/tests
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="```typescript\nfunction newFunc() {}\n```",
        generated_tests="```typescript\ntest('newFunc', () => {})\n```",
        relevant_files=[
            {"file_path": "src/main.ts", "content": "function main() {}"},
            {"file_path": "src/__tests__/main.test.ts", "content": "test('main', () => {})"}
        ],
        result={"title": "Add new function", "description": "Add newFunc", "requirements": [], "acceptance_criteria": []}
    )

    # When: The agent processes the state (no mocking, real file writes)
    result = agent(state)

    # Then: Verify file updates in the isolated environment
    updated_code_file = os.path.join(temp_project_dir, "src", "main.ts")
    updated_test_file = os.path.join(temp_project_dir, "src", "__tests__", "main.test.ts")

    # Check that files exist
    assert os.path.exists(updated_code_file), "Updated code file should exist"
    assert os.path.exists(updated_test_file), "Updated test file should exist"

    # Check file contents
    with open(updated_code_file, 'r') as f:
        code_content = f.read()
        assert "function main() {}" in code_content, "Original code should be preserved"
        assert "newFunc" in code_content, "New function should be integrated"

    with open(updated_test_file, 'r') as f:
        test_content = f.read()
        assert "test('main'" in test_content or "it('main'" in test_content, "Original test should be preserved"
        assert "test('newFunc'" in test_content or "it('newFunc'" in test_content, "New test should be integrated"

def test_code_integrator_agent_create_new_files(temp_project_dir):
    """
    Test that the agent creates new files correctly in the isolated environment when no relevant files exist.
    """
    # Given: No relevant files, new code/tests to integrate
    agent = CodeIntegratorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(
        generated_code="```typescript\nfunction newFeature() {}\n```",
        generated_tests="```typescript\ntest('newFeature', () => {})\n```",
        relevant_files=[],
        result={"title": "New Feature", "description": "Implement new feature", "requirements": [], "acceptance_criteria": []}
    )

    # When: The agent processes the state (no mocking, real file writes)
    result = agent(state)

    # Then: Verify new files are created and state is updated
    assert "relevant_files" in result, "Relevant files should be updated in state"
    assert len(result["relevant_files"]) == 2, "Two new files should be created"

    # Check the new files in the isolated environment
    new_code_file = os.path.join(temp_project_dir, result["relevant_files"][0]["file_path"])
    new_test_file = os.path.join(temp_project_dir, result["relevant_files"][1]["file_path"])

    # Verify file existence
    assert os.path.exists(new_code_file), "New code file should exist"
    assert os.path.exists(new_test_file), "New test file should exist"

    # Verify file contents
    with open(new_code_file, 'r') as f:
        code_content = f.read()
        assert "newFeature" in code_content, "New feature should be mentioned in code"
        assert re.search(r'\b(function|class)\b', code_content), "Code should contain functions or classes"

    with open(new_test_file, 'r') as f:
        test_content = f.read()
        assert "newFeature" in test_content, "New feature should be mentioned in tests"
        assert re.search(r'\b(test|it|describe)\b', test_content), "Test file should contain test structures"

    # Verify filenames (case-insensitive check for "newfeature")
    assert "newfeature" in os.path.basename(new_code_file).lower(), "Code filename should include 'newfeature'"
    assert "newfeature" in os.path.basename(new_test_file).lower(), "Test filename should include 'newfeature'"
