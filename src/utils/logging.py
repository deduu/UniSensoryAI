"""Structured logging configuration for UniSensoryAI.

Configures structlog with JSON rendering for production and
human-readable console output for development.

Usage::

    from src.utils.logging import configure_logging, get_logger

    configure_logging(json_output=False)  # Dev mode
    logger = get_logger(__name__)
    logger.info("document_processed", job_id="abc", duration_ms=150)
"""

import logging
import sys
from typing import Optional

import structlog


def configure_logging(
    json_output: bool = True,
    log_level: str = "INFO",
    module_name: Optional[str] = None,
) -> None:
    """Configure structlog with processors, renderer, and stdlib integration.

    This sets up structlog to:
    - Add timestamps, log level, and logger name to all events.
    - Render as JSON in production (``json_output=True``) or as colored
      console output in development (``json_output=False``).
    - Integrate with stdlib logging so existing ``logging.getLogger()``
      calls are captured and formatted consistently.

    Args:
        json_output: If True, render logs as JSON. If False, use console renderer.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        module_name: Optional module name filter for stdlib logging.
    """
    # Shared processors for both structlog and stdlib
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog's formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Apply to root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Reduce noise from third-party loggers
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger bound to a module name.

    This is a convenience wrapper that returns a properly typed
    structlog BoundLogger. Use this instead of ``logging.getLogger()``.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)
