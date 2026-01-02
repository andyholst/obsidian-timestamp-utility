import pytest
from unittest.mock import MagicMock, patch, Mock
from src.dependency_installer_agent import DependencyInstallerAgent
from src.state import State

@pytest.fixture
def agent():
    agent = DependencyInstallerAgent()
    agent.monitor = Mock()
    return agent

@pytest.fixture
def mock_tool_executor(agent):
    mock_executor = Mock()
    agent.tool_executor = mock_executor
    return mock_executor

@pytest.fixture
def state_no_packages():
    return {'refined_ticket': {}}

@pytest.fixture
def state_with_packages():
    return {
        'refined_ticket': {
            'npm_packages': [
                {'name': 'uuid'},
                {'name': 'nanoid'},
                'lodash'
            ]
        }
    }

def test_process_no_packages(agent, state_no_packages):
    result = agent.process(state_no_packages)
    assert result == state_no_packages
    assert 'installed_deps' not in result

@patch('os.getenv')
def test_process_with_packages(mock_getenv, agent, mock_tool_executor, state_with_packages):
    mock_getenv.return_value = '/project'
    
    # Mock tool calls
    mock_tool_executor.execute_tool.side_effect = [
        True,  # check_file_exists package.json
        '{"dependencies": {}}',  # read_file_tool
        None,  # write_file_tool
        None,  # npm_install uuid
        None,  # npm_install nanoid
        None   # npm_install lodash
    ]
    
    result = agent.process(state_with_packages)
    
    assert 'installed_deps' in result
    assert sorted(result['installed_deps']) == sorted(['uuid', 'nanoid', 'lodash'])
    
    # Verify calls
    assert mock_tool_executor.execute_tool.call_count == 6
    mock_tool_executor.execute_tool.assert_any_call(
        'npm_install_tool',
        {'package_name': 'uuid', 'is_dev': False, 'save_exact': True, 'cwd': '/project'}
    )

def test_process_package_json_update(agent, mock_tool_executor, state_with_packages):
    mock_tool_executor.execute_tool.side_effect = [
        True,
        '{"dependencies": {"express": "^4.0.0"}}',
        None,
        None
    ]
    
    result = agent.process(state_with_packages)
    
    # Should add only new deps
    assert 'installed_deps' in result
    assert len(result['installed_deps']) == 3