import os
import json
import sys
import logging
import re
from github import Github, GithubException
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

# Initialize clients
github = Github(GITHUB_TOKEN)
llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('ticket_interpreter.log')
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Define the state to track data through the workflow
class State(TypedDict):
    url: str
    ticket_content: str
    result: dict

# Function to validate GitHub URL
def validate_github_url(url: str) -> bool:
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    return bool(re.match(pattern, url))

# Node 1: Fetch the GitHub issue
def fetch_issue(state: State) -> State:
    url = state['url']
    if not validate_github_url(url):
        logger.error(f"Invalid GitHub URL: {url}")
        raise ValueError("Invalid GitHub URL")
    parts = url.split('/')
    owner, repo, issue_number = parts[3], parts[4], int(parts[6])
    try:
        repo = github.get_repo(f"{owner}/{repo}")
        issue = repo.get_issue(issue_number)
        state['ticket_content'] = issue.body
        if not state['ticket_content']:
            logger.error("Ticket has no content")
            raise ValueError("Empty ticket content")
        logger.info(f"Fetched issue {issue_number} from {owner}/{repo}")
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise
    return state

# Updated prompt template
prompt_template = PromptTemplate(
    input_variables=["ticket_content"],
    template=(
        "You are an AI assistant analyzing GitHub tickets for software applications. Your task is to extract or infer the following fields from the ticket content and return them in a structured JSON format:\n\n"
        "- **Title**: The first line of the provided content is the issue title. Use it as is.\n"
        "- **Description**: For well-structured tickets, identify the introductory paragraph after the title and before any requirements or acceptance criteria, and use only its first sentence as the description. For brief or vague tickets, infer a detailed description based on the title and content. Always include the application name if mentioned and expand acronyms on first use (e.g., 'UUID' to 'Universally Unique Identifier').\n"
        "- **Requirements**: A list of specific tasks or conditions needed to implement the feature or fix, often starting with 'The command must', 'It should', etc. If not specified, infer reasonable requirements based on the description.\n"
        "- **Acceptance Criteria**: A list of verifiable conditions to confirm the feature or fix is complete, often found after phrases like 'When this is considered done'. If not specified, infer standard acceptance criteria based on the requirements.\n\n"
        "Return only a JSON object with the fields title, description, requirements, and acceptance_criteria. Ensure your response is a valid JSON object with no additional text or code blocks.\n\n"
        "Ticket content:\n{ticket_content}\n\n"
        "Expected JSON format:\n"
        "{{\n"
        "  \"title\": \"string\",\n"
        "  \"description\": \"string\",\n"
        "  \"requirements\": [\"string\", ...],\n"
        "  \"acceptance_criteria\": [\"string\", ...]\n"
        "}}"
    )
)

# Function to validate LLM response
def validate_llm_response(response: dict) -> bool:
    required_keys = {'title', 'description', 'requirements', 'acceptance_criteria'}
    if not required_keys.issubset(response.keys()):
        return False
    if not isinstance(response['requirements'], list) or not isinstance(response['acceptance_criteria'], list):
        return False
    return True

# Node 2: Process the ticket with the LLM
def process_with_llm(state: State) -> State:
    ticket_content = state['ticket_content']
    prompt = prompt_template.format(ticket_content=ticket_content)
    for attempt in range(3):  # Retry up to 3 times
        response = llm(prompt)
        logger.info(f"LLM response attempt {attempt + 1}: {response}")
        try:
            # Try to extract JSON if embedded in text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
            else:
                result = json.loads(response.strip())
            if validate_llm_response(result):
                state['result'] = result
                logger.info("Successfully processed ticket with LLM")
                return state
            else:
                logger.warning(f"Invalid LLM response structure on attempt {attempt + 1}")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON on attempt {attempt + 1}")
    logger.error("Failed to get valid response from LLM after 3 attempts")
    raise ValueError("Invalid LLM response")

# Node 3: Output the result
def output_result(state: State) -> State:
    result = state['result']
    logger.info("Final result:\n" + json.dumps(result, indent=2))
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

# Set the entry_point
graph.set_entry_point("fetch_issue")

# Compile the graph into an executable app
app = graph.compile()

# Main execution
if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python ticket_interpreter.py <issue_url>")
        sys.exit(1)
    issue_url = sys.argv[1]
    initial_state = {"url": issue_url}
    try:
        app.invoke(initial_state)
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)
