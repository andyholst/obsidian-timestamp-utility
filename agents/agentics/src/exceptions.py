"""Custom exceptions for the agentics application."""

from typing import Optional


class AgenticsError(Exception):
    """Base exception for agentics application errors."""
    pass


class ConfigurationError(AgenticsError):
    """Raised when configuration is invalid or missing."""
    pass


class ServiceUnavailableError(AgenticsError):
    """Raised when external services are unavailable."""
    pass


class ValidationError(AgenticsError):
    """Raised when input validation fails."""
    pass


class GitHubError(AgenticsError):
    """Raised when GitHub API operations fail."""
    pass


class OllamaError(AgenticsError):
    """Raised when Ollama LLM operations fail."""
    pass


class MCPError(AgenticsError):
    """Raised when MCP operations fail."""
    pass


class WorkflowError(AgenticsError):
    """Raised when workflow execution fails."""
    pass


class CircuitBreakerError(AgenticsError):
    """Raised when circuit breaker is open."""
    pass


class BatchProcessingError(AgenticsError):
    """Raised when batch processing fails."""
    def __init__(self, message: str, failed_items: Optional[list] = None):
        super().__init__(message)
        self.failed_items = failed_items or []


class HealthCheckError(AgenticsError):
    """Raised when health checks fail."""
    pass