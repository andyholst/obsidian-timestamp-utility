"""
Standardized mock LLM responses for consistent testing.
These mocks provide realistic LLM responses to prevent real API calls in unit tests.
"""

from unittest.mock import MagicMock
import json


def create_mock_llm_response(response_text: str) -> MagicMock:
    """Create a mock LLM client that returns a predetermined response."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = response_text
    mock_llm.return_value = response_text
    return mock_llm


def create_process_llm_mock_responses():
    """Create mock responses for ProcessLLMAgent tests."""

    # Well-structured ticket response
    well_structured_response = json.dumps({
        "title": "# Implement Timestamp-based UUID Generator in Obsidian",
        "description": "Add a command to Obsidian that generates a UUID (Universally Unique Identifier) based on the current timestamp and inserts it into the active note at the cursor position. This feature will allow users to quickly create unique identifiers for linking, referencing, or organizing content within their notes. The UUID should follow the UUID v7 standard, which is the latest version, offering improved performance and privacy over earlier versions like UUID v1.",
        "requirements": [
            "The command must be accessible via Obsidian's command palette.",
            "It should generate a UUID using the current timestamp, following the UUID v7 standard.",
            "The generated UUID must be inserted at the current cursor position in the active note.",
            "If no note is active when the command is executed, an appropriate error message should be displayed."
        ],
        "acceptance_criteria": [
            "The command is visible in Obsidian's command palette when searched.",
            "When the command is executed with an active note, a valid UUID v7 is generated and inserted at the cursor position.",
            "The generated UUID is unique and correctly formatted according to the UUID v7 standard.",
            "If no note is active when the command is executed, an error message is displayed to the user."
        ],
        "implementation_steps": [
            "Install the uuid package for UUID v7 generation",
            "Create a new command in the TimestampPlugin class",
            "Implement UUID generation logic using current timestamp",
            "Add cursor position detection and text insertion",
            "Add error handling for cases when no active note exists"
        ],
        "npm_packages": ["uuid"],
        "manual_implementation_notes": "Ensure the plugin follows Obsidian's plugin development guidelines and handles edge cases gracefully."
    })

    # Sloppy ticket response
    sloppy_response = json.dumps({
        "title": "Implement Timestamp-based UUID Generator in Obsidian",
        "description": "Add a command to Obsidian that generates a UUID (Universally Unique Identifier) based on the current timestamp and inserts it into the active note at the cursor position. This feature will allow users to quickly create unique identifiers for linking, referencing, or organizing content within their notes. The UUID should follow the UUID v7 standard, which is the latest version, offering improved performance and privacy over earlier versions like UUID v1.",
        "requirements": [
            "The command must be accessible via Obsidian's command palette.",
            "It should generate a UUID using the current timestamp, following the UUID v7 standard.",
            "The generated UUID must be inserted at the current cursor position in the active note.",
            "If no note is active when the command is executed, an appropriate error message should be displayed.",
            "When this is considering done"
        ],
        "acceptance_criteria": [
            "The command is visible in Obsidian's command palette when searched.",
            "When the command is executed with an active note, a valid UUID v7 is generated and inserted at the cursor position.",
            "The generated UUID is unique and correctly formatted according to the UUID v7 standard.",
            "If no note is active when the command is executed, an error message is displayed to the user."
        ],
        "implementation_steps": [],
        "npm_packages": [],
        "manual_implementation_notes": ""
    })

    # Long ticket response
    long_response = json.dumps({
        "title": "# Very Long Ticket Title",
        "description": "Description with lots of details " * 50,
        "requirements": ["Req1", "Req2"],
        "acceptance_criteria": ["AC1", "AC2"],
        "implementation_steps": [],
        "npm_packages": [],
        "manual_implementation_notes": ""
    })

    # Empty ticket response
    empty_response = json.dumps({
        "title": "Untitled Task",
        "description": "No description provided",
        "requirements": [],
        "acceptance_criteria": [],
        "implementation_steps": [],
        "npm_packages": [],
        "manual_implementation_notes": ""
    })

    # Malformed ticket response
    malformed_response = json.dumps({
        "title": "# Title",
        "description": "Test description",
        "requirements": ["Req1"],
        "acceptance_criteria": ["AC1"],
        "implementation_steps": [],
        "npm_packages": [],
        "manual_implementation_notes": ""
    })

    # Dict input response
    dict_response = json.dumps({
        "title": "Test Ticket",
        "description": "Test description",
        "requirements": ["Req1"],
        "acceptance_criteria": ["AC1"],
        "implementation_steps": [],
        "npm_packages": [],
        "manual_implementation_notes": ""
    })

    return {
        "well_structured": create_mock_llm_response(well_structured_response),
        "sloppy": create_mock_llm_response(sloppy_response),
        "long": create_mock_llm_response(long_response),
        "empty": create_mock_llm_response(empty_response),
        "malformed": create_mock_llm_response(malformed_response),
        "dict": create_mock_llm_response(dict_response)
    }


def create_code_generator_mock_responses():
    """Create mock responses for CodeGeneratorAgent tests."""

    # Code generation response
    code_response = """import { v7 as uuidv7 } from 'uuid';

export class TimestampPlugin extends obsidian.Plugin {
    async onload() {
        this.addCommand({
            id: 'generate-uuid',
            name: 'Generate UUID v7',
            callback: () => {
                this.generateUUID();
            }
        });
    }

    generateUUID() {
        const activeView = this.app.workspace.getActiveViewOfType(obsidian.MarkdownView);
        if (!activeView) {
            new obsidian.Notice('No active note found');
            return;
        }

        const editor = activeView.editor;
        const uuid = uuidv7();
        editor.replaceSelection(uuid);
    }
}"""

    # Test generation response
    test_response = """import { TimestampPlugin } from '../src/main';

describe('TimestampPlugin', () => {
    let plugin: TimestampPlugin;
    let mockApp: any;

    beforeEach(() => {
        mockApp = {
            workspace: {
                getActiveViewOfType: jest.fn()
            }
        };
        plugin = new TimestampPlugin(mockApp);
    });

    describe('generateUUID', () => {
        it('should generate and insert UUID when active view exists', () => {
            const mockEditor = {
                replaceSelection: jest.fn()
            };
            const mockView = {
                editor: mockEditor
            };

            mockApp.workspace.getActiveViewOfType.mockReturnValue(mockView);

            plugin.generateUUID();

            expect(mockEditor.replaceSelection).toHaveBeenCalledWith(expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/));
        });

        it('should show notice when no active view exists', () => {
            mockApp.workspace.getActiveViewOfType.mockReturnValue(null);

            plugin.generateUUID();

            // Notice would be shown, but we can't easily test this without mocking obsidian.Notice
        });
    });
});"""

    # Vague ticket response (empty)
    vague_response = ""

    # Feedback response (corrected code)
    feedback_response = """import { v7 as uuidv7 } from 'uuid';

export class TimestampPlugin extends obsidian.Plugin {
    async onload() {
        this.addCommand({
            id: 'generate-uuid',
            name: 'Generate UUID v7',
            callback: async () => {
                await this.generateUUID();
            }
        });
    }

    async generateUUID() {
        const activeView = this.app.workspace.getActiveViewOfType(obsidian.MarkdownView);
        if (!activeView) {
            new obsidian.Notice('No active note found');
            return;
        }

        const editor = activeView.editor;
        const uuid = uuidv7();
        editor.replaceSelection(uuid);
    }
}"""

    return {
        "code_generation": create_mock_llm_response(code_response),
        "test_generation": create_mock_llm_response(test_response),
        "vague": create_mock_llm_response(vague_response),
        "feedback": create_mock_llm_response(feedback_response)
    }


def create_mock_prompt_template():
    """Create a mock prompt template that returns the input unchanged."""
    mock_template = MagicMock()
    mock_template.invoke.return_value = "mocked prompt"
    return mock_template


def create_streaming_llm_mock():
    """Create a mock LLM client that supports streaming responses."""
    mock_llm = MagicMock()

    def mock_stream(prompt):
        """Mock streaming response that yields chunks."""
        response_chunks = [
            "This is the first chunk of response. ",
            "Continuing with more content here. ",
            "Adding some technical details. ",
            "Finally, concluding the response."
        ]
        for chunk in response_chunks:
            yield chunk

    mock_llm.stream.side_effect = mock_stream
    mock_llm.astream = AsyncMock(side_effect=mock_stream)
    return mock_llm


def create_llm_error_scenarios():
    """Create mock LLM clients that simulate various error conditions."""

    # Timeout error
    timeout_mock = MagicMock()
    timeout_mock.invoke.side_effect = TimeoutError("Request timed out")
    timeout_mock.stream.side_effect = TimeoutError("Streaming request timed out")

    # Connection error
    connection_mock = MagicMock()
    connection_mock.invoke.side_effect = ConnectionError("Failed to connect to Ollama server")
    connection_mock.stream.side_effect = ConnectionError("Failed to connect to Ollama server")

    # Model not found error
    model_not_found_mock = MagicMock()
    model_not_found_mock.invoke.side_effect = ValueError("model 'nonexistent-model' not found")
    model_not_found_mock.stream.side_effect = ValueError("model 'nonexistent-model' not found")

    # Rate limiting error
    rate_limit_mock = MagicMock()
    rate_limit_mock.invoke.side_effect = Exception("Rate limit exceeded. Please try again later.")
    rate_limit_mock.stream.side_effect = Exception("Rate limit exceeded. Please try again later.")

    # Invalid prompt error
    invalid_prompt_mock = MagicMock()
    invalid_prompt_mock.invoke.side_effect = ValueError("Invalid prompt format")
    invalid_prompt_mock.stream.side_effect = ValueError("Invalid prompt format")

    return {
        "timeout": timeout_mock,
        "connection": connection_mock,
        "model_not_found": model_not_found_mock,
        "rate_limit": rate_limit_mock,
        "invalid_prompt": invalid_prompt_mock
    }


def create_llm_batch_responses():
    """Create mock responses for batch processing scenarios."""
    batch_responses = {
        "single_prompt": ["Response to single prompt"],
        "multiple_prompts": [
            "Response to first prompt",
            "Response to second prompt",
            "Response to third prompt"
        ],
        "empty_prompt": [""],
        "long_prompt": ["This is a very long response that contains multiple sentences and paragraphs of content to test how the system handles verbose LLM outputs." * 10]
    }

    def create_batch_mock(responses):
        mock_llm = MagicMock()
        mock_llm.batch_invoke.return_value = responses
        mock_llm.abatch_invoke = AsyncMock(return_value=responses)
        return mock_llm

    return {
        key: create_batch_mock(responses)
        for key, responses in batch_responses.items()
    }


def create_llm_with_memory():
    """Create a mock LLM that maintains conversation memory."""
    mock_llm = MagicMock()
    conversation_history = []

    def mock_invoke_with_memory(prompt):
        conversation_history.append(f"User: {prompt}")
        # Generate response based on history
        response = f"Response to: {prompt} (History length: {len(conversation_history)})"
        conversation_history.append(f"Assistant: {response}")
        return response

    mock_llm.invoke.side_effect = mock_invoke_with_memory
    mock_llm.get_conversation_history = lambda: conversation_history.copy()
    mock_llm.clear_history = lambda: conversation_history.clear()

    return mock_llm


def create_multimodal_llm_mock():
    """Create a mock LLM that handles multimodal inputs (text + images, etc.)."""
    mock_llm = MagicMock()

    def mock_invoke_multimodal(inputs):
        if isinstance(inputs, dict) and "image" in inputs:
            return "I can see an image in your input. It appears to be a technical diagram."
        elif isinstance(inputs, dict) and "text" in inputs:
            return f"Processing text input: {inputs['text'][:50]}..."
        else:
            return "Standard text response"

    mock_llm.invoke.side_effect = mock_invoke_multimodal
    mock_llm.ainvoke = AsyncMock(side_effect=mock_invoke_multimodal)

    return mock_llm


def create_llm_with_token_limits():
    """Create a mock LLM that enforces token limits."""
    mock_llm = MagicMock()

    def mock_invoke_with_limits(prompt):
        token_count = len(prompt.split())  # Rough token estimation
        if token_count > 100:
            raise ValueError("Input exceeds maximum token limit of 100")
        return f"Response to {token_count} tokens"

    mock_llm.invoke.side_effect = mock_invoke_with_limits
    mock_llm.max_tokens = 100
    mock_llm.count_tokens = lambda text: len(text.split())

    return mock_llm
    return mock_template