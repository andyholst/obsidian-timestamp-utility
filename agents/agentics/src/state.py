from typing import TypedDict

class State(TypedDict):
    url: str
    ticket_content: str
    refined_ticket: dict
    result: dict
    generated_code: str
    generated_tests: str
    existing_tests_passed: int
    existing_coverage_all_files: float
