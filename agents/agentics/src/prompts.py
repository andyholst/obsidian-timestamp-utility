class ModularPrompts:
    """Modular prompt components following LangChain best practices."""

    @staticmethod
    def get_base_instruction():
        return "You are an expert TypeScript developer for Obsidian plugins. IMPORTANT: Respond ONLY with valid code, no explanations, no markdown, no thinking content."

    @staticmethod
    def get_code_structure_section(code_structure: str):
        return f"1. **Existing Code Structure:**\n - Classes: {code_structure}\n - The plugin class extends `obsidian.Plugin`.\n - Commands are added in the `onload` method using `this.addCommand`.\n - Helper functions and modals may be defined outside the class.\n\n"

    @staticmethod
    def get_code_requirements_section():
        return (
            "2. **New Code Requirements:**\n"
            " - Add a new public method to the plugin class with a name derived from the task title.\n"
            " - The method should have the signature: public {{method_name}}(text: string | null | undefined): string\n"
            " - Implement the method to process the text according to the task details, following the implementation steps, using the suggested npm packages, or implementing manually as noted. Handle null and undefined inputs by returning an empty string.\n"
            " - Ensure the method is public and does not use `private` or `protected` keywords.\n"
            " - Add a new command using `this.addCommand` within the `onload` method that gets the current editor content using ctx.editor.getValue(), calls this method with the content, and sets the editor content to the result using ctx.editor.setValue(result). Use the correct signature: editorCallback: (editor: obsidian.Editor, ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => void\n"
            " - Reuse existing imports (e.g., `import * as obsidian from 'obsidian';`).\n"
            " - If npm packages are suggested and available, add the necessary imports for them.\n"
            " - Do not redefine existing classes, interfaces, methods, or functions.\n"
            " - Do not add new imports, modals, or external dependencies unless specified in the npm packages and available.\n"
            " - You may include single-line comments (//) above new methods to describe their purpose, but do not add any other comments or explanations.\n"
            " - Keep the code simple and focused on the task; do not add complex features unless specified.\n\n"
        )

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
    def get_test_requirements_section():
        return (
            "2. **New Test Requirements:**\n"
            " - Generate exactly two `describe` blocks:\n"
            " - One for the method `{method_name}` added to the plugin class.\n"
            " - One for the command `{command_id}` added via `this.addCommand`.\n"
            " - For the method test, call `plugin.{method_name}('test input')` to use the real implementation and check the result (e.g., expect it to return a string or call mockEditor).\n"
            " - For the command test, execute `mockCommands['{command_id}'].callback()` to trigger the command, which should call `{method_name}` and interact with `mockEditor`.\n"
            " - Match the style of existing tests (e.g., async tests with `await plugin.onload()`, checking `mockEditor.replaceSelection`).\n"
            " - Only generate tests for `{method_name}` and `{command_id}`, as these are the new additions.\n"
            " - Do not access private methods or non-existent properties on the plugin.\n"
            " - Do not use jest.spyOn on plugin methods.\n\n"
        )

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
            " - Response MUST start with 'describe(' and end with '});'.\n"
            " - ONLY the two inner describe blocks.\n"
            " - NO top-level describe, imports, comments, or extra text.\n"
            " - MUST include 'describe(' and 'it(' or 'test(' keywords.\n"
            " - Valid Jest syntax only."
        )
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