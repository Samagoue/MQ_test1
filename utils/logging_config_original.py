"""Logging configuration for the MQ CMDB system.

Provides dual-output logging: user-friendly console output (preserving emoji indicators)
and structured file output with timestamps, levels, and rotation.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


class EmojiFormatter(logging.Formatter):
    """Console formatter that preserves emoji-rich output style."""

    def format(self, record):
        # For INFO, print message as-is (preserves existing emoji output)
        if record.levelno == logging.INFO:
            return record.getMessage()
        # For WARNING, prefix with warning symbol if not already present
        msg = record.getMessage()
        if record.levelno == logging.WARNING:
            if not msg.startswith(('\u26a0', '!')):
                msg = f"\u26a0 {msg}"
            return msg
        # For ERROR/CRITICAL, prefix with cross mark if not already present
        if record.levelno >= logging.ERROR:
            if not msg.startswith(('\u2717', '\u2718', '\u2716')):
                msg = f"\u2717 {msg}"
            return msg
        # For DEBUG, prefix with dim indicator
        if record.levelno == logging.DEBUG:
            return f"  [DEBUG] {msg}"
        return msg


def setup_logging(verbose=False, log_dir=None, log_prefix="mqcmdb"):
    """
    Initialize the dual-output logging system.

    Args:
        verbose: If True, set console handler to DEBUG level.
        log_dir: Directory for log files. Defaults to Config.LOGS_DIR.
        log_prefix: Prefix for log filenames.

    Returns:
        The configured root logger for the application.
    """
    logger = logging.getLogger("mqcmdb")

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(EmojiFormatter())
    logger.addHandler(console_handler)

    # --- File handler ---
    if log_dir is None:
        # Import here to avoid circular imports
        from config.settings import Config
        log_dir = Config.LOGS_DIR

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{log_prefix}_{timestamp}.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name):
    """
    Get a child logger under the mqcmdb hierarchy.

    Args:
        name: Module name (e.g., "orchestrator", "generator.application").

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(f"mqcmdb.{name}")


def cleanup_old_logs(log_dir=None, retention_days=None):
    """
    Remove log files older than retention_days.

    Args:
        log_dir: Directory containing log files. Defaults to Config.LOGS_DIR.
        retention_days: Max age in days. Defaults to Config.LOG_RETENTION_DAYS.
    """
    if log_dir is None or retention_days is None:
        from config.settings import Config
        if log_dir is None:
            log_dir = Config.LOGS_DIR
        if retention_days is None:
            retention_days = Config.LOG_RETENTION_DAYS

    log_dir = Path(log_dir)
    if not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    for log_file in log_dir.glob("*.log*"):
        try:
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                log_file.unlink()
        except OSError:
            pass
