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
    # Mock returns evaluation first, then refinement
    mock_llm.invoke.side_effect = [
        '{"is_clear": true, "suggestions": []}',  # iteration 0
        '{"is_clear": true, "suggestions": []}',  # iteration 1
        '{"is_clear": true, "suggestions": []}',  # iteration 2
        '{"is_clear": true, "suggestions": []}',  # iteration 3
        '{"is_clear": true, "suggestions": []}',  # iteration 4
        '{"title": "Clear Ticket", "description": "Implement a feature with clear instructions.", "requirements": ["Implement feature"], "acceptance_criteria": ["Feature works"]}'  # generate_improvements
    ]
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(url="https://github.com/user/repo/issues/1", ticket_content="Implement a feature with clear instructions.")

    # When: Processing the ticket with mocked LLM
    result = agent(state)

    # Then: Verify refined ticket and comment
    assert "refined_ticket" in result, "Refined ticket missing"
    assert all(key in result["refined_ticket"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    mock_issue.create_comment.assert_called_once(), "Expected comment on GitHub"

def test_ticket_clarity_agent_vague_ticket():
    # Given: Mocked GitHub client and vague ticket
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_issue.return_value = mock_issue
    mock_llm = MagicMock(spec=Runnable)
    # Mock returns evaluation first, then refinement
    mock_llm.invoke.side_effect = [
        '{"is_clear": false, "suggestions": ["Add more details"]}',
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", "requirements": ["Add more details"], "acceptance_criteria": ["Something cool is added"]}',
        '{"is_clear": false, "suggestions": ["Add more details"]}',  # retry 1
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", "requirements": ["Add more details"], "acceptance_criteria": ["Something cool is added"]}',
        '{"is_clear": false, "suggestions": ["Add more details"]}',  # retry 2
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", "requirements": ["Add more details"], "acceptance_criteria": ["Something cool is added"]}',
        '{"is_clear": false, "suggestions": ["Add more details"]}',  # retry 3
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", "requirements": ["Add more details"], "acceptance_criteria": ["Something cool is added"]}',
        '{"is_clear": false, "suggestions": ["Add more details"]}',  # retry 4
        '{"title": "Vague Ticket", "description": "Add something cool with more details and specifications.", "requirements": ["Add more details"], "acceptance_criteria": ["Something cool is added"]}'
    ]
    mock_llm.invoke.return_value = '{"is_clear": true, "suggestions": []}'
    agent = TicketClarityAgent(mock_llm, mock_github)
    state = State(url="https://github.com/user/repo/issues/1", ticket_content="Add something cool.")

    # When: Processing the ticket with mocked LLM
    result = agent(state)

    # Then: Verify refined ticket is improved
    assert "refined_ticket" in result, "Refined ticket missing"
    assert isinstance(result["refined_ticket"], dict), "Refined ticket should be a dict"
    assert len(result["refined_ticket"]["description"]) > len(state["ticket_content"]), "Description should be expanded"
    mock_issue.create_comment.assert_called_once(), "Expected comment on GitHub"