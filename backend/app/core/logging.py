"""Structured logging via structlog.

Import-safe: configure_logging() is idempotent and get_logger() returns a
structlog logger that works even before configuration is applied.
"""
from __future__ import annotations

import logging

import structlog

_configured = False


def configure_logging() -> None:
    """Configure structlog + stdlib logging for JSON-friendly structured output."""
    global _configured
    if _configured:
        return

    logging.basicConfig(format="%(message)s", level=logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None):
    """Return a structlog logger."""
    return structlog.get_logger(name)
