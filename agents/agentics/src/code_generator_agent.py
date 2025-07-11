# code_generator_agent.py
import logging
import json
import re
import os
from typing import List, Dict
from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags, log_info
from .import_utils import filter_imports

class CodeGeneratorAgent(BaseAgent):
    def __init__(self, llm_client, knowledge: Dict[str, str]):
        super().__init__("CodeGenerator")
        self.llm = llm_client
        self.knowledge = knowledge  # Pseudo-RAG knowledge
        self.main_file = os.getenv('MAIN_FILE', 'main.ts')
        self.test_file = os.getenv('TEST_FILE', 'main.test.ts')
        self.max_reflect = 2  # Reflection loops
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with main file: {self.main_file}, test file: {self.test_file}")

    def reflect_and_fix(self, generated: str, task_details_str: str, is_code: bool = True) -> str:
        type_str = "code" if is_code else "tests"
        prompt = (
            "/think\n"
            f"Verify this {type_str} against task: {task_details_str}\n"
            f"Knowledge: {self.knowledge.get('uuid_v7_spec', '')}\n"
            "Fix errors/hallucinations. Output only fixed version if needed, else original."
        )
        response = self.llm.invoke(prompt + f"\n{type_str.capitalize()}: {generated}")
        return remove_thinking_tags(response).strip()

    def generate_code_prompt(self, task_details_str: str, existing_code_content: str) -> str:
        knowledge_snippet = self.knowledge.get('uuid_v7_spec', '') + "\n" + self.knowledge.get('obsidian_add_command_example', '')
        return (
            "/think\n"
            f"Generate TypeScript code for Obsidian plugin in {self.main_file}. Integrate into TimestampPlugin class without altering existing code.\n"
            "Add public method from task title. Add command in onload.\n"
            "Reuse imports. Add only used new imports. Stick to facts; no assumptions.\n"
            f"Knowledge: {knowledge_snippet}\n"
            "Task: {task_details_str}\n"
            "Existing: {existing_code_content}\n"
            "Output only new code starting with imports, no extras."
        ) if existing_code_content else (
            "/think\n"
            f"Generate TypeScript for task. Define TimestampPlugin extending obsidian.Plugin.\n"
            "Public method from title. Command in onload.\n"
            "Only used imports. Stick to facts; no assumptions.\n"
            f"Knowledge: {knowledge_snippet}\n"
            "Task: {task_details_str}\n"
            "Output raw code only."
        )

    def generate_test_prompt(self, method_name: str, command_id: str, task_details_str: str, filtered_code: str, existing_test_content: str) -> str:
        knowledge_snippet = self.knowledge.get('uuid_v7_spec', '')
        return (
            "/think\n"
            f"Generate Jest tests for {method_name} and {command_id} in {self.test_file}.\n"
            "Two describe blocks: method and command.\n"
            "Match existing style. No new imports. Stick to facts; no assumptions.\n"
            f"Knowledge: {knowledge_snippet}\n"
            "Task: {task_details_str}\n"
            "Code: {filtered_code}\n"
            "Existing: {existing_test_content}\n"
            "Output only describe blocks, indented 4 spaces."
        ) if existing_test_content else (
            "/think\n"
            f"Generate two describe blocks for {method_name} and {command_id}.\n"
            "Method: plugin.{method_name}(). Command: mockCommands['{command_id}'].callback().\n"
            f"Knowledge: {knowledge_snippet}\n"
            "Task: {task_details_str}\n"
            "Code: {filtered_code}\n"
            "Output only describe blocks, indented 4 spaces."
        )

    def process(self, state: State) -> State:
        task_details = state['result']
        relevant_code_files = state.get('relevant_code_files', [])
        relevant_test_files = state.get('relevant_test_files', [])
        title = task_details['title']
        description = task_details['description']
        requirements = ', '.join(task_details['requirements'])
        acceptance_criteria = ', '.join(task_details['acceptance_criteria'])
        task_details_str = f"Title: {title}\nDesc: {description}\nReq: {requirements}\nAC: {acceptance_criteria}"

        existing_code_content = ""
        for code_file in relevant_code_files:
            if code_file['file_path'].endswith(self.main_file):
                existing_code_content = code_file.get('content', "")
                break

        code_prompt = self.generate_code_prompt(task_details_str, existing_code_content)
        generated_code = remove_thinking_tags(self.llm.invoke(code_prompt)).strip()

        # Self-reflection loop for code
        for _ in range(self.max_reflect):
            fixed = self.reflect_and_fix(generated_code, task_details_str)
            if fixed == generated_code:
                break
            generated_code = fixed

        filtered_code, new_modules = filter_imports(generated_code)
        state['generated_code'] = filtered_code
        state['new_modules'] = new_modules

        method_match = re.search(r'(public|private|protected)?\s*(\w+)\s*\(', filtered_code)
        method_name = method_match.group(2) if method_match else "defaultMethod"

        command_match = re.search(r'this\.addCommand\(\{\s*id:\s*["\']([^"\']+)["\']', filtered_code)
        command_id = command_match.group(1) if command_match else "defaultCommand"

        existing_test_content = ""
        for test_file in relevant_test_files:
            if test_file['file_path'].endswith(self.test_file):
                existing_test_content = test_file.get('content', "")
                break

        test_prompt = self.generate_test_prompt(method_name, command_id, task_details_str, filtered_code, existing_test_content)
        generated_tests = remove_thinking_tags(self.llm.invoke(test_prompt)).strip()

        # Self-reflection loop for tests
        for _ in range(self.max_reflect):
            fixed = self.reflect_and_fix(generated_tests, task_details_str, is_code=False)
            if fixed == generated_tests:
                break
            generated_tests = fixed

        state['generated_tests'] = generated_tests
        return state
