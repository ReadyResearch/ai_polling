"""Structured logging setup for AI Polling pipeline."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logger(
    name: str = "ai_polling",
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """Set up structured logging for the pipeline.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file to write logs to
        format_string: Custom format string
        
    Returns:
        Configured logger instance
    """
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Default format
    if format_string is None:
        format_string = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    
    formatter = logging.Formatter(format_string)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "ai_polling") -> logging.Logger:
    """Get existing logger or create a new one."""
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set it up with defaults
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


def log_extraction_start(logger: logging.Logger, file_path: Path, attempt: int = 1) -> None:
    """Log extraction start."""
    logger.info(f"Starting extraction: {file_path.name} (attempt {attempt})")


def log_extraction_success(logger: logging.Logger, file_path: Path, record_count: int) -> None:
    """Log successful extraction."""
    logger.info(f"✅ Extracted {record_count} records from {file_path.name}")


def log_extraction_failure(logger: logging.Logger, file_path: Path, error: Exception) -> None:
    """Log extraction failure."""
    logger.error(f"❌ Failed to extract from {file_path.name}: {error}")


def log_validation_results(logger: logging.Logger, valid_count: int, invalid_count: int) -> None:
    """Log validation results."""
    total = valid_count + invalid_count
    if invalid_count > 0:
        logger.warning(f"Validation: {valid_count}/{total} records valid, {invalid_count} invalid")
    else:
        logger.info(f"✅ All {valid_count} records passed validation")


def log_cache_hit(logger: logging.Logger, file_path: Path) -> None:
    """Log cache hit."""
    logger.debug(f"📦 Using cached data for {file_path.name}")


def log_cache_miss(logger: logging.Logger, file_path: Path) -> None:
    """Log cache miss."""
    logger.debug(f"🔄 Cache miss for {file_path.name}, extracting fresh data")


def log_rate_limit_pause(logger: logging.Logger, delay: float) -> None:
    """Log rate limiting pause."""
    logger.info(f"⏱️  Rate limiting: pausing for {delay:.1f} seconds")