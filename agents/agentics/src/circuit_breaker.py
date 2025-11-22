"""
Circuit Breaker and Retry Utilities for Enhanced Error Recovery
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
import asyncio

from .monitoring import record_circuit_breaker_state, structured_log

monitor = structured_log(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """Circuit Breaker implementation for external service calls"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Exception = Exception, name: str = "CircuitBreaker",
                 fallback_strategy: Optional[Callable] = None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.fallback_strategy = fallback_strategy

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.success_count = 0
        self.next_attempt_time: Optional[datetime] = None

        monitor.info("circuit_breaker_initialized", data={"name": name, "threshold": failure_threshold, "timeout": recovery_timeout, "has_fallback": fallback_strategy is not None})

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        if self.state != CircuitBreakerState.OPEN:
            return False
        if self.next_attempt_time is None:
            return True
        return datetime.now() >= self.next_attempt_time

    def _record_success(self):
        """Record a successful call"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            monitor.info("circuit_breaker_success_half_open", data={"name": self.name, "success_count": self.success_count})
            # Could implement success threshold for half-open state
            self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0  # Reset failure count on success

        # Record state for monitoring
        record_circuit_breaker_state(self.name, self.state.value, self.failure_count)

    def _record_failure(self):
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitBreakerState.HALF_OPEN:
            monitor.warning("circuit_breaker_failure_half_open", data={"name": self.name})
            self._open_circuit()
        elif self.failure_count >= self.failure_threshold:
            monitor.warning("circuit_breaker_threshold_reached", data={"name": self.name, "failure_count": self.failure_count})
            self._open_circuit()

        # Record state for monitoring
        record_circuit_breaker_state(self.name, self.state.value, self.failure_count)

    def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.next_attempt_time = datetime.now() + timedelta(seconds=self.recovery_timeout)
        monitor.warning("circuit_breaker_opened", data={"name": self.name, "next_attempt_time": self.next_attempt_time.isoformat()})

        # Record state for monitoring
        record_circuit_breaker_state(self.name, self.state.value, self.failure_count)

    def _reset(self):
        """Reset the circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        monitor.info("circuit_breaker_reset", data={"name": self.name})

        # Record state for monitoring
        record_circuit_breaker_state(self.name, self.state.value, self.failure_count)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitBreakerState.OPEN:
            if not self._should_attempt_reset():
                # Use fallback strategy if available
                if self.fallback_strategy:
                    monitor.warning("circuit_breaker_open_using_fallback", data={"name": self.name})
                    try:
                        return self.fallback_strategy(*args, **kwargs)
                    except Exception as fallback_error:
                        monitor.error("circuit_breaker_fallback_failed", data={"name": self.name, "error": str(fallback_error)})
                        raise CircuitBreakerOpenException(f"CircuitBreaker '{self.name}' is OPEN and fallback failed")
                else:
                    raise CircuitBreakerOpenException(f"CircuitBreaker '{self.name}' is OPEN")

            monitor.info("circuit_breaker_attempt_reset", data={"name": self.name})
            self.state = CircuitBreakerState.HALF_OPEN

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""
        if self.state == CircuitBreakerState.OPEN:
            if not self._should_attempt_reset():
                # Use fallback strategy if available
                if self.fallback_strategy:
                    monitor.warning("circuit_breaker_open_using_fallback", data={"name": self.name})
                    try:
                        return await self.fallback_strategy(*args, **kwargs)
                    except Exception as fallback_error:
                        monitor.error("circuit_breaker_fallback_failed", data={"name": self.name, "error": str(fallback_error)})
                        raise CircuitBreakerOpenException(f"CircuitBreaker '{self.name}' is OPEN and fallback failed")
                else:
                    raise CircuitBreakerOpenException(f"CircuitBreaker '{self.name}' is OPEN")

            monitor.info("circuit_breaker_attempt_reset", data={"name": self.name})
            self.state = CircuitBreakerState.HALF_OPEN

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_attempt": self.next_attempt_time.isoformat() if self.next_attempt_time else None
        }


def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0,
                       jitter: bool = True) -> float:
    """Calculate exponential backoff delay with optional jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)

    if jitter:
        # Add random jitter (±25% of delay)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0.1, delay)  # Minimum 100ms delay


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0,
                      max_delay: float = 60.0, jitter: bool = True,
                      exceptions: tuple = (Exception,)):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        monitor.error("retry_all_attempts_failed", data={"max_attempts": max_attempts, "func_name": func.__name__, "error": str(e)})
                        raise e

                    delay = exponential_backoff(attempt, base_delay, max_delay, jitter)
                    monitor.warning("retry_attempt_failed", data={"attempt": attempt + 1, "func_name": func.__name__, "error": str(e), "retry_delay": delay})
                    time.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper
    return decorator


def retry_with_backoff_async(max_attempts: int = 3, base_delay: float = 1.0,
                           max_delay: float = 60.0, jitter: bool = True,
                           exceptions: tuple = (Exception,)):
    """Decorator for retrying async functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        monitor.error("retry_all_attempts_failed", data={"max_attempts": max_attempts, "func_name": func.__name__, "error": str(e)})
                        raise e

                    delay = exponential_backoff(attempt, base_delay, max_delay, jitter)
                    monitor.warning("retry_attempt_failed", data={"attempt": attempt + 1, "func_name": func.__name__, "error": str(e), "retry_delay": delay})
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper
    return decorator


class ServiceHealthMonitor:
    """Monitor health of external services and provide graceful degradation"""

    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.degradation_strategies: Dict[str, Callable] = {}

    def register_service(self, name: str, health_check: Callable[[], bool],
                        degradation_strategy: Optional[Callable] = None):
        """Register a service for health monitoring"""
        self.services[name] = {
            "health_check": health_check,
            "healthy": True,
            "last_check": None,
            "failure_count": 0
        }
        if degradation_strategy:
            self.degradation_strategies[name] = degradation_strategy

        monitor.info("service_registered", data={"service_name": name})

    def check_service_health(self, name: str) -> bool:
        """Check if a service is healthy"""
        if name not in self.services:
            return False

        service = self.services[name]
        try:
            is_healthy = service["health_check"]()
            service["healthy"] = is_healthy
            service["last_check"] = datetime.now()

            if not is_healthy:
                service["failure_count"] += 1
                monitor.warning("service_health_check_failed", data={"service_name": name, "failure_count": service['failure_count']})
            else:
                service["failure_count"] = 0
                if not service["healthy"]:  # Was unhealthy, now healthy
                    monitor.info("service_recovered", data={"service_name": name})

            return is_healthy
        except Exception as e:
            service["failure_count"] += 1
            service["healthy"] = False
            monitor.error("service_health_check_error", data={"service_name": name, "error": str(e)})
            return False

    def is_service_healthy(self, name: str) -> bool:
        """Check if service is currently considered healthy"""
        return self.services.get(name, {}).get("healthy", False)

    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all monitored services"""
        return {
            name: {
                "healthy": service["healthy"],
                "last_check": service["last_check"].isoformat() if service["last_check"] else None,
                "failure_count": service["failure_count"]
            }
            for name, service in self.services.items()
        }

    def attempt_graceful_degradation(self, service_name: str, *args, **kwargs) -> Any:
        """Attempt graceful degradation for a failed service"""
        if service_name in self.degradation_strategies:
            monitor.info("graceful_degradation_attempt", data={"service_name": service_name})
            try:
                return self.degradation_strategies[service_name](*args, **kwargs)
            except Exception as e:
                monitor.error("graceful_degradation_failed", data={"service_name": service_name, "error": str(e)})
                raise e
        else:
            monitor.warning("no_degradation_strategy", data={"service_name": service_name})
            raise RuntimeError(f"Service '{service_name}' is unavailable and no degradation strategy exists")


# Global instances
circuit_breakers: Dict[str, CircuitBreaker] = {}
health_monitor = ServiceHealthMonitor()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker instance"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    else:
        # Update existing circuit breaker with new kwargs if provided
        cb = circuit_breakers[name]
        for key, value in kwargs.items():
            if hasattr(cb, key):
                setattr(cb, key, value)
    return circuit_breakers[name]


def get_health_monitor() -> ServiceHealthMonitor:
    """Get the global health monitor instance"""
    return health_monitor