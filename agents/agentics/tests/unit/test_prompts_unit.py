import pytest
from src.prompts import ModularPrompts


def test_get_base_instruction():
    """Test base instruction generation."""
    instruction = ModularPrompts.get_base_instruction()
    assert "TypeScript developer" in instruction
    assert "Obsidian plugins" in instruction


def test_get_code_structure_section():
    """Test code structure section generation."""
    structure = '{"classes": ["TestClass"], "methods": ["testMethod"]}'
    section = ModularPrompts.get_code_structure_section(structure)
    assert "Existing Code Structure" in section
    assert structure in section
    assert "obsidian.Plugin" in section


def test_get_code_requirements_section():
    """Test code requirements section."""
    section = ModularPrompts.get_code_requirements_section()
    assert "New Code Requirements" in section
    assert "public method" in section
    assert "addCommand" in section
    assert "editorCallback" in section


def test_get_test_structure_section():
    """Test test structure section generation."""
    structure = '{"describes": ["test1", "test2"]}'
    section = ModularPrompts.get_test_structure_section(structure)
    assert "Existing Test Structure" in section
    assert structure in section
    assert "describe('TimestampPlugin'" in section


def test_get_test_requirements_section():
    """Test test requirements section."""
    section = ModularPrompts.get_test_requirements_section()
    assert "New Test Requirements" in section
    assert "describe" in section
    assert "mockCommands" in section


def test_get_output_instructions_code():
    """Test code output instructions."""
    instructions = ModularPrompts.get_output_instructions_code()
    assert "Output Instructions" in instructions
    assert "TypeScript code" in instructions
    assert "main_file" in instructions


def test_get_output_instructions_tests():
    """Test test output instructions."""
    instructions = ModularPrompts.get_output_instructions_tests()
    assert "Output Instructions" in instructions
    assert "describe" in instructions


def test_modular_prompts_static_methods():
    """Test that all methods are static."""
    # These should not raise AttributeError
    ModularPrompts.get_base_instruction()
    ModularPrompts.get_code_structure_section("{}")
    ModularPrompts.get_code_requirements_section()
    ModularPrompts.get_test_structure_section("{}")
    ModularPrompts.get_test_requirements_section()
    ModularPrompts.get_output_instructions_code()
    ModularPrompts.get_output_instructions_tests()