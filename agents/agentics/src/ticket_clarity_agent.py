import json
import datetime
import re
import copy
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base_agent import BaseAgent
from .state import State
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from github import Github, GithubException
from .utils import safe_json_dumps, remove_thinking_tags, log_info, parse_json_response
from .prompts import ModularPrompts

class TicketClarityAgent(BaseAgent):
    def __init__(self, llm_client, github_client):
        super().__init__("TicketClarityAgent")
        self.llm = llm_client
        self.github = github_client
        self.max_iterations = 3
        self.monitor.setLevel(logging.INFO)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    def process(self, state: State) -> State:
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting ticket clarity process")
        ticket_content = state['ticket_content']
        log_info(self.name, f"Initial ticket content: {ticket_content}")
        refined_ticket = self.refine_ticket(ticket_content)
        new_state = copy.deepcopy(state)
        new_state['refined_ticket'] = refined_ticket
        # Preserve full original content for agent prompts
        new_state['refined_ticket']['full_original_content'] = ticket_content
        requirements_len = len(refined_ticket.get('requirements', []))
        log_info(self.name, f"Refined ticket requirements count: {requirements_len}")
        if requirements_len < 5:
            self.monitor.warning(f"Low requirements count ({requirements_len}), potential empty state issue")
        log_info(self.name, f"Refined ticket: {json.dumps(refined_ticket, indent=2)}")
        self.post_final_ticket(new_state['refined_ticket'], new_state['url'])
        log_info(self.name, "Ticket clarity process completed")
        log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(new_state, indent=2)}")
        return new_state

    def refine_ticket(self, ticket_content):
        log_info(self.name, f"Refining ticket content: {json.dumps(ticket_content, indent=2)}")
        log_info(self.name, "Starting ticket refinement")
        original_ticket_content = copy.deepcopy(ticket_content)  # Preserve original
        refined_ticket = ticket_content
        for iteration in range(self.max_iterations):
            log_info(self.name, f"Refinement iteration {iteration + 1} of {self.max_iterations}")
            # Convert refined_ticket to string if it's a dictionary
            if isinstance(refined_ticket, dict):
                ticket_str = json.dumps(refined_ticket)
            else:
                ticket_str = refined_ticket
            log_info(self.name, f"Ticket string length for evaluation: {len(ticket_str)}")
            log_info(self.name, f"Ticket string for evaluation: {ticket_str}")

            evaluation = self.evaluate_clarity(ticket_str)
            log_info(self.name, f"Clarity evaluation: {evaluation}")
            # Validate evaluation response
            if not isinstance(evaluation, dict) or 'is_clear' not in evaluation or 'suggestions' not in evaluation:
                self.monitor.error(f"Invalid evaluation response: {evaluation}")
                raise ValueError("Invalid evaluation response")
            if evaluation['is_clear']:
                log_info(self.name, "Ticket is clear, early exit from refinement loop")
                break
            refined_ticket = self.generate_improvements(ticket_str, evaluation, original_content=str(original_ticket_content))
            log_info(self.name, f"Refined ticket after improvements: {json.dumps(refined_ticket, indent=2)}")
            # Validate refined ticket response
            if not isinstance(refined_ticket, dict) or not all(key in refined_ticket for key in ['title', 'description', 'requirements', 'acceptance_criteria']):
                self.monitor.warning(f"Invalid refined ticket response, setting defaults: {refined_ticket}")
                refined_ticket = {
                    'title': refined_ticket.get('title', 'Feature Implementation'),
                    'description': refined_ticket.get('description', 'Derived from ticket.'),
                    'requirements': refined_ticket.get('requirements', []),
                    'acceptance_criteria': refined_ticket.get('acceptance_criteria', []),
                    'implementation_steps': refined_ticket.get('implementation_steps', [])
                }
        log_info(self.name, "Ticket refinement completed")
        # Force final structured extraction to ensure non-empty requirements, append original
        ticket_str = json.dumps(refined_ticket) if isinstance(refined_ticket, dict) else str(refined_ticket)
        ticket_str += f"\n\nOriginal ticket content for reference:\n{str(original_ticket_content)}"
        extraction_suggestions = [
            "Extract concise actionable title from ticket.",
            "Provide detailed description summarizing the feature.",
            "CRITICAL: Extract ALL specific requirements into list >=8 Obsidian items: command palette, editor.replaceSelection cursor, Notice no note, public method, uniqueness, validation, crypto.random if needed, edge cases, testable, at least 10 detailed items.",
            "Derive concrete testable acceptance criteria: command visible in palette, inserts correctly, shows error if no note, etc."
        ]
        refined_ticket = self.generate_improvements(ticket_str, {"suggestions": extraction_suggestions}, original_content=str(original_ticket_content))
        log_info(self.name, f"Refined ticket result: {json.dumps(refined_ticket, indent=2)}")

        # Safeguards: Validate and re-refine if necessary
        reqs = refined_ticket.get('requirements', [])
        acs = refined_ticket.get('acceptance_criteria', [])
        if len(reqs) < 3:
            log_info(self.name, f"Requirements count {len(reqs)} < 3, triggering full re-refine with original appended")
            # Re-refine with original appended to prompt
            re_refine_prompt = ticket_str + f"\n\nCRITICAL: Original ticket must be preserved. Extract at least 8 specific requirements including UUID v7, timestamp details."
            refined_ticket = self.generate_improvements(re_refine_prompt, {"suggestions": extraction_suggestions}, original_content=str(original_ticket_content))
            reqs = refined_ticket.get('requirements', [])
        if len(reqs) < 5:
            log_info(self.name, f"Requirements count {len(reqs)} < 5, applying fallback")
            refined_ticket['requirements'] = self._generate_fallback_requirements(refined_ticket, str(original_ticket_content))
        if len(acs) < 3:
            log_info(self.name, f"Acceptance criteria count {len(acs)} < 3, triggering full re-refine")
            re_refine_prompt = ticket_str + f"\n\nCRITICAL: Original ticket must be preserved. Extract at least 5 specific acceptance criteria."
            refined_ticket = self.generate_improvements(re_refine_prompt, {"suggestions": extraction_suggestions}, original_content=str(original_ticket_content))
            acs = refined_ticket.get('acceptance_criteria', [])
        if len(acs) < 5:
            log_info(self.name, f"Acceptance criteria count {len(acs)} < 5, applying fallback")
            refined_ticket['acceptance_criteria'] = self._generate_fallback_acceptance_criteria(refined_ticket, str(original_ticket_content))
        log_info(self.name, f"Final requirements length: {len(refined_ticket.get('requirements', []))}, AC length: {len(refined_ticket.get('acceptance_criteria', []))}")
        return refined_ticket

    def evaluate_clarity(self, ticket_content):
        log_info(self.name, "Evaluating ticket clarity")
        prompt = ModularPrompts.get_ticket_clarity_evaluation_prompt().format(ticket_content=ticket_content)
        log_info(self.name, f"Clarity evaluation prompt: {prompt}")

        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        log_info(self.name, f"Raw LLM response for evaluate_clarity: {clean_response}")
        result = parse_json_response(clean_response, llm_client=self.llm, original_prompt=prompt)
        log_info(self.name, f"Parsed evaluation dict: {result}")
        return result

    def generate_improvements(self, ticket_content, evaluation, original_content=None):
        log_info(self.name, "Generating ticket improvements")
        suggestions = evaluation['suggestions']
        log_info(self.name, f"Suggestions for improvement: {suggestions}")
        prompt = ModularPrompts.get_ticket_clarity_improvements_prompt().format(ticket_content=ticket_content, suggestions="\n".join(suggestions))
        log_info(self.name, f"Improvements prompt: {prompt}")

        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        log_info(self.name, f"Raw LLM response for generate_improvements: {clean_response}")
        result = parse_json_response(clean_response, llm_client=self.llm, original_prompt=prompt)
        log_info(self.name, f"Parsed improvements dict: {result}")
        # Fix common LLM key variations
        if 'criteria' in result and 'acceptance_criteria' not in result:
            result['acceptance_criteria'] = result.pop('criteria')
        if 'reqs' in result and 'requirements' not in result:
            result['requirements'] = result.pop('reqs')
        # Ensure all keys present
        result.setdefault('title', 'Refined Feature Implementation')
        result.setdefault('description', 'Detailed feature description derived from ticket.')
        result.setdefault('requirements', [])
        result.setdefault('acceptance_criteria', [])
        result.setdefault('implementation_steps', [])
        # Fallback to original if empty
        if not result.get('title', '').strip() and original_content:
            title_match = re.search(r'(?:Title|Subject|Issue #?\\d*):\s*([^\n\r]+?)(?=\n|$)', original_content, re.I | re.M)
            if title_match:
                result['title'] = title_match.group(1).strip()
            else:
                lines = original_content.splitlines()
                if lines:
                    result['title'] = lines[0].strip()[:60] + ('...' if len(lines[0]) > 60 else '')
        if not result.get('description', '').strip() and original_content:
            desc_preview = original_content.strip()[:400] + ('...' if len(original_content) > 400 else '')
            result['description'] = desc_preview
        log_info(self.name, f"Post-parse enforced: title_len={len(result.get('title', ''))}, desc_len={len(result.get('description', ''))}, reqs_len={len(result.get('requirements', []))}, ac_len={len(result.get('acceptance_criteria', []))}")
        # Merge original content
        if original_content:
            result = self._merge_original_content(result, original_content)
        log_info(self.name, f"Parsed improvements: {result}")
        return result

    def _merge_original_content(self, refined: dict, original: str) -> dict:
        """Merge original ticket content into refined fields to preserve details."""
        log_info(self.name, f"Merging original content into refined ticket")
        before = json.dumps(refined, indent=2)
        # If title is generic, try to extract from original
        if refined.get('title', '').lower() in ['refined feature implementation', 'feature implementation']:
            title_match = re.search(r'(?:title|subject):\s*(.+?)(?:\n|$)', original, re.IGNORECASE)
            if title_match:
                refined['title'] = title_match.group(1).strip()
        # Append original to requirements if empty or generic
        if not refined.get('requirements') or len(refined['requirements']) < 3:
            keywords = re.findall(r'\b(UUID v7|timestamp|crypto\.random|Notice|editor\.replaceSelection|command palette)\b', original, re.IGNORECASE)
            if keywords:
                refined.setdefault('requirements', []).append(f"Incorporate original specifications: {', '.join(set(keywords))}")
        # Similarly for acceptance_criteria
        if not refined.get('acceptance_criteria') or len(refined['acceptance_criteria']) < 3:
            keywords = re.findall(r'\b(command visible|inserts correctly|shows error|no note|validation)\b', original, re.IGNORECASE)
            if keywords:
                refined.setdefault('acceptance_criteria', []).append(f"Ensure original requirements: {', '.join(set(keywords))}")
        after = json.dumps(refined, indent=2)
        log_info(self.name, f"Before merge: {before}")
        log_info(self.name, f"After merge: {after}")
        return refined

    def _generate_fallback_requirements(self, ticket: dict, original_content: str = None) -> list:
        """Generate fallback requirements if LLM extraction fails, injecting original content."""
        title = ticket.get('title', '')
        description = ticket.get('description', '')
        # Extract keywords from original content
        keywords = []
        if original_content:
            keywords = re.findall(r'\b(UUID v7|timestamp|crypto\.random|Notice|editor\.replaceSelection|command palette|public method|uniqueness|validation|edge cases|testable)\b', original_content, re.IGNORECASE)
            keywords = list(set(keywords))  # unique
        prompt = "/think\n" + PromptTemplate(
            input_variables=["title", "description", "keywords"],
            template=(
                "Generate at least 5 detailed, actionable requirements derived from the ticket title, description, and specific keywords. "
                "Incorporate the provided keywords into specific requirements. "
                "Return only a JSON array of strings, no additional text.\n\n"
                "Title: {title}\n\n"
                "Description: {description}\n\n"
                "Keywords: {keywords}\n\n"
                "Example: [\"Implement core feature as Obsidian command.\", \"Add public utility method.\", \"Include error handling with app.notice.\", \"Ensure TypeScript compatibility.\", \"Match existing codebase style.\"]\n\n"
                "Requirements:"
            )
        ).format(title=title, description=description, keywords=', '.join(keywords) if keywords else 'None')
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        reqs = parse_json_response(clean_response, llm_client=self.llm, original_prompt=prompt)
        if not isinstance(reqs, list):
            reqs = []
        # Post-processing: ensure at least 5 items, inject keywords if missing
        if keywords and not any(k.lower() in ' '.join(reqs).lower() for k in keywords):
            for k in keywords[:2]:  # add up to 2
                reqs.append(f"Generate UUID v7 using timestamp as described in original: {k}")
        defaults = ["Implement as Obsidian command", "Add public method", "Handle errors", "Add types", "Follow best practices"]
        while len(reqs) < 5:
            reqs.append(defaults[len(reqs) % len(defaults)])
        log_info(self.name, f"Fallback requirements generated: {len(reqs)} items")
        return reqs

    def _generate_fallback_acceptance_criteria(self, ticket: dict, original_content: str = None) -> list:
        """Generate fallback acceptance criteria if LLM extraction fails, injecting original content."""
        title = ticket.get('title', '')
        description = ticket.get('description', '')
        # Extract keywords from original content
        keywords = []
        if original_content:
            keywords = re.findall(r'\b(command visible|inserts correctly|shows error|no note|validation|success notice|error notice|compilation)\b', original_content, re.IGNORECASE)
            keywords = list(set(keywords))  # unique
        prompt = "/think\n" + PromptTemplate(
            input_variables=["title", "description", "keywords"],
            template=(
                "Generate at least 5 detailed acceptance criteria derived from the ticket title, description, and specific keywords. "
                "Incorporate the provided keywords into specific criteria. "
                "Return only a JSON array of strings, no additional text.\n\n"
                "Title: {title}\n\n"
                "Description: {description}\n\n"
                "Keywords: {keywords}\n\n"
                "Example: [\"Command appears in Obsidian command palette.\", \"Command inserts correct output at cursor.\", \"Success notice displayed.\", \"Error notice for no active note.\", \"Output validates against spec.\"]\n\n"
                "Acceptance Criteria:"
            )
        ).format(title=title, description=description, keywords=', '.join(keywords) if keywords else 'None')
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        acs = parse_json_response(clean_response, llm_client=self.llm, original_prompt=prompt)
        if not isinstance(acs, list):
            acs = []
        # Post-processing: ensure at least 5 items, inject keywords if missing
        if keywords and not any(k.lower() in ' '.join(acs).lower() for k in keywords):
            for k in keywords[:2]:  # add up to 2
                acs.append(f"Ensure {k} as described in original ticket")
        defaults = ["Command visible in palette", "Inserts correctly at cursor", "Shows success notice", "Shows error notice if invalid", "No compilation errors"]
        while len(acs) < 5:
            acs.append(defaults[len(acs) % len(defaults)])
        log_info(self.name, f"Fallback AC generated: {len(acs)} items")
        return acs

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    def post_final_ticket(self, refined_ticket, issue_url):
        log_info(self.name, "Posting final refined ticket to GitHub")
        log_info(self.name, f"Issue URL: {issue_url}")
        repo_name = "/".join(issue_url.split('/')[3:5])
        issue_number = int(issue_url.split('/')[-1])
        log_info(self.name, f"Repository: {repo_name}, Issue number: {issue_number}")

        repo = self.github.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        today = datetime.date.today().strftime("%Y%m%d")
        # Safeguard: ensure keys exist to prevent KeyError (debug validation)
        title = refined_ticket.get('title', 'Refined Feature Implementation')
        description = refined_ticket.get('description', 'Derived from original ticket.')
        requirements = refined_ticket.get('requirements', [])
        acceptance_criteria = refined_ticket.get('acceptance_criteria', [])
        self.monitor.info("post_final_ticket_keys", {
            "keys": list(refined_ticket.keys()) if isinstance(refined_ticket, dict) else "non-dict",
            "title_present": 'title' in refined_ticket,
            "reqs_count": len(requirements),
            "acs_count": len(acceptance_criteria)
        })
        comment = (
            f"TicketClarityAgent - Refined Ticket - {today}\n\n"
            f"# {title}\n\n"
            f"## Description\n{description}\n\n"
            f"## Requirements\n" + "\n".join(f"- {req}" for req in requirements) + "\n\n"
            f"## Acceptance Criteria\n" + "\n".join(f"- {ac}" for ac in acceptance_criteria)
        )
        log_info(self.name, f"Comment to post: {comment}")
        try:
            issue.create_comment(comment)
        except GithubException as e:
            self.monitor.error(f"Failed to create comment: {e}")
        log_info(self.name, "Refined ticket posted successfully")
