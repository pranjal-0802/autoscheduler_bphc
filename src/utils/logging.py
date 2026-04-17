"""
Logging configuration for the scheduler.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_LOGS_DIR: Optional[Path] = None
_LOG_FILE_HANDLER: Optional[logging.FileHandler] = None


def setup_logging(logs_dir: str = "logs", level: int = logging.INFO) -> None:
    """
    Set up logging configuration.

    Creates a logs directory and configures logging to write to both
    console and a date-stamped log file.

    Args:
        logs_dir: Directory to store log files.
        level: Logging level (default: INFO).
    """
    global _LOGS_DIR, _LOG_FILE_HANDLER

    _LOGS_DIR = Path(logs_dir)
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_filename = datetime.now().strftime("%Y-%m-%d") + ".log"
    log_file_path = _LOGS_DIR / log_filename

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    _LOG_FILE_HANDLER = logging.FileHandler(log_file_path, encoding="utf-8")
    _LOG_FILE_HANDLER.setLevel(level)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _LOG_FILE_HANDLER.setFormatter(file_format)
    root_logger.addHandler(_LOG_FILE_HANDLER)

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    root_logger.info(f"Logging initialized. Log file: {log_file_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
