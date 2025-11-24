import os
import logging
import json
import re
from .tool_integrated_agent import ToolIntegratedAgent
from .tools import read_file_tool, list_files_tool, check_file_exists_tool
from .utils import safe_json_dumps, remove_thinking_tags, log_info

class CodeExtractorAgent(ToolIntegratedAgent):
    def __init__(self, llm_client):
        super().__init__(llm_client, [read_file_tool, list_files_tool, check_file_exists_tool], "CodeExtractor")
        # Use environment variable for project root (can be set later for testing)
        self.project_root = os.getenv('PROJECT_ROOT')
        self.llm = llm_client
        self.monitor.logger.setLevel(logging.INFO)
        if self.project_root:
            log_info(self.name, f"Initialized with project root: {self.project_root}")
        else:
            log_info(self.name, "Initialized without project root (will be set later)")

    def load_stop_words(self):
        """
        Load stop words from a configuration file or environment variable.
        Returns a set of stop words to filter out common terms.
        """
        log_info(self.name, "Loading stop words for identifier extraction")
        stop_words_file = os.getenv('STOP_WORDS_FILE', 'stop_words.json')
        try:
            if os.path.exists(stop_words_file):
                with open(stop_words_file, 'r', encoding='utf-8') as f:
                    stop_words = set(json.load(f))
                log_info(self.name, f"Loaded {len(stop_words)} stop words from {stop_words_file}: {stop_words}")
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
                log_info(self.name, f"Using {len(stop_words)} default stop words: {stop_words}")
            return stop_words
        except Exception as e:
            self.monitor.error(f"Failed to load stop words: {str(e)}")
            raise

    def is_test_file(self, file_path):
        """Determine if a file is a test file based on its path."""
        log_info(self.name, f"Checking if file is a test file: {file_path}")
        parts = file_path.split('/')
        is_test = '__tests__' in parts or file_path.endswith('.test.ts')
        log_info(self.name, f"File {file_path} is {'a test file' if is_test else 'not a test file'}")
        return is_test

    def extract_identifiers(self, ticket):
        """Extract potential identifiers (e.g., function/class names, keywords) from the ticket."""
        log_info(self.name, "Extracting identifiers from ticket")
        identifiers = set()
        # Combine all ticket fields into a single string
        text = " ".join(
            str(ticket.get(key, ""))
            for key in ["title", "description", "requirements", "acceptance_criteria"]
        )
        log_info(self.name, f"Ticket text for identifier extraction: {text}")
        # Improved regex to capture more potential identifiers (e.g., camelCase, PascalCase)
        identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        identifiers.update(re.findall(identifier_pattern, text))
        try:
            stop_words = self.load_stop_words()
        except Exception as e:
            self.monitor.warning(f"Failed to load stop words: {str(e)}. Using default stop words.")
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
        log_info(self.name, f"Extracted and filtered identifiers: {filtered_identifiers}")
        return filtered_identifiers

    def is_content_relevant(self, content, identifiers):
        """Check if file content contains any of the ticket identifiers."""
        log_info(self.name, "Checking content relevance")
        log_info(self.name, f"Identifiers to match: {identifiers}")
        if not identifiers:
            log_info(self.name, "No identifiers provided; content deemed not relevant")
            return False
        content_lower = content.lower()
        is_relevant = any(identifier.lower() in content_lower for identifier in identifiers)
        log_info(self.name, f"Content relevance result: {is_relevant}")
        return is_relevant

    def extract_code_structure(self, content):
        """Extract classes, methods, and other structures from TypeScript content using regex."""
        log_info(self.name, "Extracting code structure from TypeScript content")
        structure = {
            'classes': [],
            'methods': [],
            'interfaces': [],
            'functions': []
        }

        # Extract classes
        class_pattern = r'\bclass\s+(\w+)'
        structure['classes'] = re.findall(class_pattern, content)

        # Extract methods (public/private/protected)
        method_pattern = r'(?:public|private|protected)?\s*(\w+)\s*\([^)]*\)\s*[:{]'
        methods = re.findall(method_pattern, content)
        structure['methods'] = list(set(methods))  # Remove duplicates

        # Extract interfaces
        interface_pattern = r'\binterface\s+(\w+)'
        structure['interfaces'] = re.findall(interface_pattern, content)

        # Extract functions
        function_pattern = r'\bfunction\s+(\w+)'
        structure['functions'] = re.findall(function_pattern, content)

        log_info(self.name, f"Extracted structure: {structure}")
        return structure

    def process(self, state):
        """
        Analyze code structure and determine relevant files dynamically.
        """
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting code extraction process")

        # Extract identifiers from the refined ticket
        ticket = state.get('refined_ticket', {})
        identifiers = self.extract_identifiers(ticket)
        log_info(self.name, f"Extracted identifiers from ticket: {identifiers}")

        # List all files in the project
        try:
            files_result = self.list_files(".")
            all_files = files_result.get('files', []) if isinstance(files_result, dict) else []
            log_info(self.name, f"Found {len(all_files)} files in project")
        except Exception as e:
            log_info(self.name, f"Failed to list files: {str(e)}, falling back to hardcoded files")
            # Fallback to hardcoded files if listing fails
            main_content = self.read_file_content("src/main.ts")
            test_content = self.read_file_content("src/__tests__/main.test.ts")
            code_structure = self.extract_code_structure(main_content)
            test_structure = self.extract_code_structure(test_content)

            relevant_code_files = [
                {"file_path": "src/main.ts", "content": main_content, "structure": code_structure}
            ]
            relevant_test_files = [
                {"file_path": "src/__tests__/main.test.ts", "content": test_content, "structure": test_structure}
            ]
        else:
            # Filter files based on relevance
            relevant_code_files = []
            relevant_test_files = []

            for file_path in all_files:
                if not isinstance(file_path, str):
                    continue

                try:
                    content = self.read_file_content(file_path)
                    if not content:
                        continue

                    is_test = self.is_test_file(file_path)
                    is_relevant = self.is_content_relevant(content, identifiers)

                    if is_relevant:
                        structure = self.extract_code_structure(content)
                        file_info = {
                            "file_path": file_path,
                            "content": content,
                            "structure": structure
                        }

                        if is_test:
                            relevant_test_files.append(file_info)
                        else:
                            relevant_code_files.append(file_info)

                        log_info(self.name, f"Added relevant file: {file_path} (test: {is_test})")

                except Exception as e:
                    log_info(self.name, f"Failed to process file {file_path}: {str(e)}")
                    continue

            # Ensure we have at least the main files if no relevant files found
            if not relevant_code_files:
                log_info(self.name, "No relevant code files found, adding default main.ts")
                main_content = self.read_file_content("src/main.ts")
                if main_content:
                    code_structure = self.extract_code_structure(main_content)
                    relevant_code_files.append({
                        "file_path": "src/main.ts",
                        "content": main_content,
                        "structure": code_structure
                    })

            if not relevant_test_files:
                log_info(self.name, "No relevant test files found, adding default main.test.ts")
                test_content = self.read_file_content("src/__tests__/main.test.ts")
                if test_content:
                    test_structure = self.extract_code_structure(test_content)
                    relevant_test_files.append({
                        "file_path": "src/__tests__/main.test.ts",
                        "content": test_content,
                        "structure": test_structure
                    })

        # Store structure in state for use by other agents
        if relevant_code_files:
            state['code_structure'] = relevant_code_files[0]['structure']
        if relevant_test_files:
            state['test_structure'] = relevant_test_files[0]['structure']

        state['relevant_code_files'] = relevant_code_files
        state['relevant_test_files'] = relevant_test_files

        log_info(self.name, f"Relevant code files: {[file['file_path'] for file in relevant_code_files]}")
        log_info(self.name, f"Relevant test files: {[file['file_path'] for file in relevant_test_files]}")
        log_info(self.name, f"Total relevant files found: {len(relevant_code_files) + len(relevant_test_files)}")
        log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        return state

    def read_file_content(self, rel_path):
        """Read file content from the agent's project root."""
        try:
            full_path = os.path.join(self.project_root, rel_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.monitor.error(f"Failed to read file {rel_path}: {str(e)}")
            return ""
