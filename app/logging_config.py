"""Logging configuration for TrashAlert API."""
import logging
import logging.handlers
import os
from pathlib import Path


# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
ACCESS_LOG_PATH = LOGS_DIR / "access.log"
ERROR_LOG_PATH = LOGS_DIR / "error.log"
APP_LOG_PATH = LOGS_DIR / "app.log"


def setup_logging():
    """
    Configure logging for the TrashAlert API.

    Sets up three log files:
    1. access.log - API request/response logs with timing
    2. error.log - Error logs with stack traces
    3. app.log - General application logs

    All logs use rotating file handlers (max 10MB, keep 5 backups)
    """
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Formatter for structured logs
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. Access log handler (INFO level)
    access_handler = logging.handlers.RotatingFileHandler(
        ACCESS_LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(detailed_formatter)
    access_handler.addFilter(lambda record: record.name == 'api.access')

    # 2. Error log handler (ERROR level only)
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)

    # 3. Application log handler (DEBUG and above)
    app_handler = logging.handlers.RotatingFileHandler(
        APP_LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(detailed_formatter)

    # Console handler for development (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)

    # Add all handlers to root logger
    root_logger.addHandler(access_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(console_handler)

    # Create specialized loggers
    access_logger = logging.getLogger('api.access')
    access_logger.setLevel(logging.INFO)

    app_logger = logging.getLogger('api.app')
    app_logger.setLevel(logging.DEBUG)

    return {
        'access': access_logger,
        'app': app_logger,
        'error': root_logger
    }


# Initialize loggers
loggers = setup_logging()
access_logger = loggers['access']
app_logger = loggers['app']
error_logger = loggers['error']
