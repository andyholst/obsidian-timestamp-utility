import logging
import json
from .utils import log_info

class ModularPrompts:
    """Modular prompt components following LangChain best practices."""

    @staticmethod
    def get_base_instruction():
        return (
            "You are an expert TypeScript developer specializing in Obsidian plugins. CRITICAL: You MUST implement ONLY the exact functionality described in the Task Details section below. Do NOT implement any unrelated functionality, such as swapCase, string reversal, or any other features unless explicitly requested in the task details. CRITICAL: Do NOT modify, delete, or fiddle with any existing code or tests. Generate and output ONLY brand new code and test additions strictly for the specified feature. Existing code and tests shall remain untouched. "
            "Use proper TypeScript syntax: include type annotations, interfaces, and classes. Follow Obsidian plugin patterns: extend obsidian.Plugin, use onload() for commands with this.addCommand(), handle editor content with editor.replaceSelection() for insertion at cursor, and ensure all code is syntactically valid TypeScript. "
            "Respond ONLY with valid code, no explanations, no markdown, no thinking content. "
            "IMPORTANT: Follow the exact requirements and implementation steps specified in the task details - do not deviate or add extra features."
            "CRITICAL: Use correct Obsidian API calls:\n"
            "- Get active editor: const view = this.app.workspace.getActiveViewOfType(obsidian.MarkdownView); if (!view) { new obsidian.Notice('No active note.'); return; } const editor = view.editor;\n"
            "- Insert at cursor: editor.replaceSelection;\n"
            "- Show message: new obsidian.Notice('message');\n"
            "- Do not use getActiveTextEditor, App.instance, setValue for insertion, createErrorModal;\n"
            "- NEVER redefine full class or onload(). Provide ONLY insertable snippets. Match EXACTLY existing patterns from examples below.\n"
            "CRITICAL: TS strings use '; no ` backticks except template literals.\n\n"
        )

    @staticmethod
    def get_code_structure_section(code_structure: str):
        return f"1. **Existing Code Structure:**\n - Classes: {code_structure}\n - The plugin class extends `obsidian.Plugin`.\n - Commands are added in the `onload` method using `this.addCommand`.\n - Helper functions and modals may be defined outside the class.\n\n"

    @staticmethod
    def get_code_requirements_section(raw_refined_ticket: str = "", original_ticket_content: str = ""):
        base = (
            "2. **New Code Requirements:**\n"
            " - Add a new public method to the plugin class with a name derived from the task title.\n"
            " - The method should have the signature: public {method_name}(): string if no input param needed (e.g., generators). Otherwise public {method_name}(text?: string): string\n"
            " - Implement the method to process the text according to the task details, following the implementation steps, using the suggested npm packages, or implementing manually as noted. Handle null and undefined inputs by returning an empty string.\n"
            " - Ensure the method is public and does not use `private` or `protected` keywords.\n"
            " - Add new command in `onload()` matching task:\n  - Insert/gen tasks: `this.addCommand({ id: '{command_id}', editorCallback: (editor: obsidian.Editor, ctx: MarkdownView | MarkdownFileInfo) => { editor.replaceSelection(this.{method_name}()); new obsidian.Notice('Done'); } })`\n  - Rename/file tasks: `this.addCommand({ id: '{command_id}', callback: () => { const file = this.app.workspace.getActiveFile(); if (!file) { new obsidian.Notice('No file'); return; } const p = file.parent!.path; this.app.fileManager.renameFile(file, `${p}/${this.{method_name}()}_${file.basename}.${file.extension}`); } })`\n - Null guards: `file!.parent!.path` after check, `?.` chaining, `if (!obj) return;`.\n"
            " - Reuse existing imports (e.g., `import * as obsidian from 'obsidian';`).\n"
            " - If npm packages are suggested and available, add the necessary imports for them.\n"
            " - Do not redefine existing classes, interfaces, methods, or functions.\n"
            " - Do not add new imports, modals, or external dependencies unless specified in the npm packages and available.\n"
            " - You may include single-line comments (//) above new methods to describe their purpose, but do not add any other comments or explanations.\n"
            " - Keep the code simple and focused on the task; do not add complex features unless specified.\n"
            " - Before generating, proactively use validate_obsidian_api and validate_npm_package tools from api_validation_tools.py. If invalid, use alternatives like app.notice or manual DOM.\n"
            " - Ensure code satisfies all acceptance criteria exactly. If vague, default to basic command + method with app.workspace.currentFile notice.\n"
            " - If requirements or acceptance_criteria are empty or vague, derive 3-5 minimal actionable items from title and description (e.g., 'Implement as Obsidian command', 'Add public method with Notice placeholder', 'Handle basic errors', 'Add type annotations').\n"
        )
        if raw_refined_ticket:
            formatted_section = ModularPrompts.get_raw_refined_ticket_section().format(raw_refined_ticket=json.dumps(raw_refined_ticket, indent=2) if isinstance(raw_refined_ticket, dict) else raw_refined_ticket)
            base += f"\n\n{formatted_section}"
            log_info("ModularPrompts", f"Raw refined ticket section: {formatted_section}")
            log_info("ModularPrompts", f"Requirements from refined_ticket: {raw_refined_ticket.get('requirements', []) if isinstance(raw_refined_ticket, dict) else 'not dict'}")
            # Include full original content if preserved
            if 'full_original_content' in raw_refined_ticket:
                base += f"\n\nFull Original Ticket Content:\n{raw_refined_ticket['full_original_content']}"
        if original_ticket_content:
            base += f"\n\nOriginal ticket content for reference: {original_ticket_content}. Use this if refined fields are incomplete."
        return base

    @staticmethod
    def get_test_structure_section(test_structure: str):
        return (
            f"1. **Existing Test Structure:**\n"
            f" - Test structure: {test_structure}\n"
            " - The file contains a top-level `describe('TimestampPlugin', () => { ... })` block.\n"
            " - Inside this block, there are multiple `describe` blocks for different methods and commands.\n"
            " - Mocks are set up in a `beforeEach` block, including `mockEditor`, `mockApp`, `mockFile`, etc.\n"
            " - Commands are accessed via `mockCommands['<command-id>']` after `await plugin.onload()` is called.\n"
            " - `plugin` is an instance of the plugin class initialized in `beforeEach`.\n\n"
        )

    @staticmethod
    def get_test_requirements_section(raw_refined_ticket: str = "", original_ticket_content: str = ""):
        base = (
            "IMPORTANT: For generated tests, EXACTLY match existing test style in src/__tests__/*.test.ts:\n"
            "- Use global describe, it, expect, beforeEach WITHOUT any import from 'jest'.\n"
            "- Mock Obsidian using patterns from src/__mocks__/obsidian.ts.\n"
            "- Avoid obsidian.Manifest or undefined types; use 'any' or mock consistently.\n"
            "- Use jest.fn() for mocks where appropriate.\n\n"
            "2. **New Test Requirements:**\n"
            " - Analyze the Generated Code section to identify the exact method name and command id added.\n"
            " - Generate exactly two `describe` blocks:\n"
            " - One for the new method added to the plugin class (extract name from code like 'public methodName(): string').\n"
            " - One for the new command added via `this.addCommand` (extract id from code like 'id: \"command-id\"').\n"
            " - For the method test, call `plugin.methodName('test input')` to use the real implementation and check the result (e.g., expect it to return a string or call mockEditor).\n"
            " - For the command test, execute `mockCommands['command-id'].callback()` to trigger the command, which should call the method and interact with `mockEditor`.\n"
            " - Match the style of existing tests (e.g., async tests with `await plugin.onload()`, expect(mockEditor.replaceSelection).toHaveBeenCalledWith(result)).\n"
            " - Only generate tests for the new method and command identified in the Generated Code.\n"
            " - Do not access private methods or non-existent properties on the plugin.\n"
            " - Do not use jest.spyOn on plugin methods.\n"
            " - IMPORTANT: Do not use `plugin.commandIds` or any property access for command IDs; always use string literals like `'command-id'` in `mockCommands['command-id']`.\n"
            "- Use `new TimestampPlugin(mockApp, {} as any)` matching existing tests. Mock `obsidian.Editor` completely: define `mockEditor` with **all** methods from Obsidian Editor API as `jest.fn()` - see [`src/__tests__/main.test.ts`](src/__tests__/main.test.ts:14) for exact mock (getDoc, refresh, setValue, replaceSelection, getValue, getLine, lineCount, etc. all `jest.fn()` with appropriate mocks like getValue: jest.fn(() => "")). Use `button.onclick = () => {}` for modals (lowercase). Match **EXACTLY** the method and command names from the Generated Code section. Follow [`src/__mocks__/obsidian.ts`](src/__mocks__/obsidian.ts) for other mocks.\n"
             " - Tests must comprehensively cover code implementation. Ensure code satisfies all acceptance criteria exactly. If vague, default to basic command + method with app.workspace.currentFile notice.\n"
             " - If requirements or acceptance_criteria are empty or vague, derive 3-5 minimal actionable items from title and description (e.g., 'Implement as Obsidian command', 'Add public method with Notice placeholder', 'Handle basic errors', 'Add type annotations').\n\n"
            "Use precise syntax:\n"
            "const mockGetActiveView = app.workspace.getActiveViewOfType as jest.Mock;\n"
            "(app.workspace.getActiveViewOfType as jest.Mock).mockReturnValue(view);\n"
            "Always end statements with ';'.\n"
            "Emphasize strict TS/Jest syntax, no hallucinations.\n"
            "CRITICAL: Extract method name and command id directly from the Generated Code section - do not use placeholders or assumptions.\n"
        )
        if raw_refined_ticket:
            formatted_section = ModularPrompts.get_raw_refined_ticket_section().format(raw_refined_ticket=json.dumps(raw_refined_ticket, indent=2) if isinstance(raw_refined_ticket, dict) else raw_refined_ticket)
            base += f"\n\n{formatted_section}"
            log_info("ModularPrompts", f"Raw refined ticket section: {formatted_section}")
            log_info("ModularPrompts", f"Requirements from refined_ticket: {raw_refined_ticket.get('requirements', []) if isinstance(raw_refined_ticket, dict) else 'not dict'}")
            # Include full original content if preserved
            if 'full_original_content' in raw_refined_ticket:
                base += f"\n\nFull Original Ticket Content:\n{raw_refined_ticket['full_original_content']}"
        if original_ticket_content:
            base += f"\n\nOriginal ticket content for reference: {original_ticket_content}. Use this if refined fields are incomplete."
        return base

    @staticmethod
    def get_output_instructions_code():
        return (
            "6. **Output Instructions:**\n"
            " - Your response MUST be ONLY the new TypeScript code to be added to `{main_file}`.\n"
            " - Start directly with imports or code, end with code.\n"
            " - NO comments, explanations, markdown, or extra text.\n"
            " - MUST include at least one: import, export, class, interface, or function.\n"
            " - Code must be syntactically valid TypeScript."
        )

    @staticmethod
    def get_output_instructions_tests():
        return (
            "7. **Output Instructions:**\n"
            " - Output ONLY valid JSON: {\"tests\": \"describe block code here\"}\n"
            " - The 'tests' field must contain the complete Jest test code starting with 'describe(' and ending with '});'.\n"
            " - Include exactly two inner describe blocks for the method and command.\n"
            " - NO extra text, comments, or markdown outside the JSON.\n"
            " - MUST include 'describe(' and 'it(' or 'test(' keywords.\n"
            " - Valid Jest syntax only."
        )
    @staticmethod
    def get_raw_refined_ticket_section():
        return "**Full Raw Refined Ticket (JSON):**\n```json\n{raw_refined_ticket}\n```\n\n"

    @staticmethod
    def get_tool_instructions_for_code_extractor_agent():
        return (
            "7. **Available Tools:**\n"
            "You have access to the following tools to help extract and analyze code structure:\n\n"
            "- **read_file_tool**: Read the content of a file from the project root. Use this when you need to examine the content of specific files to understand their structure, classes, methods, or other code elements.\n"
            "- **list_files_tool**: List files and directories in a specified directory. Use this to explore the project structure and identify relevant files for analysis.\n"
            "- **check_file_exists_tool**: Check if a file exists at a given path. Use this to verify file availability before attempting to read or process them.\n\n"
            "**Tool Usage Guidelines:**\n"
            "- Use read_file_tool to analyze TypeScript files and extract code structures like classes, methods, interfaces, and functions.\n"
            "- Use list_files_tool to discover relevant files in the src/ and src/__tests__/ directories.\n"
            "- Use check_file_exists_tool to validate file paths before processing.\n"
            "- When extracting identifiers from tickets, use these tools to read relevant files and determine which ones contain matching code elements.\n"
            "- Always use tools proactively to gather complete context before making decisions about code relevance.\n\n"
        )

    @staticmethod
    def get_tool_instructions_for_code_integrator_agent():
        return (
            "7. **Available Tools:**\n"
            "You have access to the following tools to help integrate code and tests into project files:\n\n"
            "- **read_file_tool**: Read the content of a file from the project root. Use this to examine existing code and test files before integration.\n"
            "- **check_file_exists_tool**: Check if a file exists at a given path. Use this to verify file availability and determine whether to update existing files or create new ones.\n\n"
            "**Tool Usage Guidelines:**\n"
            "- Use read_file_tool to read existing main.ts and main.test.ts files to understand their current structure.\n"
            "- Use check_file_exists_tool to determine if relevant files exist before attempting integration.\n"
            "- When integrating code, always read the existing files first to ensure proper merging without overwriting existing functionality.\n"
            "- For new features, use tools to verify the project structure and create appropriately named files.\n\n"
        )

    @staticmethod
    def get_tool_instructions_for_dependency_analyzer_agent():
        return (
            "7. **Available Tools:**\n"
            "You have access to the following tools to help analyze project dependencies:\n\n"
            "- **read_file_tool**: Read the content of a file from the project root. Use this to examine package.json and other configuration files.\n"
            "- **check_file_exists_tool**: Check if a file exists at a given path. Use this to verify the presence of package.json.\n"
            "- **npm_search_tool**: Search for npm packages and return suggestions. Use this when you need to find available packages for specific functionality.\n"
            "- **npm_install_tool**: Install an npm package. Use this to add new dependencies to the project when required.\n"
            "- **npm_list_tool**: List installed npm packages. Use this to get the current list of available dependencies.\n\n"
            "**Tool Usage Guidelines:**\n"
            "- Use npm_list_tool to get the current installed dependencies from package.json.\n"
            "- Use npm_search_tool when the task requires external packages that may not be currently installed.\n"
            "- Use npm_install_tool only when a required package is not available and needs to be installed.\n"
            "- Always check existing dependencies first before suggesting new package installations.\n"
            "- Use read_file_tool to examine package.json directly if needed for detailed dependency analysis.\n\n"
        )

    @staticmethod
    def get_tool_instructions_for_code_generator_agent():
        return (
            "7. **Available Tools:**\n"
            "You have access to the following tools to help with package management during code generation:\n\n"
            "- **npm_search_tool**: Search for npm packages and return suggestions. Use this to find packages that might be needed for implementing specific functionality.\n"
            "- **npm_install_tool**: Install an npm package. Use this when a required package is identified and needs to be installed.\n\n"
            "**Tool Usage Guidelines:**\n"
            "- Use npm_search_tool to research available packages when the task mentions specific npm packages or when you need external libraries.\n"
            "- Use npm_install_tool to install packages that are confirmed to be needed and available.\n"
            "- Only install packages that are explicitly mentioned in the task requirements or that you've verified are necessary.\n"
            "- Filter generated code imports to only include packages that are actually available in the project.\n"
            "- When generating code, consider the available dependencies and avoid suggesting packages that aren't installed.\n\n"
        )

    @staticmethod
    def get_collaborative_generation_prompt(code_structure: str, test_structure: str, method_name: str, command_id: str, main_file: str, test_file: str, raw_refined_ticket: str = "", original_ticket_content: str = ""):
        """Generate prompt for collaborative code and test generation."""
        formatted_section = ModularPrompts.get_raw_refined_ticket_section().format(raw_refined_ticket=json.dumps(raw_refined_ticket, indent=2) if isinstance(raw_refined_ticket, dict) else raw_refined_ticket)
        log_info("ModularPrompts", f"Raw refined ticket section: {formatted_section}")
        return (
            f"{ModularPrompts.get_base_instruction()}\n\n"
            f"{ModularPrompts.get_code_structure_section(code_structure)}\n"
            f"{ModularPrompts.get_code_requirements_section(raw_refined_ticket, original_ticket_content)}\n"
            f"{ModularPrompts.get_test_structure_section(test_structure)}\n"
            f"{ModularPrompts.get_test_requirements_section(raw_refined_ticket, original_ticket_content)}\n"
            "3. **Collaborative Generation Requirements:**\n"
            " - Generate both the TypeScript code additions and the Jest test additions together in a single response.\n"
            " - First, output the complete code additions for {main_file}, starting directly with the new method and command.\n"
            " - Then, output the complete test additions for {test_file}, starting with the two describe blocks.\n"
            " - Ensure code and tests are mutually consistent: tests must validate the exact implementation in the code.\n"
            " - Use cross-validation: code should pass the generated tests, and tests should accurately reflect the code's behavior.\n"
            " - Follow iterative refinement: if initial generation has issues, refine both code and tests collaboratively.\n\n"
            "4. **Task Details:**\n"
            "{{task_details}}\n\n"
            f"{formatted_section}"
            "5. **Output Format:**\n"
            " - Start with: // CODE ADDITIONS FOR {main_file}\n"
            " - Follow with the exact code to add.\n"
            " - Then: // TEST ADDITIONS FOR {test_file}\n"
            " - Follow with the exact test code.\n"
            " - NO extra text, explanations, or markdown.\n"
            " - Ensure all code is valid TypeScript and Jest syntax."
        )

    @staticmethod
    def get_tool_instructions_for_post_test_runner_agent():
        return (
            "7. **Available Tools:**\n"
            "You have access to the following tools to help with testing and project management:\n\n"
            "- **npm_install_tool**: Install npm packages or run npm install. Use this to ensure all dependencies are installed before running tests.\n"
            "- **npm_run_tool**: Run npm scripts. Use this to execute test commands and other npm scripts.\n"
            "- **check_file_exists_tool**: Check if a file exists. Use this to verify the presence of package.json and other configuration files.\n"
            "- **write_file_tool**: Write content to a file. Use this to create log files for test failures.\n\n"
            "**Tool Usage Guidelines:**\n"
            "- Use check_file_exists_tool to verify package.json exists before attempting npm operations.\n"
            "- Use npm_install_tool to install dependencies before running tests.\n"
            "- Use npm_run_tool to execute the test script and capture output for analysis.\n"
            "- Use write_file_tool to save detailed test failure logs when tests fail.\n"
            "- Always handle tool failures gracefully and provide meaningful error messages.\n\n"
        )

    @staticmethod
    def get_ticket_clarity_evaluation_prompt():
        return (
            "Return only valid JSON on the first line. No thinking, no explanations, no markdown.\n\n"
            "Evaluate the clarity of the following ticket and provide a JSON object with 'is_clear' (boolean) and 'suggestions' (list of strings).\n\n"
            "Ticket:\n{ticket_content}\n\n"
            "JSON:"
        )

    @staticmethod
    def get_ticket_clarity_improvements_prompt():
        return (
            "Return only valid JSON on the first line. No thinking, no explanations, no markdown.\n\n"
            "CRITICAL: Refine ticket to structured JSON.\n\n"
            "Ticket:\n{ticket_content}\n\n"
            "Suggestions:\n{suggestions}\n\n"
            "JSON:"
        )

    @staticmethod
    def get_npm_build_test_fix_prompt():
        return (
            "You are an expert TypeScript and Jest developer. Analyze the following errors from npm build and test execution, and propose fixes to the generated code and tests.\n\n"
            "Generated Code:\n{generated_code}\n\n"
            "Generated Tests:\n{generated_tests}\n\n"
            "Errors:\n{errors}\n\n"
            "Propose specific fixes to the code and tests to resolve these errors. Output in JSON format:\n"
            "{{\n"
            "  \"code_fixes\": \"string with updated code\",\n"
            "  \"test_fixes\": \"string with updated tests\",\n"
            "  \"explanation\": \"brief explanation of fixes\"\n"
            "}}"
        )

    @staticmethod
    def get_ts_build_fix_prompt():
        return """You are expert in Obsidian TS plugins (rollup/Jest). Fix TS compile (rollup/tsc), Jest errors in `src/main.ts`/`src/__tests__/main.test.ts`.

Obsidian mocks: use `src/__mocks__/obsidian.ts` patterns (mockEditor.replaceSelection, mockApp.workspace.getActiveViewOfType etc.).

Errors: {errors}

Code: {generated_code}

Tests: {generated_tests}

Output JSON: {{"code_fixes": "updated main.ts snippet", "test_fixes": "updated main.test.ts snippet", "explanation": "fixes"}}""".format(...)
