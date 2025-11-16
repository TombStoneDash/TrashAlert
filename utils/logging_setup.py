"""
Centralized logging configuration for TrashAlert.

This module provides a consistent logging setup across all scripts.
Import and use setup_logging() at the start of each script.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    name: str = "trashalert",
    level: str = "INFO",
    log_dir: str = "logs",
    log_to_file: bool = True,
    log_to_console: bool = True,
    format_string: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up logging with both file and console handlers.

    Args:
        name: Logger name (typically script name or module name)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        log_to_file: Whether to write logs to file
        log_to_console: Whether to write logs to console
        format_string: Custom format string (uses default if None)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep

    Returns:
        Configured logger instance

    Example:
        >>> from utils.logging_setup import setup_logging
        >>> logger = setup_logging(__name__)
        >>> logger.info("Script started")
        >>> logger.debug("Debug information")
        >>> logger.error("Error occurred")
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Prevent duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

    # Default format
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string)

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Create log file name based on logger name
        log_file = log_path / f"{name}.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_logging_from_config(config: dict, script_name: str) -> logging.Logger:
    """
    Set up logging using configuration from cities.yaml.

    Args:
        config: Configuration dictionary (typically from cities.yaml)
        script_name: Name of the script/module requesting the logger

    Returns:
        Configured logger instance

    Example:
        >>> import yaml
        >>> with open('config/cities.yaml') as f:
        >>>     config = yaml.safe_load(f)
        >>> logger = setup_logging_from_config(config, 'fetch_osm_data')
    """
    log_config = config.get('logging', {})

    return setup_logging(
        name=script_name,
        level=log_config.get('level', 'INFO'),
        log_dir=log_config.get('log_dir', 'logs'),
        format_string=log_config.get('format'),
        max_bytes=log_config.get('max_bytes', 10485760),
        backup_count=log_config.get('backup_count', 5)
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger


# Quick setup function for simple scripts
def quick_setup(script_name: str = None, level: str = "INFO") -> logging.Logger:
    """
    Quick logging setup for simple scripts.

    Args:
        script_name: Name of the script (uses __name__ if None)
        level: Logging level

    Returns:
        Configured logger instance

    Example:
        >>> from utils.logging_setup import quick_setup
        >>> logger = quick_setup(__file__)
        >>> logger.info("Started processing")
    """
    if script_name is None:
        script_name = "trashalert"
    else:
        # Extract script name from file path if full path provided
        script_name = Path(script_name).stem

    return setup_logging(script_name, level=level)
