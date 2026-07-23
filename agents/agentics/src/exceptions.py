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


class LlamaError(AgenticsError):
    """Raised when llama LLM operations fail."""

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


class TestRecoveryNeeded(AgenticsError):
    """Raised when tests fail and recovery is needed."""

    pass


class CompileError(AgenticsError):
    """Raised when TypeScript compilation fails."""

    pass


class LintError(AgenticsError):
    """Raised when the lint gate fails (non-zero eslint/prettier exit).

    Surfaces as a recovery signal so the loop re-enters error_recovery
    (agentic-self-correct-loop, tasks.md §2.2).
    """

    pass


class OmissionDetected(AgenticsError):
    """Raised when generated TS/test shrank vs its timestamped backup.

    A genuine omission (logic dropped) — the file is restored to the backup
    and the loop re-enters error_recovery (agentic-self-correct-loop §4.3).
    """

    pass
