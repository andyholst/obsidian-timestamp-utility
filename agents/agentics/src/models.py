from pydantic import BaseModel, Field
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodeSpec:
    """Specification for code generation"""
    language: str
    framework: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TestSpec:
    """Specification for test generation"""
    test_framework: str
    test_type: str = "unit"
    coverage_requirements: Optional[dict] = None


@dataclass(frozen=True)
class ValidationResults:
    """Results of validation process"""
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CodeGenerationOutput(BaseModel):
    code: str = Field(description="The generated TypeScript code")
    method_name: str = Field(description="The name of the generated method")
    command_id: str = Field(description="The ID of the generated command")


class TestGenerationOutput(BaseModel):
    tests: str = Field(description="The generated Jest test code")