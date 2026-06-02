"""
Structured Logging Module for Agentics

Provides structured logging with consistent JSON format.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StructuredLogger(logging.Logger):
    """Structured logging with consistent format"""

    def __init__(self, name: str):
        super().__init__(name)
        self.logger = logging.getLogger(name)

    def _log_structured(
        self,
        level: int,
        event: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": logging.getLevelName(level),
            "event": event,
            "component": self.name,
            **(data or {}),
            **(extra or {}),
        }

        if error:
            log_data["error"] = {"type": type(error).__name__, "message": str(error)}

        message = json.dumps(log_data, default=str, separators=(",", ":"))

        super().log(level, message)
        logging.getLogger().log(level, message)

    def log(self, level: int, msg: str, *args, **kwargs):
        if isinstance(msg, str) and not msg.startswith("{"):
            data = kwargs.pop("extra", {})
            error = kwargs.pop("exc_info", None)
            if error and isinstance(error, Exception):
                error = error
            elif error:
                error = None
            self._log_structured(level, msg, data, error, kwargs)
        else:
            super().log(level, msg, *args, **kwargs)

    def debug(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.DEBUG, event, extra=extra)

    def info(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.INFO, event, extra=extra)

    def warning(
        self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs
    ):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.WARNING, event, extra=extra)

    def error(
        self,
        event: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        *args,
        **kwargs,
    ):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.ERROR, event, data=extra, error=error)

    def critical(
        self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs
    ):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.CRITICAL, event, extra=extra)

    def exception(
        self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs
    ):
        extra = kwargs.pop("extra", {})
        extra.update(data or {})
        self._log_structured(logging.ERROR, event, exc_info=True, extra=extra)

    fatal = critical


def record_circuit_breaker_state(name: str, state: str, failure_count: int):
    """No-op stub for circuit breaker state recording."""
    pass


def structured_log(name) -> StructuredLogger:
    if isinstance(name, logging.Logger):
        name = name.name
    if not isinstance(name, str):
        name = str(name) if name is not None else "unknown"
    return StructuredLogger(name)
