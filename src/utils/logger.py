"""Logging configuration and utilities."""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache

from rich.console import Console
from rich.logging import RichHandler

from ..config.settings import get_settings


def setup_logging() -> None:
    """Configure application-wide logging."""
    settings = get_settings()

    # Create log file path with timestamp
    log_file = settings.paths.logs_dir / f"app_{datetime.now():%Y%m%d}.log"
    settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with Rich formatting
    console_handler = RichHandler(
        console=Console(stderr=True, width=160),
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )
    console_handler.setLevel(settings.log_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger.addHandler(console_handler)

    # File handler (best effort; fallback to console-only)
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)
    except Exception as exc:  # pragma: no cover - defensive
        root_logger.warning("File logging disabled (%s)", exc)

    # Suppress noisy third-party loggers
    for logger_name in ["httpx", "httpcore", "chromadb", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


@lru_cache(maxsize=32)
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Initialize logging on module import
setup_logging()
