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
from unittest.mock import patch, MagicMock, AsyncMock
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
        assert "Empty ticket content" in str(exc_info.value)

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
        assert isinstance(exc_info.value.__cause__, GithubException)


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
         patch('src.clients.llm_reasoning', mock_llm_reasoning), \
         patch('src.clients.llm_code', mock_llm_code), \
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




