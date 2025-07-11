# code_integrator_agent.py
import os
import logging
import re
import json
from typing import Dict, Any
from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags, log_info

class CodeIntegratorAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__("CodeIntegrator")
        self.project_root = os.getenv('PROJECT_ROOT', '/project')
        self.code_ext = os.getenv('CODE_FILE_EXTENSION', '.ts')
        self.test_ext = os.getenv('TEST_FILE_EXTENSION', '.test.ts')
        self.llm = llm_client
        self.max_reflect = 2  # Added
        self.logger.setLevel(logging.INFO)

    def integrate_code_with_llm(self, existing_content: str, new_code: str) -> str:
        prompt = (
            "/think\n"
            f"Integrate new code into existing: {existing_content}\n"
            "New: {new_code}\n"
            "Add to TimestampPlugin. Preserve existing. Only new used imports. No alterations.\n"
            "Output full updated code only."
        )
        response = self.llm.invoke(prompt)
        integrated = remove_thinking_tags(response).strip()

        # Reflection
        for _ in range(self.max_reflect):
            fixed = self.reflect_and_fix(integrated, existing_content, new_code, is_code=True)
            if fixed == integrated:
                break
            integrated = fixed
        return integrated

    def reflect_and_fix(self, integrated: str, existing: str, new: str, is_code: bool) -> str:
        type_str = "code" if is_code else "tests"
        prompt = (
            "/think\n"
            f"Verify integrated {type_str}: Preserves all existing, adds new correctly, no hallucinations.\n"
            f"Existing: {existing}\nNew: {new}\n"
            "Fix if needed. Output only fixed full {type_str}."
        )
        response = self.llm.invoke(prompt + f"\nIntegrated: {integrated}")
        return remove_thinking_tags(response).strip()

    def integrate_tests_manually(self, existing_content: str, new_tests: str) -> str:
        existing_lines = existing_content.split('\n')
        new_test_lines = [line for line in new_tests.split('\n') if 'typescript' not in line.lower() and 'javascript' not in line.lower()]

        new_imports = [line for line in new_test_lines if line.strip().startswith('import')]
        import_end_idx = 0
        for i, line in enumerate(existing_lines):
            if not line.strip().startswith('import') and line.strip():
                import_end_idx = i
                break

        existing_imports_set = set(line.strip() for line in existing_lines[:import_end_idx] if line.strip().startswith('import'))
        unique_new_imports = [imp for imp in new_imports if imp.strip() not in existing_imports_set]

        if unique_new_imports:
            existing_lines = existing_lines[:import_end_idx] + unique_new_imports + [''] + existing_lines[import_end_idx:]

        describe_start_idx = -1
        for i, line in enumerate(existing_lines):
            if line.strip().startswith("describe('TimestampPlugin',"):
                describe_start_idx = i
                break
        if describe_start_idx == -1:
            raise ValueError("Could not find describe('TimestampPlugin', block")

        insert_idx = describe_start_idx + 1
        while insert_idx < len(existing_lines) and not existing_lines[insert_idx].strip():
            insert_idx += 1

        describe_blocks = [line for line in new_test_lines if not line.strip().startswith('import')]
        if describe_blocks:
            indented_describe_blocks = ['    ' + line for line in describe_blocks]
            existing_lines = existing_lines[:insert_idx] + indented_describe_blocks + [''] + existing_lines[insert_idx:]

        updated_content = '\n'.join(existing_lines)  # After manual insert

        # Reflection for tests
        for _ in range(self.max_reflect):
            fixed = self.reflect_and_fix(updated_content, existing_content, new_tests, is_code=False)
            if fixed == updated_content:
                break
            updated_content = fixed
        return updated_content

    def generate_filename(self, task_description: str, task_title: str) -> str:
        sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', task_title).lower()
        return sanitized_title.split('_')[0] or "newFeature"

    def process(self, state: State) -> State:
        task_details = state['result']
        relevant_code_files = state.get('relevant_code_files', [])
        relevant_test_files = state.get('relevant_test_files', [])

        code_content = state['generated_code']
        test_content = state['generated_tests']

        if relevant_code_files or relevant_test_files:
            for file_data in relevant_code_files:
                abs_file_path = os.path.join(self.project_root, file_data['file_path'])
                existing_content = file_data['content']
                updated_content = self.integrate_code_with_llm(existing_content, code_content)
                with open(abs_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            for file_data in relevant_test_files:
                abs_file_path = os.path.join(self.project_root, file_data['file_path'])
                existing_content = file_data['content']
                updated_content = self.integrate_tests_manually(existing_content, test_content)
                with open(abs_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
        else:
            task_description = task_details['description']
            task_title = task_details['title']
            filename = self.generate_filename(task_description, task_title)

            new_code_file = os.path.join(self.project_root, 'src', f"{filename}{self.code_ext}")
            new_test_file = os.path.join(self.project_root, 'src', '__tests__', f"{filename}{self.test_ext}")

            os.makedirs(os.path.dirname(new_code_file), exist_ok=True)
            with open(new_code_file, 'w', encoding='utf-8') as f:
                f.write(code_content)
            with open(new_test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)

            state['relevant_code_files'] = [{"file_path": os.path.relpath(new_code_file, self.project_root), "content": code_content}]
            state['relevant_test_files'] = [{"file_path": os.path.relpath(new_test_file, self.project_root), "content": test_content}]

        return state
