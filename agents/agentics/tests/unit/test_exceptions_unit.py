import pytest
from src.exceptions import (
    AgenticsError,
    ConfigurationError,
    ServiceUnavailableError,
    ValidationError,
    GitHubError,
    OllamaError,
    MCPError,
    WorkflowError,
    CircuitBreakerError,
    BatchProcessingError,
    HealthCheckError,
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_agentics_error(self):
        """Test that all custom exceptions inherit from AgenticsError."""
        exceptions = [
            ConfigurationError,
            ServiceUnavailableError,
            ValidationError,
            GitHubError,
            OllamaError,
            MCPError,
            WorkflowError,
            CircuitBreakerError,
            BatchProcessingError,
            HealthCheckError,
        ]

        for exc_class in exceptions:
            # Create instance and check inheritance
            exc = exc_class("test message")
            assert isinstance(exc, AgenticsError)
            assert isinstance(exc, Exception)

    def test_agentics_error_is_base_exception(self):
        """Test that AgenticsError inherits from Exception."""
        exc = AgenticsError("test")
        assert isinstance(exc, Exception)


class TestExceptionMessages:
    """Test exception message formatting and string representation."""

    @pytest.mark.parametrize("exc_class", [
        ConfigurationError,
        ServiceUnavailableError,
        ValidationError,
        GitHubError,
        OllamaError,
        MCPError,
        WorkflowError,
        CircuitBreakerError,
        HealthCheckError,
    ])
    def test_basic_exception_messages(self, exc_class):
        """Test basic exceptions with custom messages."""
        message = "Custom error message"
        exc = exc_class(message)
        assert str(exc) == message
        assert exc.args[0] == message

    def test_batch_processing_error_message(self):
        """Test BatchProcessingError message."""
        message = "Batch processing failed"
        exc = BatchProcessingError(message)
        assert str(exc) == message
        assert exc.args[0] == message


class TestBatchProcessingError:
    """Test BatchProcessingError custom attributes."""

    def test_batch_processing_error_with_failed_items(self):
        """Test BatchProcessingError with failed_items parameter."""
        message = "Some items failed"
        failed_items = ["item1", "item2", "item3"]
        exc = BatchProcessingError(message, failed_items=failed_items)
        assert str(exc) == message
        assert exc.failed_items == failed_items

    def test_batch_processing_error_without_failed_items(self):
        """Test BatchProcessingError without failed_items (defaults to empty list)."""
        message = "Batch failed"
        exc = BatchProcessingError(message)
        assert str(exc) == message
        assert exc.failed_items == []

    def test_batch_processing_error_with_none_failed_items(self):
        """Test BatchProcessingError with None failed_items."""
        message = "Batch failed"
        exc = BatchProcessingError(message, failed_items=None)
        assert str(exc) == message
        assert exc.failed_items == []


class TestExceptionInstantiation:
    """Test exception instantiation with various parameters."""

    @pytest.mark.parametrize("exc_class", [
        ConfigurationError,
        ServiceUnavailableError,
        ValidationError,
        GitHubError,
        OllamaError,
        MCPError,
        WorkflowError,
        CircuitBreakerError,
        HealthCheckError,
    ])
    def test_instantiation_with_message(self, exc_class):
        """Test instantiation with message string."""
        message = "Test message"
        exc = exc_class(message)
        assert exc.args == (message,)

    @pytest.mark.parametrize("exc_class", [
        ConfigurationError,
        ServiceUnavailableError,
        ValidationError,
        GitHubError,
        OllamaError,
        MCPError,
        WorkflowError,
        CircuitBreakerError,
        HealthCheckError,
    ])
    def test_instantiation_with_multiple_args(self, exc_class):
        """Test instantiation with multiple arguments."""
        args = ("Message", "extra", 123)
        exc = exc_class(*args)
        assert exc.args == args

    def test_batch_processing_error_instantiation_variations(self):
        """Test BatchProcessingError instantiation variations."""
        # With message only
        exc1 = BatchProcessingError("msg")
        assert exc1.failed_items == []

        # With message and failed_items
        exc2 = BatchProcessingError("msg", failed_items=["a", "b"])
        assert exc2.failed_items == ["a", "b"]

        # With message and None
        exc3 = BatchProcessingError("msg", failed_items=None)
        assert exc3.failed_items == []


class TestExceptionChaining:
    """Test exception chaining and context preservation."""

    def test_exception_chaining_with_raise_from(self):
        """Test exception chaining using 'raise from'."""
        original_exc = ValueError("Original error")
        try:
            raise ConfigurationError("Config error") from original_exc
        except ConfigurationError as e:
            assert isinstance(e, ConfigurationError)
            assert e.__cause__ is original_exc
            assert str(e) == "Config error"

    def test_exception_chaining_with_custom_exceptions(self):
        """Test chaining between custom exceptions."""
        try:
            raise ValidationError("Validation failed")
        except ValidationError as ve:
            try:
                raise WorkflowError("Workflow failed") from ve
            except WorkflowError as we:
                assert we.__cause__ is ve
                assert str(we) == "Workflow failed"

    def test_batch_processing_error_chaining(self):
        """Test chaining with BatchProcessingError."""
        original = GitHubError("GitHub API failed")
        try:
            raise BatchProcessingError("Batch failed", failed_items=["item1"]) from original
        except BatchProcessingError as e:
            assert e.__cause__ is original
            assert e.failed_items == ["item1"]
            assert str(e) == "Batch failed"

    def test_no_chaining(self):
        """Test exceptions without chaining."""
        exc = AgenticsError("No cause")
        assert exc.__cause__ is None
        assert exc.__context__ is None