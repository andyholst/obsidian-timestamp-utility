import pytest
import os
from ticket_interpreter import app

@pytest.mark.integration
def test_full_workflow_integration():
    assert "GITHUB_TOKEN" in os.environ, "GITHUB_TOKEN environment variable is required"
    assert "OLLAMA_HOST" in os.environ, "OLLAMA_HOST environment variable is required"
    test_issue_url = os.getenv("TEST_ISSUE_URL")
    assert test_issue_url is not None, "TEST_ISSUE_URL environment variable is required"

    initial_state = {"url": test_issue_url}
    result = app.invoke(initial_state)

    assert "result" in result
    result_data = result["result"]

    assert isinstance(result_data, dict)
    assert "title" in result_data
    assert isinstance(result_data["title"], str)
    assert "description" in result_data
    assert isinstance(result_data["description"], str)
    assert "requirements" in result_data
    assert isinstance(result_data["requirements"], list)
    assert "acceptance_criteria" in result_data
    assert isinstance(result_data["acceptance_criteria"], list)
