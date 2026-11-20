"""Application logging configuration.

Provides a standard way to initialize and retrieve loggers with consistent
formatting, an optional timestamped log file, and console output.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_level: str = "INFO",
                  log_to_file: bool = True,
                  log_dir: str = "./logs/",
                  console_output: bool = True) -> logging.Logger:
    """Configure the root logger for the application.

    Replaces any existing root handlers. The console handler respects
    `log_level`, while the file handler always captures DEBUG and above.

    Args:
        log_level: Minimum level for console output: "DEBUG", "INFO",
            "WARNING", "ERROR", or "CRITICAL". Unknown values fall back to "INFO".
        log_to_file: Whether to write logs to a timestamped file in `log_dir`.
            Pass False on Databricks.
        log_dir: Directory for log files. Created if it does not exist.
        console_output: Whether to print logs to stdout.

    Returns:
        The configured root logger.
    """

    log_level_int = _get_log_level(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers (if any)
    root_logger.handlers.clear()

    # Define format (Fixed the syntax error in the format string)
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level_int)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_path / f"{timestamp}.log"

        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {log_file}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return the logger with the given name.

    Args:
        name: Logger name, typically `__name__` of the calling module.

    Returns:
        The named logger. It uses the handlers set by `setup_logging`.
    """
    return logging.getLogger(name)


def _get_log_level(log_level: str = "INFO") -> int:
    """Convert a level name to its `logging` integer constant.

    Args:
        log_level: Level name, case-insensitive.

    Returns:
        The matching constant (e.g. `logging.INFO`), or `logging.INFO` if unknown.
    """
    levels = {
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    return levels.get(log_level.upper(), logging.INFO)