from typing import TypedDict, List, Dict

class State(TypedDict):
    url: str
    ticket_content: str
    refined_ticket: dict
    result: dict
    generated_code: str
    generated_tests: str
    existing_tests_passed: int
    existing_coverage_all_files: float
    relevant_code_files: List[Dict[str, str]]
    relevant_test_files: List[Dict[str, str]]
