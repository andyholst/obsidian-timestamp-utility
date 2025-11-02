import pytest
import json
import re
from src.utils import validate_github_url, remove_thinking_tags, parse_json_response

def test_validate_github_url_valid():
    """Test that valid GitHub issue URLs are correctly validated."""
    # Given: Valid GitHub issue URLs
    urls = [
        "https://github.com/user/repo/issues/1",
        "https://github.com/another-user/another-repo/issues/42"
    ]

    # When: Validating URLs
    results = [validate_github_url(url) for url in urls]

    # Then: Verify all are valid
    assert all(result == True for result in results), "Expected all URLs to be valid"

def test_validate_github_url_invalid():
    """Test that invalid URLs are correctly rejected."""
    # Given: Invalid URLs
    urls = [
        "https://github.com/user/repo/pull/1",
        "https://github.com/user/repo/issues/abc",
        "https://example.com/user/repo/issues/1",
        "invalid_url"
    ]

    # When: Validating URLs
    results = [validate_github_url(url) for url in urls]

    # Then: Verify all are invalid
    assert all(result == False for result in results), "Expected all URLs to be invalid"

def test_remove_thinking_tags():
    """Test that thinking tags and markdown code blocks are properly removed."""
    text = "<think>This is thinking</think>Some content```typescript\ncode\n```"
    result = remove_thinking_tags(text)
    assert result == "Some contentcode"

def test_parse_json_response_valid():
    """Test parsing a valid JSON string."""
    # Given a valid JSON string
    response = '{"key": "value"}'
    # When parsing the JSON response
    result = parse_json_response(response)
    # Then it should return the parsed dictionary
    assert result == {"key": "value"}

def test_parse_json_response_with_extra_text():
    """Test parsing JSON with extra text after it."""
    # Given JSON with extra text after it
    response = '{"key": "value"} some extra text'
    # When parsing the JSON response
    result = parse_json_response(response)
    # Then it should extract and return the JSON object
    assert result == {"key": "value"}

def test_parse_json_response_nested():
    """Test parsing nested JSON with extra text."""
    # Given nested JSON with extra text
    response = '{"key": {"nested": "value"}} and more text'
    # When parsing the JSON response
    result = parse_json_response(response)
    # Then it should extract and return the nested JSON object
    assert result == {"key": {"nested": "value"}}

def test_parse_json_response_invalid():
    """Test that invalid JSON raises ValueError."""
    # Given completely invalid JSON
    response = 'not json at all'
    # When parsing the JSON response
    # Then it should raise ValueError
    with pytest.raises(ValueError):
        parse_json_response(response)

def test_parse_json_response_partial_json():
    """Test that malformed JSON raises ValueError."""
    # Given malformed JSON
    response = '{"key": "value" and some text'
    # When parsing the JSON response
    # Then it should raise ValueError
    with pytest.raises(ValueError):
        parse_json_response(response)

def test_parse_json_response_empty():
    """Test that empty string raises ValueError."""
    # Given an empty string
    response = ''
    # When parsing the JSON response
    # Then it should raise ValueError
    with pytest.raises(ValueError):
        parse_json_response(response)

def test_parse_json_response_only_extra_text():
    """Test that text without JSON raises ValueError."""
    # Given text without any JSON
    response = 'some text without json'
    # When parsing the JSON response
    # Then it should raise ValueError
    with pytest.raises(ValueError):
        parse_json_response(response)

def test_parse_json_response_complex():
    """Test parsing complex JSON with extra text like LLM responses."""
    # Given complex JSON with extra text (like LLM responses with translations)
    response = '{"is_clear": false, "suggestions": ["test"]}`newline руковордите перевод: JSON ответ:\n\n{\n  "is_clear": false,\n  "suggestions": [\n    "test"\n  ]\n}'
    # When parsing the JSON response
    result = parse_json_response(response)
    # Then it should extract the valid JSON object
    assert result == {"is_clear": False, "suggestions": ["test"]}
