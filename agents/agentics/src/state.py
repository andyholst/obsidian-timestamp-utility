# state.py
from typing import TypedDict, List, Dict, Optional, Any

class State(TypedDict):
    url: str
    ticket_content: Optional[str]
    refined_ticket: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    generated_code: Optional[str]
    generated_tests: Optional[str]
    existing_tests_passed: Optional[int]
    existing_coverage_all_files: Optional[float]
    relevant_code_files: Optional[List[Dict[str, str]]]
    relevant_test_files: Optional[List[Dict[str, str]]]
    new_modules: Optional[List[str]]
    error: Optional[str]
