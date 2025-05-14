import pytest
import os
from src.code_extractor_agent import CodeExtractorAgent
from src.state import State
from src.agentics import llm

@pytest.fixture
def temp_project_dir(tmp_path):
    # Given: A temporary project directory with TypeScript files
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    src_dir = project_dir / "src"
    src_dir.mkdir()
    tests_dir = src_dir / "tests"
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
    
    # When: Processing the ticket
    result = agent.process(state)
    
    # Then: Verify relevant files are identified
    relevant_files = result["relevant_files"]
    assert isinstance(relevant_files, list), "Relevant files should be a list"
    paths = [f["file_path"] for f in relevant_files]
    assert "src/main.ts" in paths, "main.ts should be included"
    assert "src/tests/main.test.ts" in paths, "main.test.ts should be included"
    assert "src/utils.ts" not in paths, "utils.ts should not be included"

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
    
    # When: Processing the ticket
    result = agent.process(state)
    
    # Then: Verify no relevant files are found
    relevant_files = result["relevant_files"]
    assert isinstance(relevant_files, list), "Relevant files should be a list"
    assert len(relevant_files) == 0 or all("main.ts" not in f["file_path"] for f in relevant_files), "No relevant files expected"

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
    
    # When: Processing the ticket
    result = agent.process(state)
    
    # Then: Verify no files are found
    assert result["relevant_files"] == [], "Expected empty relevant files list"

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
    
    # When: Processing the ticket
    result = agent.process(state)
    
    # Then: Verify no non-existent files are included
    relevant_files = result["relevant_files"]
    assert isinstance(relevant_files, list), "Relevant files should be a list"
    assert all("nonexistent.ts" not in f["file_path"] for f in relevant_files), "Non-existent files should not be included"

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
