import os
import logging
import json
import re
from .base_agent import BaseAgent
from .utils import remove_thinking_tags, log_info

class CodeExtractorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeExtractor")
        # Use environment variable for project root, default to '/project'
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.llm = llm_client
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with project root: {self.project_root}")

    def load_stop_words(self):
        """
        Load stop words from a configuration file or environment variable.
        Returns a set of stop words to filter out common terms.
        """
        log_info(self.logger, "Loading stop words for identifier extraction")
        stop_words_file = os.getenv('STOP_WORDS_FILE', 'stop_words.json')
        try:
            if os.path.exists(stop_words_file):
                with open(stop_words_file, 'r', encoding='utf-8') as f:
                    stop_words = set(json.load(f))
                log_info(self.logger, f"Loaded {len(stop_words)} stop words from {stop_words_file}: {stop_words}")
            else:
                # Fallback default stop words
                stop_words = {
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
                log_info(self.logger, f"Using {len(stop_words)} default stop words: {stop_words}")
            return stop_words
        except Exception as e:
            self.logger.error(f"Failed to load stop words: {str(e)}")
            raise

    def is_test_file(self, file_path):
        """Determine if a file is a test file based on its path."""
        log_info(self.logger, f"Checking if file is a test file: {file_path}")
        parts = file_path.split('/')
        is_test = '__tests__' in parts or file_path.endswith('.test.ts')
        log_info(self.logger, f"File {file_path} is {'a test file' if is_test else 'not a test file'}")
        return is_test

    def extract_identifiers(self, ticket):
        """Extract potential identifiers (e.g., function/class names, keywords) from the ticket."""
        log_info(self.logger, "Extracting identifiers from ticket")
        identifiers = set()
        # Combine all ticket fields into a single string
        text = " ".join(
            str(ticket.get(key, ""))
            for key in ["title", "description", "requirements", "acceptance_criteria"]
        )
        log_info(self.logger, f"Ticket text for identifier extraction: {text}")
        # Improved regex to capture more potential identifiers (e.g., camelCase, PascalCase)
        identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        identifiers.update(re.findall(identifier_pattern, text))
        try:
            stop_words = self.load_stop_words()
        except Exception as e:
            self.logger.warning(f"Failed to load stop words: {str(e)}. Using default stop words.")
            stop_words = {
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
        # Filter out stop words and short identifiers
        filtered_identifiers = [id for id in identifiers if id.lower() not in stop_words and len(id) > 2]
        log_info(self.logger, f"Extracted and filtered identifiers: {filtered_identifiers}")
        return filtered_identifiers

    def is_content_relevant(self, content, identifiers):
        """Check if file content contains any of the ticket identifiers."""
        log_info(self.logger, "Checking content relevance")
        log_info(self.logger, f"Identifiers to match: {identifiers}")
        if not identifiers:
            log_info(self.logger, "No identifiers provided; content deemed not relevant")
            return False
        content_lower = content.lower()
        is_relevant = any(identifier.lower() in content_lower for identifier in identifiers)
        log_info(self.logger, f"Content relevance result: {is_relevant}")
        return is_relevant

    def process(self, state):
        """
        For this Obsidian plugin, always use main.ts and main.test.ts.
        """
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting code extraction process")

        # For this Obsidian plugin, always use main.ts and main.test.ts
        relevant_code_files = [
            {"file_path": "src/main.ts", "content": self.read_file_content("src/main.ts")}
        ]
        relevant_test_files = [
            {"file_path": "src/__tests__/main.test.ts", "content": self.read_file_content("src/__tests__/main.test.ts")}
        ]

        state['relevant_code_files'] = relevant_code_files
        state['relevant_test_files'] = relevant_test_files
        log_info(self.logger, f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}")
        log_info(self.logger, f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}")
        log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state

    def read_file_content(self, rel_path):
        """Read file content from the project root."""
        full_path = os.path.join(self.project_root, rel_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read file {rel_path}: {str(e)}")
            return ""
