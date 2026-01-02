"""
Monitoring and Observability Module for Agentics

Provides structured logging, performance metrics, and workflow observability
without impacting execution performance.
"""

import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict, deque
from functools import wraps
import weakref

logger = logging.getLogger(__name__)


class MetricsStore:
    """Thread-safe in-memory metrics store"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.lock = threading.RLock()

    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value

    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timer metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.timers[key].append(duration)
            # Keep only recent measurements
            if len(self.timers[key]) > self.max_history:
                self.timers[key] = self.timers[key][-self.max_history:]

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram value"""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)

    def get_metrics(self) -> Dict[str, Any]:
        """Get all current metrics"""
        with self.lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "timers": {k: self._summarize_timer(v) for k, v in self.timers.items()},
                "histograms": {k: self._summarize_histogram(v) for k, v in self.histograms.items()}
            }

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a unique key from name and labels"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _summarize_timer(self, durations: List[float]) -> Dict[str, Any]:
        """Summarize timer measurements"""
        if not durations:
            return {"count": 0}
        return {
            "count": len(durations),
            "avg": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
            "p95": sorted(durations)[int(len(durations) * 0.95)] if durations else None,
            "p99": sorted(durations)[int(len(durations) * 0.99)] if durations else None
        }

    def _summarize_histogram(self, values: deque) -> Dict[str, Any]:
        """Summarize histogram values"""
        if not values:
            return {"count": 0}
        values_list = list(values)
        return {
            "count": len(values_list),
            "avg": sum(values_list) / len(values_list),
            "min": min(values_list),
            "max": max(values_list),
            "current": values_list[-1] if values_list else None
        }


class StructuredLogger(logging.Logger):
    """Structured logging with consistent format"""

    def __init__(self, name: str):
        # Initialize the parent Logger class
        super().__init__(name)
        self.logger = logging.getLogger(name)

    def _log_structured(self, level: int, event: str, data: Optional[Dict[str, Any]] = None,
                       error: Optional[Exception] = None, extra: Optional[Dict[str, Any]] = None):
        """Log structured event with proper logging level"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": logging.getLevelName(level),
            "event": event,
            "component": self.name,
            **(data or {}),
            **(extra or {})
        }

        if error:
            log_data["error"] = {
                "type": type(error).__name__,
                "message": str(error)
            }

        message = json.dumps(log_data, default=str, separators=(',', ':'))

        # Use parent class logging method
        super().log(level, message)
        # Duplicate to root logger for pytest caplog visibility
        logging.getLogger().log(level, message)

    def log(self, level: int, msg: str, *args, **kwargs):
        """Override log method to support structured logging"""
        if isinstance(msg, str) and not msg.startswith('{'):
            # If it's not already JSON, treat it as an event
            data = kwargs.pop('extra', {})
            error = kwargs.pop('exc_info', None)
            if error and isinstance(error, Exception):
                error = error
            elif error:
                error = None
            self._log_structured(level, msg, data, error, kwargs)
        else:
            # If it's already JSON or another format, use parent
            super().log(level, msg, *args, **kwargs)

    def debug(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log debug event"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.DEBUG, event, extra=extra)

    def info(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log info event"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.INFO, event, extra=extra)

    def warning(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log warning event"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.WARNING, event, extra=extra)

    def error(self, event: str, data: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None, *args, **kwargs):
        """Log error event"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.ERROR, event, data=extra, error=error)

    def critical(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log critical event"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.CRITICAL, event, extra=extra)

    def exception(self, event: str, data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Log exception with traceback"""
        extra = kwargs.pop('extra', {})
        extra.update(data or {})
        self._log_structured(logging.ERROR, event, exc_info=True, extra=extra)

    # Alias for critical
    fatal = critical


class WorkflowTracker:
    """Track workflow execution progress and state"""

    def __init__(self):
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.completed_workflows: deque = deque(maxlen=100)  # Keep last 100
        self.workflow_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.lock = threading.RLock()

    def start_workflow(self, workflow_id: str, workflow_type: str, initial_data: Optional[Dict[str, Any]] = None):
        """Start tracking a workflow"""
        with self.lock:
            self.active_workflows[workflow_id] = {
                "type": workflow_type,
                "start_time": time.time(),
                "current_step": None,
                "steps_completed": [],
                "data": initial_data or {},
                "status": "running"
            }

    def update_workflow_step(self, workflow_id: str, step: str, step_data: Optional[Dict[str, Any]] = None):
        """Update current step in workflow"""
        with self.lock:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                workflow["current_step"] = step
                workflow["steps_completed"].append({
                    "step": step,
                    "timestamp": time.time(),
                    "data": step_data or {}
                })

    def complete_workflow(self, workflow_id: str, result: Optional[Dict[str, Any]] = None):
        """Mark workflow as completed"""
        with self.lock:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                workflow["end_time"] = time.time()
                workflow["duration"] = workflow["end_time"] - workflow["start_time"]
                workflow["status"] = "completed"
                workflow["result"] = result or {}

                # Move to completed
                self.completed_workflows.append(workflow)
                del self.active_workflows[workflow_id]

    def fail_workflow(self, workflow_id: str, error: Exception):
        """Mark workflow as failed"""
        with self.lock:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                workflow["end_time"] = time.time()
                workflow["duration"] = workflow["end_time"] - workflow["start_time"]
                workflow["status"] = "failed"
                workflow["error"] = {
                    "type": type(error).__name__,
                    "message": str(error)
                }

                # Move to completed (with failure status)
                self.completed_workflows.append(workflow)
                del self.active_workflows[workflow_id]

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a workflow"""
        with self.lock:
            if workflow_id in self.active_workflows:
                return dict(self.active_workflows[workflow_id])
            # Check completed workflows
            for workflow in self.completed_workflows:
                if workflow.get("id") == workflow_id:
                    return dict(workflow)
            return None

    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflows"""
        with self.lock:
            return [dict(w) for w in self.active_workflows.values()]

    def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get aggregated workflow metrics"""
        with self.lock:
            completed = list(self.completed_workflows)
            if not completed:
                return {"total_workflows": 0}

            total_duration = sum(w.get("duration", 0) for w in completed)
            successful = sum(1 for w in completed if w.get("status") == "completed")
            failed = sum(1 for w in completed if w.get("status") == "failed")

            return {
                "total_workflows": len(completed),
                "active_workflows": len(self.active_workflows),
                "success_rate": successful / len(completed) if completed else 0,
                "failure_rate": failed / len(completed) if completed else 0,
                "avg_duration": total_duration / len(completed) if completed else 0
            }


class PerformanceMonitor:
    """Monitor performance metrics without impacting execution"""

    def __init__(self):
        self.metrics = MetricsStore()
        self.logger = StructuredLogger("performance_monitor")
        self.workflow_tracker = WorkflowTracker()

    def time_execution(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Decorator to time function execution"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    self.metrics.record_timer(f"{name}_duration", duration, labels)
                    self.metrics.increment_counter(f"{name}_calls", labels=labels)
                    return result
                except Exception as e:
                    duration = time.perf_counter() - start_time
                    self.metrics.record_timer(f"{name}_error_duration", duration, labels)
                    self.metrics.increment_counter(f"{name}_errors", labels=labels)
                    raise e
            return wrapper
        return decorator

    def track_agent_execution(self, agent_name: str):
        """Track agent execution metrics"""
        return self.time_execution(f"agent_{agent_name}", {"agent": agent_name})

    def track_workflow_progress(self, workflow_id: str, workflow_type: str):
        """Track workflow execution"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.workflow_tracker.start_workflow(workflow_id, workflow_type)
                try:
                    result = func(*args, **kwargs)
                    self.workflow_tracker.complete_workflow(workflow_id, {"result": "success"})
                    return result
                except Exception as e:
                    self.workflow_tracker.fail_workflow(workflow_id, e)
                    raise e
            return wrapper
        return decorator

    def record_circuit_breaker_state(self, name: str, state: str, failure_count: int = 0):
        """Record circuit breaker state"""
        self.metrics.set_gauge(f"circuit_breaker_{name}_state",
                              1 if state == "open" else 0 if state == "half_open" else 2,
                              {"circuit_breaker": name})
        self.metrics.record_histogram(f"circuit_breaker_{name}_failures", failure_count,
                                    {"circuit_breaker": name})

    def get_monitoring_data(self) -> Dict[str, Any]:
        """Get all monitoring data"""
        return {
            "metrics": self.metrics.get_metrics(),
            "workflows": self.workflow_tracker.get_workflow_metrics(),
            "active_workflows": self.workflow_tracker.get_active_workflows()
        }


# Global monitoring instance
_monitor = PerformanceMonitor()

def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor"""
    return _monitor

def structured_log(name) -> StructuredLogger:
    if isinstance(name, logging.Logger):
        name = name.name
    if not isinstance(name, str):
        name = str(name) if name is not None else "unknown"
    return StructuredLogger(name)

# Convenience functions
def time_execution(name: str, labels: Optional[Dict[str, str]] = None):
    """Time execution decorator"""
    return _monitor.time_execution(name, labels)

def track_agent_execution(agent_name: str):
    """Track agent execution"""
    return _monitor.track_agent_execution(agent_name)

def track_workflow_progress(workflow_id: str, workflow_type: str):
    """Track workflow progress"""
    return _monitor.track_workflow_progress(workflow_id, workflow_type)

def record_circuit_breaker_state(name: str, state: str, failure_count: int = 0):
    """Record circuit breaker state"""
    _monitor.record_circuit_breaker_state(name, state, failure_count)

def get_monitoring_data() -> Dict[str, Any]:
    """Get all monitoring data"""
    return _monitor.get_monitoring_data()


# Import ServiceHealthMonitor from circuit_breaker for backward compatibility
from .circuit_breaker import ServiceHealthMonitor