import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock, mock_open
from src.code_integrator_agent import CodeIntegratorAgent
from src.state import State
from src.exceptions import ValidationError


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing"""
    client = MagicMock()
    client.invoke.return_value = "mocked response"
    return client


@pytest.fixture
def temp_project_root():
    """Create a temporary directory for testing file operations"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create src and src/__tests__ directories
        os.makedirs(os.path.join(temp_dir, 'src'))
        os.makedirs(os.path.join(temp_dir, 'src', '__tests__'))
        yield temp_dir


@pytest.fixture
def sample_state():
    """Sample state for testing"""
    return State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={"title": "Test Feature", "description": "Add test feature"},
        generated_code="export class TestFeature { method() { return true; } }",
        generated_tests="describe('TestFeature', () => { it('should work', () => { expect(true).toBe(true); }); });",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[]
    )


class TestCodeIntegratorAgentInit:
    """Test CodeIntegratorAgent initialization"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_init_success(self, mock_llm_client):
        # Given: Required environment variables set
        # When: Initializing the agent
        agent = CodeIntegratorAgent(mock_llm_client)

        # Then: Agent is properly initialized
        assert agent.project_root == '/test/root'
        assert agent.code_ext == '.ts'
        assert agent.test_ext == '.test.ts'
        assert agent.llm == mock_llm_client
        assert len(agent.tools) == 2  # read_file_tool and check_file_exists_tool

    @patch.dict(os.environ, {}, clear=True)
    def test_init_missing_project_root(self, mock_llm_client):
        # Given: PROJECT_ROOT not set
        # When/Then: Initialization raises ValueError
        with pytest.raises(ValueError, match="PROJECT_ROOT environment variable is required"):
            CodeIntegratorAgent(mock_llm_client)

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root', 'CODE_FILE_EXTENSION': '.js', 'TEST_FILE_EXTENSION': '.spec.js'})
    def test_init_custom_extensions(self, mock_llm_client):
        # Given: Custom file extensions
        # When: Initializing the agent
        agent = CodeIntegratorAgent(mock_llm_client)

        # Then: Custom extensions are used
        assert agent.code_ext == '.js'
        assert agent.test_ext == '.spec.js'


class TestCodeIntegratorAgentProcess:
    """Test the main process method"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_process_no_files_no_content(self, mock_llm_client, sample_state):
        # Given: No relevant files and no generated content
        state = sample_state.copy()
        state['relevant_code_files'] = []
        state['relevant_test_files'] = []
        state['generated_code'] = ""
        state['generated_tests'] = ""

        agent = CodeIntegratorAgent(mock_llm_client)

        # When: Processing
        result = agent.process(state)

        # Then: State is returned unchanged
        assert result == state

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_process_no_files_with_content(self, mock_llm_client, sample_state, temp_project_root):
        # Given: No relevant files but generated content
        state = sample_state.copy()
        state['relevant_code_files'] = []
        state['relevant_test_files'] = []

        agent = CodeIntegratorAgent(mock_llm_client)

        # Mock generate_filename and create_file
        with patch.object(agent, 'generate_filename', return_value='testFeature'), \
             patch.object(agent, 'create_file') as mock_create:
            # When: Processing
            result = agent.process(state)

        # Then: New files are created and state is updated
        assert 'relevant_code_files' in result
        assert 'relevant_test_files' in result
        assert len(result['relevant_code_files']) == 1
        assert len(result['relevant_test_files']) == 1
        # Verify create_file was called twice
        assert mock_create.call_count == 2

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_process_with_existing_files(self, mock_llm_client, sample_state):
        # Given: Existing relevant files
        state = sample_state.copy()
        state['relevant_code_files'] = [{"file_path": "src/main.ts", "content": "existing code"}]
        state['relevant_test_files'] = [{"file_path": "src/__tests__/main.test.ts", "content": "existing tests"}]

        agent = CodeIntegratorAgent(mock_llm_client)

        # Mock update_file
        with patch.object(agent, 'update_file') as mock_update:
            # When: Processing
            result = agent.process(state)

        # Then: Files are updated (mocked)
        assert result == state
        # Verify update_file was called twice
        assert mock_update.call_count == 2


class TestCodeIntegratorAgentHelpers:
    """Test helper methods"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_remove_unwanted_lines(self, mock_llm_client):
        # Given: Content with unwanted lines
        agent = CodeIntegratorAgent(mock_llm_client)
        content = "typescript\nsome code\njavascript\nmore code"

        # When: Removing unwanted lines
        result = agent.remove_unwanted_lines(content)

        # Then: Unwanted lines are removed
        assert "typescript" not in result.lower()
        assert "javascript" not in result.lower()
        assert "some code" in result
        assert "more code" in result

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_extract_content(self, mock_llm_client):
        # Given: Raw text content with thinking tags
        agent = CodeIntegratorAgent(mock_llm_client)
        text = "<think>some thinking</think>final content"

        # When: Extracting content
        result = agent.extract_content(text)

        # Then: Thinking tags are removed
        assert result == "final content"

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_generate_filename_success(self, mock_llm_client):
        # Given: LLM returns valid filename
        mock_llm_client.invoke.return_value = "testFeature"
        agent = CodeIntegratorAgent(mock_llm_client)

        # When: Generating filename
        result = agent.generate_filename("Add test feature", "Test Feature")

        # Then: Valid filename is returned
        assert result == "testFeature"

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_generate_filename_fallback(self, mock_llm_client):
        # Given: LLM fails, use fallback
        mock_llm_client.invoke.side_effect = Exception("LLM error")
        agent = CodeIntegratorAgent(mock_llm_client)

        # When: Generating filename
        result = agent.generate_filename("Add test feature", "Test Feature")

        # Then: Fallback filename is used
        assert result == "test"


class TestCodeIntegratorAgentFileOperations:
    """Test file operation methods"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_create_file(self, mock_makedirs, mock_file, mock_llm_client):
        # Given: File path and content
        agent = CodeIntegratorAgent(mock_llm_client)

        # When: Creating file
        agent.create_file('/test/path/file.ts', 'content')

        # Then: File is created
        mock_makedirs.assert_called_once_with('/test/path', exist_ok=True)
        mock_file.assert_called_once_with('/test/path/file.ts', 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with('content')

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    @patch('builtins.open', new_callable=mock_open)
    def test_update_file(self, mock_file, mock_llm_client):
        # Given: Existing file path and content
        agent = CodeIntegratorAgent(mock_llm_client)

        # When: Updating file
        agent.update_file('/test/path/file.ts', 'new content')

        # Then: File is updated
        mock_file.assert_called_once_with('/test/path/file.ts', 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with('new content')


class TestCodeIntegratorAgentIntegration:
    """Test LLM integration methods"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_integrate_code_with_llm(self, mock_llm_client):
        # Given: Existing and new code
        mock_llm_client.invoke.return_value = "integrated code"
        agent = CodeIntegratorAgent(mock_llm_client)
        existing = "class Test { }"
        new_code = "method() { }"

        # When: Integrating code
        result = agent.integrate_code_with_llm(existing, new_code)

        # Then: LLM is called and response processed
        assert result == "integrated code"
        mock_llm_client.invoke.assert_called_once()

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_integrate_tests_manually(self, mock_llm_client):
        # Given: Existing and new tests in expected format
        agent = CodeIntegratorAgent(mock_llm_client)
        existing = "describe('TimestampPlugin', () => { it('exists', () => {}); });"
        new_tests = "import { test } from 'jest'; describe('New', () => { it('works', () => {}); });"

        # When: Integrating tests
        result = agent.integrate_tests_manually(existing, new_tests)

        # Then: Tests are manually integrated
        assert "import { test } from 'jest';" in result
        assert "describe('New', () => { it('works', () => {}); });" in result


class TestCodeIntegratorAgentErrorHandling:
    """Test error handling"""

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    def test_process_empty_content_after_extraction(self, mock_llm_client, sample_state):
        # Given: Generated content that becomes empty after processing
        state = sample_state.copy()
        state['generated_code'] = "typescript"
        state['generated_tests'] = "javascript"

        agent = CodeIntegratorAgent(mock_llm_client)

        # When/Then: Processing raises ValueError
        with pytest.raises(ValueError, match="Code or test content is empty"):
            agent.process(state)

    @patch.dict(os.environ, {'PROJECT_ROOT': '/test/root'})
    @patch('builtins.open')
    def test_create_file_io_error(self, mock_open, mock_llm_client):
        # Given: File creation fails
        mock_open.side_effect = IOError("Disk full")
        agent = CodeIntegratorAgent(mock_llm_client)

        # When/Then: Exception is raised
        with pytest.raises(IOError):
            agent.create_file('/test/file.ts', 'content')