import os
import json
import sys
from github import Github
from langchain.llms import Ollama
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

# Initialize clients
github = Github(GITHUB_TOKEN)
llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST)

# Define the state to track data through the workflow
class State(TypedDict):
    url: str
    ticket_content: str
    result: dict

# Node 1: Fetch the GitHub issue
def fetch_issue(state: State) -> State:
    url = state['url']
    parts = url.split('/')
    owner, repo, issue_number = parts[3], parts[4], int(parts[6])
    repo = github.get_repo(f"{owner}/{repo}")
    issue = repo.get_issue(issue_number)
    state['ticket_content'] = issue.body
    return state

# Node 2: Process the ticket with the LLM
def process_with_llm(state: State) -> State:
    ticket_content = state['ticket_content']
    prompt = (
        "Analyze the following GitHub ticket and extract or infer the title, description, "
        "requirements, and acceptance criteria. Output the result in JSON format:\n\n"
        "{\n"
        "  \"title\": \"...\",\n"
        "  \"description\": \"...\",\n"
        "  \"requirements\": [\"...\", \"...\"],\n"
        "  \"acceptance_criteria\": [\"...\", \"...\"]\n"
        "}\n\n"
        f"Ticket:\n{ticket_content}"
    )
    response = llm(prompt)  # Call the LLM via LangChain
    try:
        state['result'] = json.loads(response.strip())
    except json.JSONDecodeError:
        print("Failed to parse LLM response as JSON")
        sys.exit(1)
    return state

# Node 3: Output the result
def output_result(state: State) -> State:
    print(json.dumps(state['result'], indent=2))
    return state

# Define the LangGraph workflow
graph = StateGraph(State)
graph.add_node("fetch_issue", fetch_issue)
graph.add_node("process_with_llm", process_with_llm)
graph.add_node("output_result", output_result)

# Define the flow: fetch -> process -> output
graph.add_edge("fetch_issue", "process_with_llm")
graph.add_edge("process_with_llm", "output_result")
graph.add_edge("output_result", END)

# Set the entry point
graph.set_entry_point("fetch_issue")

# Compile the graph into an executable app
app = graph.compile()

# Main execution
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ticket_interpreter.py <issue_url>")
        sys.exit(1)
    issue_url = sys.argv[1]
    initial_state = {"url": issue_url}
    app.invoke(initial_state)
