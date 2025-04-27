from typing import TypedDict

class State(TypedDict):
    url: str
    ticket_content: str
    result: dict
    generated_code: str
    generated_tests: str
