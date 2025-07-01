"""
Logging setup for Adelfa email client.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> None:
    """
    Set up application logging with both file and console handlers.
    
    Args:
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        log_file: Path to log file. If None, uses default location.
        console_output: Whether to output logs to console.
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create main logger
    logger = logging.getLogger("adelfa")
    logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        # Default log file location
        if sys.platform.startswith("linux"):
            log_dir = Path.home() / ".local" / "share" / "adelfa" / "logs"
        else:
            log_dir = Path.home() / ".adelfa" / "logs"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "adelfa.log"
    
    # Rotating file handler (max 10MB, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Log startup message
    logger.info("Adelfa Email Client - Logging initialized")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__).
        
    Returns:
        logging.Logger: Logger instance.
    """
    return logging.getLogger(f"adelfa.{name}") 