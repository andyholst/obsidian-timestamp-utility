"""
Combined agents for ultra-fast E2E testing.

These agents combine multiple workflow steps into a single LLM call,
reducing the total number of LLM calls from 5 to 2:
  1. CombinedClarifyPlanAgent: ticket_clarity + implementation_planner (1 LLM call)
  2. CombinedExtractGenerateAgent: code_extractor + collaborative_generator (1 LLM call)

This reduces LLM inference time from ~15-40 seconds to ~6-16 seconds per workflow.
"""
import json
import logging
import os
import re
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent
from .state import State, CodeGenerationState
from .utils import safe_json_dumps, remove_thinking_tags, log_info, parse_json_response
from .circuit_breaker import get_circuit_breaker
from .monitoring import structured_log


class CombinedClarifyPlanAgent(BaseAgent):
    """
    Combines TicketClarityAgent and ImplementationPlannerAgent into a single LLM call.
    
    Takes raw ticket content and produces an enhanced ticket with:
    - Refined requirements
    - Implementation plan
    - NPM dependencies
    - Affected files
    """

    def __init__(self, llm_client):
        super().__init__("CombinedClarifyPlan")
        self.llm = llm_client
        self.monitor.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        log_info(self.name, "Starting combined clarify+plan process")
        ticket_content = state.get("ticket_content", "")

        # Single LLM call that does both clarity and planning
        prompt = self._build_prompt(ticket_content)
        response = self._call_llm_with_retry(prompt)
        enhanced_ticket = self._parse_response(response, ticket_content)

        new_state = dict(state)
        new_state["refined_ticket"] = enhanced_ticket
        new_state["refined_ticket"]["full_original_content"] = ticket_content

        requirements_len = len(enhanced_ticket.get("requirements", []))
        log_info(self.name, f"Combined clarify+plan complete. Requirements: {requirements_len}")
        return new_state

    def _build_prompt(self, ticket_content: str) -> str:
        return f"""You are an expert TypeScript developer working on an Obsidian plugin.

Analyze the following GitHub issue and produce a structured implementation plan.

## GitHub Issue Content:
{ticket_content}

## Your Task:
1. Extract and refine the requirements from the issue
2. Create a step-by-step implementation plan
3. Identify any NPM dependencies needed
4. Identify which existing files will be affected

## Output Format (JSON only, no markdown):
{{
  "requirements": [
    "Requirement 1: detailed description",
    "Requirement 2: detailed description"
  ],
  "implementation_steps": [
    "Step 1: what to do",
    "Step 2: what to do"
  ],
  "npm_packages": ["package1", "package2"],
  "affected_files": ["src/main.ts"],
  "feature_type": "new_command|modal|setting|other",
  "complexity": "low|medium|high"
}}

Respond ONLY with valid JSON. No explanations, no markdown.
"""

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        for attempt in range(max_retries):
            try:
                cb = get_circuit_breaker(self.name)
                response = cb.call(self.llm.invoke, prompt)
                return response
            except Exception as e:
                log_info(self.name, f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        return ""

    def _parse_response(self, response: str, original_content: str) -> Dict:
        # Try to extract JSON from the response
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            parsed = json.loads(cleaned.strip())
            # Ensure required fields exist
            parsed.setdefault("requirements", [])
            parsed.setdefault("implementation_steps", [])
            parsed.setdefault("npm_packages", [])
            parsed.setdefault("affected_files", ["src/main.ts"])
            parsed.setdefault("feature_type", "other")
            parsed.setdefault("complexity", "medium")
            return parsed
        except (json.JSONDecodeError, IndexError) as e:
            log_info(self.name, f"Failed to parse LLM response as JSON: {e}")
            # Fallback: extract requirements from plain text
            return self._fallback_parse(response, original_content)

    def _fallback_parse(self, response: str, original_content: str) -> Dict:
        """Fallback parser that extracts requirements from plain text."""
        # Split by numbered lines or bullet points
        lines = response.split("\n")
        requirements = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                cleaned = re.sub(r'^[\d\-\*\.\s]+', '', line).strip()
                if cleaned and len(cleaned) > 10:
                    requirements.append(cleaned)

        if not requirements:
            # Last resort: use the original content
            requirements = [f"Implement the feature described in the issue"]

        return {
            "requirements": requirements[:10],
            "implementation_steps": requirements[:5],
            "npm_packages": [],
            "affected_files": ["src/main.ts"],
            "feature_type": "other",
            "complexity": "medium",
        }


class CombinedExtractGenerateAgent(BaseAgent):
    """
    Combines CodeExtractorAgent and CollaborativeGenerator into a single LLM call.
    
    Takes the enhanced ticket and existing code, then generates:
    - TypeScript code for the new feature
    - TypeScript tests for the new feature
    - Integration instructions
    
    All in ONE LLM call instead of separate extract + generate + test calls.
    """

    def __init__(self, llm_client):
        super().__init__("CombinedExtractGenerate")
        self.llm = llm_client
        self.project_root = os.getenv("PROJECT_ROOT", "/tmp/obsidian-project")
        self.monitor.setLevel(logging.INFO)

    def process(self, state: Dict) -> Dict:
        log_info(self.name, "Starting combined extract+generate process")

        refined_ticket = state.get("refined_ticket", {})
        existing_code = self._read_existing_code()

        # Single LLM call that does extraction + code generation + test generation
        prompt = self._build_prompt(refined_ticket, existing_code)
        response = self._call_llm_with_retry(prompt)

        # Parse the multi-section response
        code_output = self._parse_response(response)

        new_state = dict(state)
        new_state["generated_code"] = code_output.get("code", "")
        new_state["generated_tests"] = code_output.get("tests", "")
        new_state["integration_instructions"] = code_output.get("instructions", "")
        new_state["code_updated"] = bool(code_output.get("code", "").strip())

        log_info(self.name, f"Combined extract+generate complete. "
                 f"Code: {len(new_state['generated_code'])} chars, "
                 f"Tests: {len(new_state['generated_tests'])} chars")
        return new_state

    def _read_existing_code(self) -> str:
        """Read existing main.ts to provide context."""
        main_ts_path = os.path.join(self.project_root, "src/main.ts")
        try:
            if os.path.exists(main_ts_path):
                with open(main_ts_path, "r") as f:
                    return f.read()
        except Exception as e:
            log_info(self.name, f"Could not read existing code: {e}")
        return ""

    def _build_prompt(self, refined_ticket: Dict, existing_code: str) -> str:
        requirements = refined_ticket.get("requirements", [])
        steps = refined_ticket.get("implementation_steps", [])
        modules = ref_npm = refined_ticket.get("npm_packages", [])

        return f"""You are an expert TypeScript developer working on an Obsidian plugin.

Generate TypeScript code and tests for the following feature.

## Requirements:
{chr(10).join(f"- {r}" for r in requirements)}

## Implementation Steps:
{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(steps))}

## Existing Code (main.ts):
```typescript
{existing_code[:3000]}
```

## NPM Packages to Install (if any):
{chr(10).join(f"- {p}" for p in modules) if packages else "None needed"}

## Your Task:
Generate THREE sections:

### SECTION 1: TypeScript Code
Write ONLY the NEW code snippets to add to main.ts. Do NOT repeat existing code.
- Use proper TypeScript with type annotations
- Follow Obsidian plugin patterns (extend obsidian.Plugin, use onload(), addCommand())
- Ensure all code is syntactically valid TypeScript
- Do NOT use backticks in strings, use single quotes
- Do NOT modify existing code

### SECTION 2: TypeScript Tests
Write Jest tests for the NEW code using `import * as obsidian from 'obsidian'`.
- Use describe() and it() blocks
- Mock Obsidian APIs as needed
- Test the new functionality

### SECTION 3: Integration Instructions
Brief instructions on how to integrate the new code with existing code.

## Output Format:

=== CODE ===
```typescript
// New code here
```

=== TESTS ===
```typescript
// Test code here
```

=== INSTRUCTIONS ===
Step-by-step integration instructions.

Respond ONLY with the three sections clearly marked.
"""

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        for attempt in range(max_retries):
            try:
                cb = get_circuit_breaker(self.name)
                response = cb.call(self.llm.invoke, prompt)
                return response
            except Exception as e:
                log_info(self.name, f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        return ""

    def _parse_response(self, response: str) -> Dict:
        result = {"code": "", "tests": "", "instructions": ""}

        try:
            # Extract CODE section
            code_match = re.search(r'=== CODE ===\s*```(?:typescript|ts)?\s*(.*?)```', response, re.DOTALL)
            if code_match:
                result["code"] = code_match.group(1).strip()

            # Extract TESTS section
            tests_match = re.search(r'=== TESTS ===\s*```(?:typescript|ts)?\s*(.*?)```', response, re.DOTALL)
            if tests_match:
                result["tests"] = tests_match.group(1).strip()

            # Extract INSTRUCTIONS section
            instr_match = re.search(r'=== INSTRUCTIONS ===\s*(.*?)(?===|$)', response, re.DOTALL)
            if instr_match:
                result["instructions"] = instr_match.group(1).strip()

            # Fallback: if no sections found, try to extract any TypeScript code blocks
            if not result["code"]:
                code_blocks = re.findall(r'```(?:typescript|ts)\s*(.*?)```', response, re.DOTALL)
                if code_blocks:
                    result["code"] = code_blocks[0].strip()
                if len(code_blocks) > 1:
                    result["tests"] = code_blocks[1].strip()

        except Exception as e:
            log_info(self.name, f"Error parsing response: {e}")
            result["code"] = response  # Fallback: use entire response as code

        return result
