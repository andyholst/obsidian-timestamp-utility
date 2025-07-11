# code_extractor_agent.py
import os
import logging
import json
import re
from typing import List, Dict
from .base_agent import BaseAgent
from .utils import remove_thinking_tags, log_info
from .state import State

class CodeExtractorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeExtractor")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.llm = llm_client
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with project root: {self.project_root}")

    def load_stop_words(self) -> set:
        stop_words_file = os.getenv('STOP_WORDS_FILE', 'stop_words.json')
        try:
            if os.path.exists(stop_words_file):
                with open(stop_words_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            else:
                return {
                    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'while', 'for', 'in', 'on', 'at', 'by', 'with',
                    'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
                    'to', 'from', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
                    'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
                    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
                    'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now', 'is', 'are', 'was', 'were', 'be',
                    'have', 'has', 'had', 'do', 'does', 'did', 'would', 'shall', 'could', 'may', 'might', 'must',
                    'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'I', 'me',
                    'you', 'he', 'she', 'it', 'we', 'they', 'him', 'her', 'us', 'them', 'add', 'modify', 'test',
                    'update', 'documentation', 'revise', 'readme', 'installation', 'section', 'reflects', 'changes',
                    'new', 'steps'
                }
        except Exception as e:
            self.logger.error(f"Failed to load stop words: {str(e)}")
            raise

    def is_test_file(self, file_path: str) -> bool:
        parts = file_path.split('/')
        return '__tests__' in parts or file_path.endswith('.test.ts')

    def extract_identifiers(self, ticket: Dict[str, Any]) -> List[str]:
        text = " ".join(str(ticket.get(key, "")) for key in ["title", "description", "requirements", "acceptance_criteria"])
        identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        identifiers = re.findall(identifier_pattern, text)
        try:
            stop_words = self.load_stop_words()
        except Exception:
            stop_words = set()
        return [id for id in identifiers if id.lower() not in stop_words and len(id) > 2]

    def is_content_relevant(self, content: str, identifiers: List[str]) -> bool:
        if not identifiers:
            return False
        content_lower = content.lower()
        return any(identifier.lower() in content_lower for identifier in identifiers)

    def process(self, state: State) -> State:
        refined_ticket = state['refined_ticket']
        src_dir = os.path.join(self.project_root, 'src')
        all_ts_files = []
        file_contents = {}
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.ts'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.project_root)
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    all_ts_files.append(rel_path)
                    file_contents[rel_path] = content

        if not all_ts_files:
            state['relevant_code_files'] = []
            state['relevant_test_files'] = []
            return state

        identifiers = self.extract_identifiers(refined_ticket)
        if not identifiers:
            state['relevant_code_files'] = []
            state['relevant_test_files'] = []
            return state

        candidate_files = {
            path: content for path, content in file_contents.items()
            if self.is_content_relevant(content, identifiers) or any(id.lower() in path.lower() for id in identifiers)
        }

        file_summaries = "\n".join(f"- {path}: {content[:200]}" for path, content in candidate_files.items())  # Truncate for efficiency
        prompt = (
            "/think\n"
            f"Select relevant TypeScript files for ticket: {json.dumps(refined_ticket, indent=2)}\n\n"
            f"Files: {file_summaries}\n\n"
            "Return JSON array of paths only."
        )
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        try:
            relevant_files = json.loads(clean_response.strip())
            relevant_files = list(dict.fromkeys(file for file in relevant_files if file in all_ts_files))
        except:
            relevant_files = list(candidate_files.keys())

        relevant_code_files = []
        relevant_test_files = []
        for file in relevant_files:
            content = file_contents.get(file, "")
            file_data = {"file_path": file, "content": content}
            if self.is_test_file(file):
                relevant_test_files.append(file_data)
            else:
                relevant_code_files.append(file_data)

        state['relevant_code_files'] = relevant_code_files
        state['relevant_test_files'] = relevant_test_files
        return state
