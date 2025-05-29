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
        Process the refined ticket to extract relevant TypeScript files from the project source directory.
        Updates state with separate relevant_code_files and relevant_test_files.
        """
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting code extraction process")
        refined_ticket = state['refined_ticket']
        log_info(self.logger, f"Refined ticket received: {json.dumps(refined_ticket, indent=2)}")

        # Step 1: Collect all .ts files and their contents
        log_info(self.logger, "Collecting TypeScript files from project source")
        src_dir = os.path.join(self.project_root, 'src')
        all_ts_files = []
        file_contents = {}
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.ts'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.project_root)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        all_ts_files.append(rel_path)
                        file_contents[rel_path] = content
                        log_info(self.logger, f"Collected file: {rel_path} with content length: {len(content)}")
                        log_info(self.logger, f"Content of {rel_path}: {content}")
                    except Exception as e:
                        self.logger.error(f"Failed to read file {rel_path}: {str(e)}")
                        continue
        log_info(self.logger, f"Total .ts files found: {len(all_ts_files)}")

        if not all_ts_files:
            state['relevant_code_files'] = []
            state['relevant_test_files'] = []
            log_info(self.logger, "No TypeScript files found in project source; setting relevant files to empty lists")
            return state

        # Step 2: Extract identifiers from the ticket
        log_info(self.logger, "Extracting identifiers from refined ticket")
        identifiers = self.extract_identifiers(refined_ticket)
        if not identifiers:
            state['relevant_code_files'] = []
            state['relevant_test_files'] = []
            log_info(self.logger, "No relevant identifiers found in the ticket; setting relevant files to empty lists")
            return state

        # Step 3: Pre-filter files based on content relevance or file name
        log_info(self.logger, "Pre-filtering files based on content relevance or file name")
        candidate_files = {
            path: content for path, content in file_contents.items()
            if self.is_content_relevant(content, identifiers) or any(id.lower() in path.lower() for id in identifiers)
        }
        log_info(self.logger, f"Candidate files identified: {list(candidate_files.keys())}")

        # Step 4: Create prompt for LLM with file contents and enable thinking mode
        log_info(self.logger, "Preparing LLM prompt for file relevance determination")
        file_summaries = "\n".join(
            f"- {path}: {content}"
            for path, content in candidate_files.items()
        ) or "No candidate files found based on initial filtering."
        prompt = (
            "/think\n"
            f"Given the following TypeScript files in an Obsidian plugin project under project/src:\n\n"
            f"{file_summaries}\n\n"
            f"And the following ticket for the Obsidian plugin:\n\n"
            f"{json.dumps(refined_ticket, indent=2)}\n\n"
            f"Please select which of these files are most relevant to the task described in the ticket. "
            f"Consider both code files and their corresponding test files. For example, if 'src/main.ts' is relevant, "
            f"also consider 'src/__tests__/main.test.ts' if it exists. Prioritize updating 'src/main.ts' and "
            f"'src/__tests__/main.test.ts' for tasks involving the Obsidian plugin. "
            f"Return only a JSON array of the relevant file paths, like [\"src/main.ts\", \"src/__tests__/main.test.ts\"]. "
            f"If no files are relevant, return an empty array []."
        )
        log_info(self.logger, f"LLM prompt prepared with {len(candidate_files)} candidate files: {prompt}")

        # Step 5: Invoke LLM and clean response
        log_info(self.logger, "Invoking LLM to determine relevant files")
        try:
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            log_info(self.logger, f"LLM response: {clean_response}")
            relevant_files = json.loads(clean_response.strip())
            if not isinstance(relevant_files, list):
                raise ValueError("LLM response is not a list")
            # Filter to existing files and remove duplicates while preserving order
            relevant_files = list(dict.fromkeys(
                file for file in relevant_files if file in all_ts_files
            ))
            log_info(self.logger, f"Relevant files from LLM: {relevant_files}")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse LLM response: {str(e)}. Using content-based filtering only.")
            relevant_files = list(candidate_files.keys())
            log_info(self.logger, f"Fallback relevant files: {relevant_files}")

        # Step 6: Prepare output with file contents and separate into code and test files
        log_info(self.logger, "Preparing relevant files data for state update")
        relevant_code_files = []
        relevant_test_files = []
        for file in relevant_files:
            content = file_contents.get(file, "")
            file_data = {"file_path": file, "content": content}
            if self.is_test_file(file):
                relevant_test_files.append(file_data)
            else:
                relevant_code_files.append(file_data)
            log_info(self.logger, f"Added file: {file} as {'test' if self.is_test_file(file) else 'code'} file with content length: {len(content)}")
            log_info(self.logger, f"Content of {file}: {content}")

        # Step 7: Update state with separated lists and log
        state['relevant_code_files'] = relevant_code_files
        state['relevant_test_files'] = relevant_test_files
        log_info(self.logger, f"Code extraction completed. Relevant code files: {[f['file_path'] for f in relevant_code_files]}, Relevant test files: {[f['file_path'] for f in relevant_test_files]}")
        log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state
