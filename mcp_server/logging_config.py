"""
Structured logging configuration for MCP server.

All logs go to stderr to maintain MCP protocol compliance (stdout is reserved for JSON-RPC).
Uses JSON formatting for production observability and log aggregation.
"""

import json
import logging
import sys
from collections.abc import MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)  # type: ignore[attr-defined]

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        # Add color to level name
        level_color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]

        # Base message
        message = f"{timestamp} {level_color}{record.levelname:8s}{reset} [{record.module}:{record.lineno}] {record.getMessage()}"

        # Add extra fields if present
        if hasattr(record, "extra_data") and record.extra_data:  # type: ignore[attr-defined]
            extra_str = " | ".join(f"{k}={v}" for k, v in record.extra_data.items())  # type: ignore[attr-defined]
            message += f" | {extra_str}"

        # Add exception if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


class StructuredLogger(logging.LoggerAdapter):
    """Logger adapter that supports extra data."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """Process log message and add extra data."""
        # Extract extra data from kwargs
        extra_data = kwargs.pop("extra", {})

        # Store in a way that formatters can access
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        kwargs["extra"]["extra_data"] = extra_data

        return msg, kwargs


class _CurrentStderrHandler(logging.StreamHandler):
    """Writes to whatever sys.stderr is at emit time.

    A plain StreamHandler keeps the stream it was created with. The CLI
    imports the server stack under contextlib.redirect_stderr (to keep a
    failed import quiet), so a handler made then kept writing into that
    throwaway buffer: every progress line of a 35-minute index build vanished
    and setup looked frozen.
    """

    @property  # type: ignore[override]
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value):
        pass


def setup_logging(
    level: str = "INFO", format_type: str = "human", log_file: Optional[Path] = None
) -> StructuredLogger:
    """
    Configure structured logging to stderr.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" for production, "human" for development
        log_file: Optional file path for log output

    Returns:
        Configured structured logger
    """
    # Get or create logger
    logger = logging.getLogger("claude-patent-creator")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Choose formatter
    formatter = StructuredFormatter() if format_type == "json" else HumanReadableFormatter()

    # Create stderr handler (required for MCP protocol)
    stderr_handler = _CurrentStderrHandler()
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    # Optional file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())  # Always JSON for files
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Wrap in adapter
    return StructuredLogger(logger, {})


# Global logger instance
_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        # Read from environment variables
        import os

        log_level = os.environ.get("PATENT_LOG_LEVEL", "INFO")
        format_type = os.environ.get(
            "PATENT_LOG_FORMAT", "json"
        )  # Use JSON by default for MCP compatibility

        _logger = setup_logging(level=log_level, format_type=format_type)

    return _logger


# Convenience function for quick logging
logger = get_logger()
