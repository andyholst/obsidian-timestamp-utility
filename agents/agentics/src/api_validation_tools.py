"""
API Validation Tools for Tool-Integrated Code Generator

This module provides tools for validating Obsidian API usage and npm package dependencies
before code generation, implementing error recovery for API hallucinations.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from .exceptions import ValidationError
from .monitoring import structured_log

logger = structured_log(__name__)


@dataclass(frozen=True)
class ValidationResult:
    """Immutable validation result"""
    is_valid: bool
    errors: List[str]
    suggestions: List[str]
    confidence_score: float

    def with_error(self, error: str) -> 'ValidationResult':
        """Return new result with added error"""
        return ValidationResult(
            is_valid=False,
            errors=self.errors + [error],
            suggestions=self.suggestions,
            confidence_score=max(0, self.confidence_score - 0.1)
        )

    def with_suggestion(self, suggestion: str) -> 'ValidationResult':
        """Return new result with added suggestion"""
        return ValidationResult(
            is_valid=self.is_valid,
            errors=self.errors,
            suggestions=self.suggestions + [suggestion],
            confidence_score=self.confidence_score
        )


class ObsidianAPIValidator:
    """Validates Obsidian API calls against documentation"""

    def __init__(self):
        self.logger = structured_log("obsidian_api_validator")

    def validate_api_call(self, api_call: str, context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate an Obsidian API call against actual documentation

        Args:
            api_call: The API method call (e.g., 'app.vault.create')
            context: Additional context about the call

        Returns:
            ValidationResult with validation status and details
        """
        try:
            # Use MCP context7 to get Obsidian documentation
            # First resolve library ID for Obsidian
            library_id = self._resolve_obsidian_library_id()

            # Get API documentation
            docs = self._get_obsidian_api_docs(library_id, api_call)

            # Check if API call exists in docs
            if self._api_exists_in_docs(api_call, docs):
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    suggestions=[],
                    confidence_score=0.95
                )
            else:
                # API not found, suggest alternatives
                suggestions = self._find_similar_apis(api_call, docs)
                return ValidationResult(
                    is_valid=False,
                    errors=[f"API call '{api_call}' not found in Obsidian documentation"],
                    suggestions=suggestions,
                    confidence_score=0.3
                )

        except Exception as e:
            self.logger.error("obsidian_api_validation_error", {"api_call": api_call, "error": str(e)})
            return ValidationResult(
                is_valid=False,
                errors=[f"Failed to validate API call: {str(e)}"],
                suggestions=["Check Obsidian API documentation manually"],
                confidence_score=0.0
            )

    def _resolve_obsidian_library_id(self) -> str:
        """Resolve Context7 library ID for Obsidian"""
        # This would use mcp_context7_resolve-library-id
        # For now, assume it's '/obsidian/docs'
        return '/obsidian/docs'

    def _get_obsidian_api_docs(self, library_id: str, topic: str) -> Dict[str, Any]:
        """Get Obsidian API documentation using Context7"""
        # This would use mcp_context7_get-library-docs
        # Mock implementation for now
        # In real implementation, call the MCP tool
        return {
            "apis": [
                "app.vault.create",
                "app.vault.read",
                "app.vault.modify",
                "app.metadataCache.getFileCache",
                "app.workspace.getActiveView"
            ]
        }

    def _api_exists_in_docs(self, api_call: str, docs: Dict[str, Any]) -> bool:
        """Check if API call exists in documentation"""
        apis = docs.get("apis", [])
        return api_call in apis

    def _find_similar_apis(self, api_call: str, docs: Dict[str, Any]) -> List[str]:
        """Find similar API calls for suggestions"""
        apis = docs.get("apis", [])
        # Simple string similarity - in real implementation, use better matching
        similar = [api for api in apis if api_call.split('.')[0] in api]
        return similar[:3]  # Limit suggestions


class NPMDependencyValidator:
    """Validates npm package availability before import generation"""

    def __init__(self):
        self.logger = structured_log("npm_dependency_validator")

    def validate_package(self, package_name: str, version: Optional[str] = None) -> ValidationResult:
        """
        Validate npm package availability

        Args:
            package_name: Name of the npm package
            version: Optional version constraint

        Returns:
            ValidationResult with validation status
        """
        try:
            # Check if package exists using npm view
            result = self._check_package_exists(package_name, version)

            if result["exists"]:
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    suggestions=[],
                    confidence_score=0.98
                )
            else:
                # Package not found
                suggestions = self._find_similar_packages(package_name)
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Package '{package_name}' not found on npm"],
                    suggestions=suggestions,
                    confidence_score=0.1
                )

        except Exception as e:
            self.logger.error("npm_validation_error", {"package": package_name, "error": str(e)})
            return ValidationResult(
                is_valid=False,
                errors=[f"Failed to validate package: {str(e)}"],
                suggestions=["Check package name spelling", "Verify package exists on npmjs.com"],
                confidence_score=0.0
            )

    def _check_package_exists(self, package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Check if package exists using npm view"""
        # This would use execute_command with npm view
        # Mock implementation for now
        known_packages = ["obsidian", "typescript", "jest", "@types/node"]
        exists = package_name in known_packages
        return {"exists": exists, "version": version or "latest"}

    def _find_similar_packages(self, package_name: str) -> List[str]:
        """Find similar package names"""
        # Mock implementation - in real, use npm search
        similar = ["obsidian", "obsidian-api", "obsidian-dev-utils"]
        return [pkg for pkg in similar if package_name.lower() in pkg.lower()][:3]


class APIValidationTools:
    """Collection of API validation tools"""

    def __init__(self):
        self.obsidian_validator = ObsidianAPIValidator()
        self.npm_validator = NPMDependencyValidator()

    @tool
    def validate_obsidian_api(self, api_call: str) -> str:
        """
        Validate an Obsidian API call against documentation

        Args:
            api_call: The API method call to validate

        Returns:
            JSON string with validation result
        """
        result = self.obsidian_validator.validate_api_call(api_call)
        return result.__dict__

    @tool
    def validate_npm_package(self, package_name: str, version: Optional[str] = None) -> str:
        """
        Validate npm package availability

        Args:
            package_name: Name of the package
            version: Optional version constraint

        Returns:
            JSON string with validation result
        """
        result = self.npm_validator.validate_package(package_name, version)
        return result.__dict__