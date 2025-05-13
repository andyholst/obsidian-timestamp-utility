import os
import json
import re
from .base_agent import BaseAgent

class CodeExtractorAgent(BaseAgent):
    project_root = '/project'

    def __init__(self, llm_client):
        super().__init__("CodeExtractor")
        self.llm = llm_client

    def extract_identifiers(self, ticket):
        """Extract potential identifiers (e.g., function/class names, keywords) from the ticket."""
        identifiers = set()
        # Combine all ticket fields into a single string
        text = " ".join(
            str(ticket.get(key, "")) 
            for key in ["title", "description", "requirements", "acceptance_criteria"]
        )
        # Simple regex to find potential TypeScript identifiers (alphanumeric with underscores)
        identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        identifiers.update(re.findall(identifier_pattern, text))
        # Expanded stop words to filter out common English words
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'while', 'for', 'in', 'on', 'at', 'by', 'with', 'about', 
            'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 
            'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 
            'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 
            'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 
            'will', 'just', 'don', 'should', 'now', 'is', 'are', 'was', 'were', 'be', 'have', 'has', 'had', 'do', 
            'does', 'did', 'would', 'shall', 'could', 'may', 'might', 'must', 'this', 'that', 'these', 'those', 
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'I', 'me', 'you', 'he', 'she', 'it', 'we', 'they', 
            'him', 'her', 'us', 'them', 'add', 'modify', 'test', 'update', 'documentation', 'revise', 'readme', 
            'installation', 'section', 'reflects', 'changes', 'new', 'steps'
        }
        # Filter out stop words and short identifiers
        return [id for id in identifiers if id.lower() not in stop_words and len(id) > 2]

    def is_content_relevant(self, content, identifiers):
        """Check if file content contains any of the ticket identifiers."""
        if not identifiers:
            return False  # No identifiers, so no relevance
        content_lower = content.lower()
        return any(identifier.lower() in content_lower for identifier in identifiers)

    def process(self, state):
        """
        Process the refined ticket to extract relevant TypeScript files from /project/src.
        Updates state['relevant_files'] with a list of dictionaries containing file_path and content.

        Logic:
        - Collect all .ts files from /project/src with their contents.
        - Extract identifiers from the ticket.
        - If no identifiers are found, set relevant_files to empty list.
        - Otherwise, filter files by content relevance and enhance with LLM reasoning.
        - Ensure no duplicates and update state accordingly.
        """
        refined_ticket = state['refined_ticket']

        # Step 1: Collect all .ts files and their contents
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
                    except Exception as e:
                        self.logger.error(f"Failed to read file {rel_path}: {e}")
                        continue
        self.logger.debug(f"All .ts files found: {all_ts_files}")

        if not all_ts_files:
            state['relevant_files'] = []
            self.logger.info("No TypeScript files found in project/src")
            return state

        # Step 2: Extract identifiers from the ticket
        identifiers = self.extract_identifiers(refined_ticket)
        self.logger.debug(f"Extracted identifiers: {identifiers}")

        if not identifiers:
            state['relevant_files'] = []
            self.logger.info("No relevant identifiers found in the ticket")
            return state

        # Step 3: Pre-filter files based on content relevance
        candidate_files = {
            path: content for path, content in file_contents.items()
            if self.is_content_relevant(content, identifiers) or any(id.lower() in path.lower() for id in identifiers)
        }

        # Step 4: Create prompt for LLM with file contents
        file_summaries = "\n".join(
            f"- {path}: {content[:100]}..." 
            for path, content in candidate_files.items()
        ) or "No candidate files found based on initial filtering."
        prompt = (
            f"Given the following TypeScript files in project/src and their content previews:\n\n"
            f"{file_summaries}\n\n"
            f"And the following ticket:\n\n"
            f"{json.dumps(refined_ticket, indent=2)}\n\n"
            f"Please select which of these files are most relevant to the task described in the ticket. "
            f"Consider file names and content (e.g., functions, classes, or keywords mentioned in the ticket). "
            f"Return only a JSON array of the relevant file paths, like [\"src/main.ts\", \"src/utils.ts\"]. "
            f"If no files are relevant, return an empty array []."
        )

        # Step 5: Invoke LLM
        try:
            response = self.llm.invoke(prompt)
            relevant_files = json.loads(response.strip())
            if not isinstance(relevant_files, list):
                raise ValueError("LLM response is not a list")
            # Filter to existing files and remove duplicates while preserving order
            relevant_files = list(dict.fromkeys(
                file for file in relevant_files if file in all_ts_files
            ))
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse LLM response: {e}. Using content-based filtering only.")
            relevant_files = list(candidate_files.keys())

        # Step 6: Prepare output with file contents
        relevant_files_data = []
        for file in relevant_files:
            content = file_contents.get(file, "")
            relevant_files_data.append({"file_path": file, "content": content})

        # Step 7: Update state and log
        state['relevant_files'] = relevant_files_data
        self.logger.info(f"Found {len(relevant_files_data)} relevant files: {[f['file_path'] for f in relevant_files_data]}")
        return state
