# agentics.py
import os
import sys
import logging
import json
from typing import Dict, Any

from github import Github, Auth
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .state import State
from .fetch_issue_agent import FetchIssueAgent
from .ticket_clarity_agent import TicketClarityAgent
from .process_llm_agent import ProcessLLMAgent
from .code_generator_agent import CodeGeneratorAgent
from .output_result_agent import OutputResultAgent
from .pre_test_runner_agent import PreTestRunnerAgent
from .code_extractor_agent import CodeExtractorAgent
from .code_integrator_agent import CodeIntegratorAgent
from .config import LOGGER_LEVEL, INFO_AS_DEBUG
from .utils import log_info, validate_github_url

# Environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')

# Set up logging for prod.agentics
logger = logging.getLogger(__name__)
logger.setLevel(LOGGER_LEVEL)
file_handler = logging.FileHandler('agentics.log')
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Configure root logger to ensure all agent logs are output to console
root_logger = logging.getLogger()
root_logger.setLevel(LOGGER_LEVEL)
root_console_handler = logging.StreamHandler()
root_console_handler.setFormatter(formatter)
root_logger.addHandler(root_console_handler)

log_info(logger, "Initializing agentics application")
log_info(logger, f"Using GITHUB_TOKEN: {'set' if GITHUB_TOKEN else 'not set'}")
log_info(logger, f"OLLAMA_HOST: {OLLAMA_HOST}")
log_info(logger, f"OLLAMA_MODEL: {OLLAMA_MODEL}")

# Load knowledge base for pseudo-RAG
knowledge_path = os.path.join(os.path.dirname(__file__), 'knowledge.json')
with open(knowledge_path, 'r') as f:
    knowledge = json.load(f)
log_info(logger, "Knowledge base loaded successfully")

# Initialize clients
log_info(logger, "Initializing GitHub client")
auth = Auth.Token(GITHUB_TOKEN)
github = Github(auth=auth)
log_info(logger, "GitHub client initialized successfully")

log_info(logger, "Initializing Ollama LLM client")
llm = OllamaLLM(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.3,  # Lowered for less hallucinations
    top_p=0.5,
    top_k=10,
    min_p=0,
    extra_params={
        "presence_penalty": 1.5,  # Added to reduce repetition/hallucinations
        "num_ctx": 8192,  # Balanced context
        "num_predict": 8192
    }
)
log_info(logger, "Ollama LLM client initialized successfully")

# Define the prompt template with optimized instructions
log_info(logger, "Defining prompt template")
prompt_template = PromptTemplate(
    input_variables=["ticket_content"],
    template=(
        "/think\n"
        "Extract or infer from the ticket: title (first line or 'Untitled Task'), "
        "description (concise summary or 'No description provided'), "
        "requirements (list or empty), acceptance_criteria (list or empty). "
        "Stick to ticket facts; no assumptions. Return only JSON object.\n\n"
        "Ticket: {ticket_content}\n\n"
        "Format: {{\"title\": \"str\", \"description\": \"str\", \"requirements\": [\"str\"], \"acceptance_criteria\": [\"str\"]}}"
    )
)
log_info(logger, "Prompt template defined successfully")

# Instantiate agents (pass knowledge to relevant ones)
log_info(logger, "Instantiating agents")
fetch_issue_agent = FetchIssueAgent(github)
ticket_clarity_agent = TicketClarityAgent(llm, github)
code_extractor_agent = CodeExtractorAgent(llm)
process_llm_agent = ProcessLLMAgent(llm, prompt_template)
code_generator_agent = CodeGeneratorAgent(llm, knowledge)
pre_test_runner_agent = PreTestRunnerAgent()
code_integrator_agent = CodeIntegratorAgent(llm)
output_result_agent = OutputResultAgent()
log_info(logger, "Agents instantiated successfully")

# Define the LangGraph workflow with checkpointing for efficiency
log_info(logger, "Defining LangGraph workflow")
memory = SqliteSaver.from_conn_string(":memory:")  # In-memory checkpointing
graph = StateGraph(State)
graph.add_node("pre_test_runner", pre_test_runner_agent)
graph.add_node("fetch_issue", fetch_issue_agent)
graph.add_node("ticket_clarity", ticket_clarity_agent)
graph.add_node("code_extractor", code_extractor_agent)
graph.add_node("process_with_llm", process_llm_agent)
graph.add_node("generate_code", code_generator_agent)
graph.add_node("integrate_code", code_integrator_agent)
graph.add_node("output_result", output_result_agent)

# Define the flow with error handling
def should_continue(state: State) -> str:
    if 'error' in state:
        return END
    return "next_node"

graph.add_conditional_edges("fetch_issue", should_continue, {"next_node": "ticket_clarity", END: END})

log_info(logger, "Defining workflow edges")
graph.add_edge("pre_test_runner", "fetch_issue")
graph.add_edge("fetch_issue", "ticket_clarity")
graph.add_edge("ticket_clarity", "code_extractor")
graph.add_edge("code_extractor", "process_with_llm")
graph.add_edge("process_with_llm", "generate_code")
graph.add_edge("generate_code", "integrate_code")
graph.add_edge("integrate_code", "output_result")
graph.add_edge("output_result", END)

graph.set_entry_point("pre_test_runner")
app = graph.compile(checkpointer=memory)  # Enable checkpointing
log_info(logger, "Workflow defined and compiled successfully")

# Main execution
if __name__ == "__main__":
    log_info(logger, "Starting main execution")
    if len(sys.argv) != 2:
        logger.error("Usage: python agentics.py <issue_url>")
        sys.exit(1)
    issue_url = sys.argv[1]
    log_info(logger, f"Processing issue URL: {issue_url}")
    initial_state: Dict[str, Any] = {"url": issue_url}
    try:
        log_info(logger, "Invoking workflow")
        app.invoke(initial_state)
        log_info(logger, "Workflow completed successfully")
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        sys.exit(1)
