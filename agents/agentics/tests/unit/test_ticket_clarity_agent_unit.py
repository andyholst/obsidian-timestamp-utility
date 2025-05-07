import pytest
import json
from src.ticket_clarity_agent import TicketClarityAgent
from src.state import State
from unittest.mock import MagicMock

def test_ticket_clarity_agent_clear_ticket():
    mock_llm = MagicMock()
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_issue.return_value = mock_issue

    # Responses: 5 evaluations (all clear), then 1 refinement on the last iteration
    responses = [
        json.dumps({"is_clear": True, "suggestions": []}),  # Evaluate 1
        json.dumps({"is_clear": True, "suggestions": []}),  # Evaluate 2
        json.dumps({"is_clear": True, "suggestions": []}),  # Evaluate 3
        json.dumps({"is_clear": True, "suggestions": []}),  # Evaluate 4
        json.dumps({"is_clear": True, "suggestions": []}),  # Evaluate 5
        json.dumps({
            "title": "Clear Ticket",
            "description": "Implement a UUID generator in Obsidian.",
            "requirements": ["Use uuid library"],
            "acceptance_criteria": ["Verify UUID format"]
        }),  # Refine 5
    ]
    mock_llm.invoke.side_effect = responses

    agent = TicketClarityAgent(mock_llm, mock_github)
    state = {"url": "https://github.com/user/repo/issues/1", "ticket_content": "Clear ticket content"}
    result = agent(state)

    assert "refined_ticket" in result
    assert result["refined_ticket"]["title"] == "Clear Ticket"
    assert mock_issue.create_comment.called
    assert mock_llm.invoke.call_count == 6  # 5 evaluations + 1 refinement

def test_ticket_clarity_agent_vague_ticket():
    mock_llm = MagicMock()
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_repo.get_issue.return_value = mock_issue

    # Responses: eval1 (False), refine1, eval2 (False), refine2, eval3 (True), eval4 (True), eval5 (True), refine5
    responses = [
        json.dumps({"is_clear": False, "suggestions": ["Add details"]}),  # Eval 1
        json.dumps({
            "title": "Vague",
            "description": "Add feature",
            "requirements": [],
            "acceptance_criteria": []
        }),  # Refine 1
        json.dumps({"is_clear": False, "suggestions": ["Specify library"]}),  # Eval 2
        json.dumps({
            "title": "Vague",
            "description": "Add UUID feature",
            "requirements": ["Use uuid"],
            "acceptance_criteria": []
        }),  # Refine 2
        json.dumps({"is_clear": True, "suggestions": []}),  # Eval 3
        json.dumps({"is_clear": True, "suggestions": []}),  # Eval 4
        json.dumps({"is_clear": True, "suggestions": []}),  # Eval 5
        json.dumps({
            "title": "UUID Generator",
            "description": "Add UUID generator",
            "requirements": ["Use uuid"],
            "acceptance_criteria": ["Verify UUID"]
        }),  # Refine 5
    ]
    mock_llm.invoke.side_effect = responses

    agent = TicketClarityAgent(mock_llm, mock_github)
    state = {"url": "https://github.com/user/repo/issues/1", "ticket_content": "Vague ticket"}
    result = agent(state)

    assert "refined_ticket" in result
    assert "UUID Generator" in result["refined_ticket"]["title"]
    assert mock_issue.create_comment.called
    assert mock_llm.invoke.call_count == 8  # 5 evaluations + 3 refinements
