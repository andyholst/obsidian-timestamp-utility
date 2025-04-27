import os
import sys
import logging
from github import Github, Auth
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from .state import State
from .fetch_issue_agent import FetchIssueAgent
from .process_llm_agent import ProcessLLMAgent
from .code_generator_agent import CodeGeneratorAgent
from .output_result_agent import OutputResultAgent

# Environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

# Initialize clients
auth = Auth.Token(GITHUB_TOKEN)
github = Github(auth=auth)
llm = OllamaLLM(model=OLLAMA_MODEL, base_url=OLLAMA_HOST)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('agentics.log')
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Define the prompt template
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

# Instantiate agents
fetch_issue_agent = FetchIssueAgent(github)
process_llm_agent = ProcessLLMAgent(llm, prompt_template)
code_generator_agent = CodeGeneratorAgent(llm)
output_result_agent = OutputResultAgent()

# Define the LangGraph workflow
graph = StateGraph(State)
graph.add_node("fetch_issue", fetch_issue_agent)
graph.add_node("process_with_llm", process_llm_agent)
graph.add_node("generate_code", code_generator_agent)
graph.add_node("output_result", output_result_agent)

# Define the flow
graph.add_edge("fetch_issue", "process_with_llm")
graph.add_edge("process_with_llm", "generate_code")
graph.add_edge("generate_code", "output_result")
graph.add_edge("output_result", END)

graph.set_entry_point("fetch_issue")
app = graph.compile()

# Main execution
if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python agentics.py <issue_url>")
        sys.exit(1)
    issue_url = sys.argv[1]
    initial_state = {"url": issue_url}
    try:
        app.invoke(initial_state)
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)
