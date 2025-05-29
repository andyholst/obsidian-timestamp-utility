import pytest
import os
from src.code_extractor_agent import CodeExtractorAgent
from src.state import State
from src.agentics import llm
from unittest.mock import patch

@pytest.fixture
def temp_project_dir(tmp_path):
    # Given: A temporary project directory with TypeScript files
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    src_dir = project_dir / "src"
    src_dir.mkdir()
    tests_dir = src_dir / "__tests__"  # Changed from 'tests' to '__tests__'
    tests_dir.mkdir()
    (src_dir / "main.ts").write_text("function main() {}")
    (src_dir / "utils.ts").write_text("function util() {}")
    (tests_dir / "main.test.ts").write_text("test('main', () => {})")
    return project_dir

def test_code_extractor_agent_relevant_files(temp_project_dir):
    # Given: A ticket mentioning specific files
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(refined_ticket={
        "title": "Update main.ts",
        "description": "Modify main.ts and add tests in main.test.ts",
        "requirements": ["Change main.ts"],
        "acceptance_criteria": ["Verify with main.test.ts"]
    })
    
    # When: Processing the ticket with real LLM
    result = agent.process(state)
    
    # Then: Verify relevant files are identified
    relevant_code_files = result["relevant_code_files"]
    relevant_test_files = result["relevant_test_files"]
    assert isinstance(relevant_code_files, list), "Relevant code files should be a list"
    assert isinstance(relevant_test_files, list), "Relevant test files should be a list"
    code_paths = [f["file_path"] for f in relevant_code_files]
    test_paths = [f["file_path"] for f in relevant_test_files]
    assert "src/main.ts" in code_paths, "main.ts should be included"
    assert "src/__tests__/main.test.ts" in test_paths, "main.test.ts should be included"  # Updated path
    assert "src/utils.ts" not in code_paths, "utils.ts should not be included in code files"
    assert "src/utils.ts" not in test_paths, "utils.ts should not be included in test files"

def test_code_extractor_agent_no_relevant_files(temp_project_dir):
    # Given: A ticket with no specific file mentions
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(refined_ticket={
        "title": "Add new feature",
        "description": "Implement a new feature",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    # When: Processing the ticket with real LLM
    result = agent.process(state)
    
    # Then: Verify no relevant files are found
    relevant_code_files = result["relevant_code_files"]
    relevant_test_files = result["relevant_test_files"]
    assert isinstance(relevant_code_files, list), "Relevant code files should be a list"
    assert isinstance(relevant_test_files, list), "Relevant test files should be a list"
    assert len(relevant_code_files) == 0 or all("main.ts" not in f["file_path"] for f in relevant_code_files), "No relevant code files expected"
    assert len(relevant_test_files) == 0 or all("main.test.ts" not in f["file_path"] for f in relevant_test_files), "No relevant test files expected"

def test_code_extractor_agent_no_ts_files(tmp_path):
    # Given: An empty project directory
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(tmp_path)
    state = State(refined_ticket={
        "title": "Update main.ts",
        "description": "Modify main.ts",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    # When: Processing the ticket with real LLM
    result = agent.process(state)
    
    # Then: Verify no files are found
    assert result["relevant_code_files"] == [], "Expected empty relevant code files list"
    assert result["relevant_test_files"] == [], "Expected empty relevant test files list"

def test_code_extractor_agent_non_existent_files(temp_project_dir):
    # Given: A ticket mentioning non-existent files
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(refined_ticket={
        "title": "Update nonexistent.ts",
        "description": "Modify nonexistent.ts",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    # When: Processing the ticket with real LLM
    result = agent.process(state)
    
    # Then: Verify no non-existent files are included
    relevant_code_files = result["relevant_code_files"]
    relevant_test_files = result["relevant_test_files"]
    assert isinstance(relevant_code_files, list), "Relevant code files should be a list"
    assert isinstance(relevant_test_files, list), "Relevant test files should be a list"
    assert all("nonexistent.ts" not in f["file_path"] for f in relevant_code_files), "Non-existent files should not be included in code files"
    assert all("nonexistent.ts" not in f["file_path"] for f in relevant_test_files), "Non-existent files should not be included in test files"

def test_extract_identifiers():
    # Given: A ticket with identifiable terms
    agent = CodeExtractorAgent(llm)
    ticket = {
        "title": "Update main function",
        "description": "Modify the main function in TypeScript",
        "requirements": ["Add logging"],
        "acceptance_criteria": ["Logs output"]
    }
    
    # When: Extracting identifiers
    identifiers = agent.extract_identifiers(ticket)
    
    # Then: Verify extracted identifiers
    assert "main" in identifiers, "Expected 'main' identifier"
    assert "TypeScript" in identifiers, "Expected 'TypeScript' identifier"
    assert "logging" in identifiers, "Expected 'logging' identifier"
    assert "update" not in identifiers, "Stop word 'update' should be excluded"

def test_is_content_relevant():
    # Given: File content and identifiers
    agent = CodeExtractorAgent(llm)
    content = "function main() { console.log('Hello'); }"
    identifiers = ["main", "console"]
    
    # When: Checking content relevance
    relevant = agent.is_content_relevant(content, identifiers)
    not_relevant = agent.is_content_relevant("function util() {}", ["main"])
    empty_identifiers = agent.is_content_relevant(content, [])
    
    # Then: Verify relevance outcomes
    assert relevant == True, "Content should be relevant"
    assert not_relevant == False, "Content should not be relevant"
    assert empty_identifiers == False, "Empty identifiers should return False"

def test_code_extractor_agent_stop_words_failure(temp_project_dir):
    # Given: A ticket and mocked stop words file loading failure
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(refined_ticket={
        "title": "Update main function",
        "description": "Modify main function",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    with patch.object(agent, 'load_stop_words', side_effect=Exception("File corrupted")):
        # When: Processing the ticket with real LLM
        result = agent.process(state)
    
    # Then: Verify default stop words are used and process continues
    assert "relevant_code_files" in result, "Should have relevant_code_files key"
    assert "relevant_test_files" in result, "Should have relevant_test_files key"

def test_code_extractor_agent_empty_identifiers_with_files(temp_project_dir):
    # Given: A ticket yielding no identifiers but files exist
    agent = CodeExtractorAgent(llm)
    agent.project_root = str(temp_project_dir)
    state = State(refined_ticket={
        "title": "A B C",
        "description": "X Y Z",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    # When: Processing the ticket with real LLM
    result = agent.process(state)
    
    # Then: Verify no relevant files when identifiers are empty
    assert result["relevant_code_files"] == [], "Expected empty relevant_code_files"
    assert result["relevant_test_files"] == [], "Expected empty relevant_test_files"
