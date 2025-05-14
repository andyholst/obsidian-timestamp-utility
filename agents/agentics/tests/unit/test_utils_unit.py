import pytest
from src.utils import validate_github_url

def test_validate_github_url_valid():
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
