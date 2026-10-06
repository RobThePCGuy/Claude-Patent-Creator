"""
Performance monitoring and metrics tracking for the MCP server.

Provides decorators and utilities for tracking:
    - Request duration and latency (with percentiles)
    - Error rates and types
    - Operation counts
    - Resource usage

Key Components:
    PerformanceMetrics: Thread-safe metrics collector with p50/p95/p99
    track_performance: Decorator for automatic timing and error tracking
    OperationTimer: Context manager for sub-operation timing
    log_operation_result: Helper for structured result logging

Usage:
    from monitoring import track_performance, OperationTimer

    @track_performance
    def my_function(data: str) -> dict:
        with OperationTimer("parsing"):
            parsed = parse(data)
        with OperationTimer("processing"):
            result = process(parsed)
        return result

All metrics are thread-safe and include percentile calculations for
latency analysis.
"""

import functools
import inspect
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable

# Per-operation ring buffer size for latency samples.
_DURATION_RING_SIZE = 1024

try:
    from logging_config import get_logger
except ImportError:
    from mcp_server.logging_config import get_logger

logger = get_logger()


class PerformanceMetrics:
    """Thread-safe performance metrics collector."""

    def __init__(self):
        self._lock = threading.Lock()
        self._operation_counts = defaultdict(int)
        self._operation_durations: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=_DURATION_RING_SIZE)
        )
        self._error_counts = defaultdict(int)
        self._start_time = time.time()

    def record_operation(self, operation: str, duration_ms: float, success: bool = True):
        """Record an operation execution."""
        with self._lock:
            self._operation_counts[operation] += 1
            self._operation_durations[operation].append(duration_ms)
            if not success:
                self._error_counts[operation] += 1

    def record_error(self, operation: str, error_type: str):
        """Record an error occurrence."""
        with self._lock:
            error_key = f"{operation}:{error_type}"
            self._error_counts[error_key] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current performance statistics."""
        with self._lock:
            stats = {
                "uptime_seconds": time.time() - self._start_time,
                "operations": dict(self._operation_counts),
                "errors": dict(self._error_counts),
                "latency": {},
            }

            # Calculate latency percentiles
            for operation, durations in self._operation_durations.items():
                if durations:
                    sorted_durations = sorted(durations)
                    count = len(sorted_durations)
                    stats["latency"][operation] = {
                        "count": count,
                        "min": min(sorted_durations),
                        "max": max(sorted_durations),
                        "mean": sum(sorted_durations) / count,
                        "p50": sorted_durations[int(count * 0.5)],
                        "p95": (
                            sorted_durations[int(count * 0.95)]
                            if count > 1
                            else sorted_durations[0]
                        ),
                        "p99": (
                            sorted_durations[int(count * 0.99)]
                            if count > 1
                            else sorted_durations[0]
                        ),
                    }

            return stats

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._operation_counts.clear()
            self._operation_durations.clear()
            self._error_counts.clear()
            self._start_time = time.time()


# Global metrics instance
_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Get the global metrics instance."""
    return _metrics


def track_performance(operation_name: str, log_params: bool = True):
    """
    Decorator to track operation performance.

    Args:
        operation_name: Name of the operation for tracking
        log_params: Whether to log function parameters

    Example:
        @track_performance("search_patents")
        def search(query: str):
            # ... implementation
    """

    def decorator(func: Callable) -> Callable:
        # A sync wrapper around a coroutine function returns the un-awaited
        # coroutine, and MCPServer rejects it, so every call to the tool failed
        # (search_epo_patents, get_epo_patent, get_epo_patent_family).
        if inspect.iscoroutinefunction(func):
            return track_async_performance(operation_name, log_params)(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()

            # Prepare log context
            log_context: dict[str, Any] = {
                "operation": operation_name,
                "function": func.__name__,
            }

            # Optionally include parameters (sanitized)
            if log_params:
                log_context["args_count"] = len(args)
                # Only include kwargs keys, not values (avoid logging sensitive data)
                log_context["params"] = list(kwargs.keys())

            # Log operation start
            logger.info(f"{operation_name}_started", extra=log_context)

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Record success
                _metrics.record_operation(operation_name, duration_ms, success=True)

                # Log success
                logger.info(
                    f"{operation_name}_completed",
                    extra={**log_context, "duration_ms": round(duration_ms, 2), "success": True},
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Record failure
                _metrics.record_operation(operation_name, duration_ms, success=False)
                _metrics.record_error(operation_name, type(e).__name__)

                # Log failure
                logger.error(
                    f"{operation_name}_failed",
                    extra={
                        **log_context,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

                raise

        return wrapper

    return decorator


def track_async_performance(operation_name: str, log_params: bool = True):
    """
    Decorator to track async operation performance.

    Args:
        operation_name: Name of the operation for tracking
        log_params: Whether to log function parameters

    Example:
        @track_async_performance("async_search")
        async def search(query: str):
            # ... async implementation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()

            log_context: dict[str, Any] = {
                "operation": operation_name,
                "function": func.__name__,
            }

            if log_params:
                log_context["args_count"] = len(args)
                log_context["params"] = list(kwargs.keys())

            logger.info(f"{operation_name}_started", extra=log_context)

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                _metrics.record_operation(operation_name, duration_ms, success=True)

                logger.info(
                    f"{operation_name}_completed",
                    extra={**log_context, "duration_ms": round(duration_ms, 2), "success": True},
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                _metrics.record_operation(operation_name, duration_ms, success=False)
                _metrics.record_error(operation_name, type(e).__name__)

                logger.error(
                    f"{operation_name}_failed",
                    extra={
                        **log_context,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

                raise

        return wrapper

    return decorator


class OperationTimer:
    """Context manager for timing operations."""

    def __init__(self, operation_name: str, log_result: bool = True):
        self.operation_name = operation_name
        self.log_result = log_result
        self.start_time: float | None = None
        self.duration_ms: float | None = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.debug(f"{self.operation_name}_timer_started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        else:
            self.duration_ms = 0.0

        if exc_type is None:
            # Success
            _metrics.record_operation(self.operation_name, self.duration_ms, success=True)
            if self.log_result:
                logger.debug(
                    f"{self.operation_name}_timer_completed",
                    extra={"duration_ms": round(self.duration_ms, 2)},
                )
        else:
            # Failure
            _metrics.record_operation(self.operation_name, self.duration_ms, success=False)
            _metrics.record_error(self.operation_name, exc_type.__name__)
            if self.log_result:
                logger.error(
                    f"{self.operation_name}_timer_failed",
                    extra={
                        "duration_ms": round(self.duration_ms, 2),
                        "error_type": exc_type.__name__,
                    },
                )

        return False  # Don't suppress exceptions


def log_operation_result(operation: str, **metrics):
    """
    Log operation result with custom metrics.

    Args:
        operation: Operation name
        **metrics: Arbitrary metrics to log

    Example:
        log_operation_result("search", query_length=10, results_count=5)
    """
    logger.info(f"{operation}_result", extra={"operation": operation, **metrics})
