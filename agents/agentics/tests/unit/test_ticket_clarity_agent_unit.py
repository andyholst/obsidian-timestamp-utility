import pytest
from unittest.mock import MagicMock
from src.ticket_clarity_agent import TicketClarityAgent
from src.state import State
from langchain_core.runnables import Runnable


def test_ticket_clarity_agent_clear_ticket():
    # Given: Mocked GitHub client and clear ticket
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_issue.return_value = mock_issue
    mock_llm = MagicMock(spec=Runnable)
    # Mock returns JSON for the simplified single-call approach
    mock_llm.invoke.return_value = (
        '{"title": "Clear Ticket", "description": "Implement a feature with clear instructions.", '
        '"requirements": ["Implement feature", "Add command", "Handle edge cases", "Add tests", "Update docs"], '
        '"acceptance_criteria": ["Feature works", "Tests pass"], '
        '"implementation_steps": ["Add command", "Implement handler", "Add tests"], '
        '"npm_packages": [], "affected_files": ["src/main.ts"]}'
    )
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Implement a feature with clear instructions.",
    )

    # When: Processing the ticket with mocked LLM
    result = agent.process(state)

    # Then: Verify refined ticket
    assert "refined_ticket" in result, "Refined ticket missing"
    assert all(
        key in result["refined_ticket"]
        for key in ["title", "description", "requirements", "acceptance_criteria"]
    ), "Missing required fields"
    assert len(result["refined_ticket"]["requirements"]) >= 1


def test_ticket_clarity_agent_vague_ticket():
    # Given: Mocked GitHub client and vague ticket
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_issue.return_value = mock_issue
    mock_llm = MagicMock(spec=Runnable)
    # Mock returns JSON for the simplified single-call approach
    mock_llm.invoke.return_value = (
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", '
        '"requirements": ["Add more details", "Implement feature", "Add tests"], '
        '"acceptance_criteria": ["Something cool is added"], '
        '"implementation_steps": ["Add more details"], '
        '"npm_packages": [], "affected_files": ["src/main.ts"]}'
    )
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Add something cool.",
    )

    # When: Processing the ticket with mocked LLM
    result = agent.process(state)

    # Then: Verify refined ticket is improved
    assert "refined_ticket" in result, "Refined ticket missing"
    assert isinstance(result["refined_ticket"], dict), "Refined ticket should be a dict"
    assert len(result["refined_ticket"]["description"]) > len(
        state["ticket_content"]
    ), "Description should be expanded"


def test_ticket_clarity_agent_empty_llm_response():
    # Given: Mocked GitHub client and LLM returns empty response
    mock_github = MagicMock()
    mock_llm = MagicMock(spec=Runnable)
    mock_llm.invoke.return_value = ""  # Empty response
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Add something cool.",
    )

    # When: Processing the ticket with empty LLM response
    result = agent.process(state)

    # Then: Verify fallback is used
    assert "refined_ticket" in result, "Refined ticket missing"
    assert len(result["refined_ticket"]["requirements"]) >= 1


def test_ticket_clarity_agent_invalid_json_response():
    # Given: Mocked GitHub client and LLM returns invalid JSON
    mock_github = MagicMock()
    mock_llm = MagicMock(spec=Runnable)
    mock_llm.invoke.return_value = "This is not JSON at all"
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Add something cool.\n- Requirement 1\n- Requirement 2\n- Requirement 3",
    )

    # When: Processing the ticket with invalid JSON response
    result = agent.process(state)

    # Then: Verify fallback extracts requirements from text
    assert "refined_ticket" in result, "Refined ticket missing"
    assert len(result["refined_ticket"]["requirements"]) >= 1
