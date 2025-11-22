import pytest
import json
import os
import tempfile
from src.dependency_analyzer_agent import DependencyAnalyzerAgent
from src.state import State

@pytest.fixture
def temp_project_dir(tmp_path):
    # Given: A temporary project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    return project_dir

def test_dependency_analyzer_no_project_root():
    # Given: An agent and state without project_root
    agent = DependencyAnalyzerAgent()
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])

    # When: Processing the state
    result = agent.process(state)

    # Then: available_dependencies is empty list, state is dict with key
    assert result['available_dependencies'] == []
    assert isinstance(result, dict)
    assert 'available_dependencies' in result
    # Assert state keys
    expected_keys = ['url', 'ticket_content', 'refined_ticket', 'result', 'generated_code', 'generated_tests', 'existing_tests_passed', 'existing_coverage_all_files', 'relevant_code_files', 'relevant_test_files', 'available_dependencies']
    for key in expected_keys:
        assert key in result

def test_dependency_analyzer_no_package_json(temp_project_dir):
    # Given: An agent and state with project_root but no package.json
    agent = DependencyAnalyzerAgent()
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])
    state['project_root'] = str(temp_project_dir)

    # When: Processing the state
    result = agent.process(state)

    # Then: available_dependencies is empty list
    assert result['available_dependencies'] == []
    assert isinstance(result, dict)
    assert 'available_dependencies' in result
    assert isinstance(result['available_dependencies'], list)

def test_dependency_analyzer_empty_dev_dependencies(temp_project_dir):
    # Given: package.json with empty devDependencies
    agent = DependencyAnalyzerAgent()
    package_json = temp_project_dir / "package.json"
    package_json.write_text(json.dumps({"name": "test", "devDependencies": {}}))
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])
    state['project_root'] = str(temp_project_dir)

    # When: Processing the state
    result = agent.process(state)

    # Then: available_dependencies is empty list
    assert result['available_dependencies'] == []
    assert isinstance(result, dict)
    assert 'available_dependencies' in result
    assert isinstance(result['available_dependencies'], list)

def test_dependency_analyzer_with_dev_dependencies(temp_project_dir):
    # Given: package.json with devDependencies
    agent = DependencyAnalyzerAgent()
    package_json = temp_project_dir / "package.json"
    package_json.write_text(json.dumps({"name": "test", "devDependencies": {"jest": "^29.0.0", "typescript": "^4.0.0"}}))
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])
    state['project_root'] = str(temp_project_dir)

    # When: Processing the state
    result = agent.process(state)

    # Then: available_dependencies contains the dev dependencies as list of strings
    assert set(result['available_dependencies']) == {"jest", "typescript"}
    assert isinstance(result['available_dependencies'], list)
    assert all(isinstance(dep, str) for dep in result['available_dependencies'])
    assert isinstance(result, dict)
    assert 'available_dependencies' in result

def test_dependency_analyzer_no_dev_dependencies_key(temp_project_dir):
    # Given: package.json without devDependencies key
    agent = DependencyAnalyzerAgent()
    package_json = temp_project_dir / "package.json"
    package_json.write_text(json.dumps({"name": "test"}))
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])
    state['project_root'] = str(temp_project_dir)

    # When: Processing the state
    result = agent.process(state)

    # Then: available_dependencies is empty list
    assert result['available_dependencies'] == []
    assert isinstance(result, dict)
    assert 'available_dependencies' in result
    assert isinstance(result['available_dependencies'], list)

def test_dependency_analyzer_invalid_json(temp_project_dir):
    # Given: Invalid package.json
    agent = DependencyAnalyzerAgent()
    package_json = temp_project_dir / "package.json"
    package_json.write_text("invalid json")
    state = State(url="https://example.com", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])
    state['project_root'] = str(temp_project_dir)

    # When/Then: Processing raises JSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        agent.process(state)

def test_dependency_analyzer_state_preservation(temp_project_dir):
    # Given: package.json with devDependencies and full state
    agent = DependencyAnalyzerAgent()
    package_json = temp_project_dir / "package.json"
    package_json.write_text(json.dumps({"name": "test", "devDependencies": {"eslint": "^8.0.0"}}))
    state = State(url="https://example.com", ticket_content="test", refined_ticket={"title": "test"}, result={"key": "value"}, generated_code="code", generated_tests="tests", existing_tests_passed=5, existing_coverage_all_files=80.0, relevant_code_files=[{"file_path": "a.ts", "content": "a"}], relevant_test_files=[{"file_path": "a.test.ts", "content": "test"}])
    state['project_root'] = str(temp_project_dir)

    # When: Processing the state
    result = agent.process(state)

    # Then: State is preserved, available_dependencies added
    assert result['url'] == "https://example.com"
    assert result['ticket_content'] == "test"
    assert result['available_dependencies'] == ["eslint"]
    assert isinstance(result, dict)
    # Ensure all original keys are present
    for key in state.keys():
        assert key in result
    # Assert types of State fields
    assert isinstance(result['url'], str)
    assert isinstance(result['ticket_content'], str)
    assert isinstance(result['refined_ticket'], dict)
    assert isinstance(result['result'], dict)
    assert isinstance(result['generated_code'], str)
    assert isinstance(result['generated_tests'], str)
    assert isinstance(result['existing_tests_passed'], int)
    assert isinstance(result['existing_coverage_all_files'], float)
    assert isinstance(result['relevant_code_files'], list)
    assert isinstance(result['relevant_test_files'], list)
    assert isinstance(result['available_dependencies'], list)
