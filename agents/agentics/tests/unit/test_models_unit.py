import pytest
from src.models import CodeGenerationOutput, TestGenerationOutput


def test_code_generation_output():
    """Test CodeGenerationOutput Pydantic model."""
    output = CodeGenerationOutput(
        code="public generateUUID(): string { return 'uuid'; }",
        method_name="generateUUID",
        command_id="generate-uuid"
    )
    assert output.code == "public generateUUID(): string { return 'uuid'; }"
    assert output.method_name == "generateUUID"
    assert output.command_id == "generate-uuid"


def test_code_generation_output_validation():
    """Test CodeGenerationOutput validation."""
    with pytest.raises(ValueError):
        # Missing required field
        CodeGenerationOutput(code="test", method_name="test")  # Missing command_id


def test_test_generation_output():
    """Test TestGenerationOutput Pydantic model."""
    output = TestGenerationOutput(
        tests="describe('test', () => { it('works', () => {}); });"
    )
    assert "describe" in output.tests
    assert "it" in output.tests


def test_test_generation_output_validation():
    """Test TestGenerationOutput validation."""
    with pytest.raises(ValueError):
        # Missing required field
        TestGenerationOutput()  # Missing tests