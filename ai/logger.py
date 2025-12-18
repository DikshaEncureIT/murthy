"""
Centralized Logger Class

Provides a centralized logging utility with RotatingFileHandler for the application.
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class AppLogger:
    """
    Centralized logger class for the application with RotatingFileHandler.
    Handles all logging configuration with support for both console and file logging.
    """

    _configured = False

    @classmethod
    def configure(cls, log_level: Optional[str] = None, log_file: Optional[str] = None) -> None:
        """
        Configure the global logging settings once.

        Features:
        - RotatingFileHandler: Automatically rotates log files at 10MB
        - Dual handlers: Console (INFO+) and File (DEBUG+)
        - Environment-based configuration via LOG_FILE and LOG_LEVEL

        Args:
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file (str): Path to log file
        """
        if cls._configured:
            return

        # Read from environment variables with defaults
        log_file = log_file or os.getenv("LOG_FILE", "/logs/backend.log")
        log_level = log_level or os.getenv("LOG_LEVEL", "INFO").upper()

        # Create log directory if it doesn't exist
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        except PermissionError:
            # Fallback to local logs directory if /logs is not accessible
            log_file = "../logs/backend.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Detailed log format matching existing format
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))

        # Console handler - shows INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(detailed_formatter)

        # File handler with rotation - saves DEBUG and above
        # Rotates at 10MB, keeps 5 backup files
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)

        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        cls._configured = True

    @classmethod
    def get_logger(cls, file_path: str) -> logging.Logger:
        """
        Get a logger for a specific module.

        Args:
            file_path (str): Module file path (use __file__)

        Returns:
            logging.Logger: Configured logger instance with module name
        """
        # Ensure logging is configured
        if not cls._configured:
            cls.configure()

        # Extract module name from file path
        module_name = Path(file_path).stem
        return logging.getLogger(module_name)
