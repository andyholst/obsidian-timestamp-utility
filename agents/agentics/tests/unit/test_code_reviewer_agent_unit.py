import pytest
import json
from unittest.mock import MagicMock
from src.code_reviewer_agent import CodeReviewerAgent
from src.state import State
from langchain_core.runnables import Runnable

def test_code_reviewer_agent_initialization():
    """Test CodeReviewerAgent initialization."""
    llm = MagicMock(spec=Runnable)
    agent = CodeReviewerAgent(llm)
    assert agent.name == "CodeReviewer"
    assert agent.llm == llm
    assert hasattr(agent, 'review_chain')

def test_code_reviewer_agent_process_aligned():
    """Test CodeReviewerAgent process with aligned code using mocked LLM."""
    llm = MagicMock(spec=Runnable)
    llm.invoke.return_value = '{"is_aligned": true, "feedback": "Good code", "tuned_prompt": "Keep it", "needs_fix": false}'
    agent = CodeReviewerAgent(llm)
    state = State(
        result={
            'requirements': ['Generate UUID'],
            'acceptance_criteria': ['UUID is valid']
        },
        generated_code='public generateUUID(): string { return "uuid"; }',
        generated_tests='describe("generateUUID", () => { test("works", () => {}); });'
    )
    result = agent.process(state)
    assert 'feedback' in result
    assert isinstance(result['feedback']['is_aligned'], bool)
    assert isinstance(result['feedback']['feedback'], str)
    assert isinstance(result['feedback']['tuned_prompt'], str)
    assert isinstance(result['feedback']['needs_fix'], bool)

def test_code_reviewer_agent_process_needs_fix():
    """Test CodeReviewerAgent process with code that needs fixes using mocked LLM."""
    llm = MagicMock(spec=Runnable)
    llm.invoke.return_value = '{"is_aligned": false, "feedback": "Add error handling", "tuned_prompt": "Improve", "needs_fix": true}'
    agent = CodeReviewerAgent(llm)
    state = State(
        result={
            'requirements': ['Generate UUID with error handling'],
            'acceptance_criteria': ['Handles errors']
        },
        generated_code='public generateUUID(): string { return "uuid"; }',
        generated_tests='describe("generateUUID", () => { test("works", () => {}); });'
    )
    result = agent.process(state)
    assert 'feedback' in result
    assert isinstance(result['feedback']['is_aligned'], bool)
    assert isinstance(result['feedback']['feedback'], str)
    assert isinstance(result['feedback']['tuned_prompt'], str)
    assert isinstance(result['feedback']['needs_fix'], bool)

def test_code_reviewer_agent_process_invalid_json():
    """Test CodeReviewerAgent process with invalid JSON response using mocked LLM."""
    llm = MagicMock(spec=Runnable)
    llm.invoke.return_value = 'invalid json'
    agent = CodeReviewerAgent(llm)
    state = State(
        result={
            'requirements': ['Generate UUID'],
            'acceptance_criteria': ['UUID is valid']
        },
        generated_code='public generateUUID(): string { return "uuid"; }',
        generated_tests='describe("generateUUID", () => { test("works", () => {}); });'
    )
    result = agent.process(state)
    assert isinstance(result['feedback'], dict)
    assert all(key in result['feedback'] for key in ['is_aligned', 'feedback', 'tuned_prompt', 'needs_fix'])
