
"""Logging configuration - re-exports from shared scripts directory.

The actual implementation lives at C:/Users/Samag/Scripts/logging_config.py
so it can be reused across multiple projects. This module adds that path
and re-exports all public symbols so existing imports continue to work.

Falls back to the local copy (logging_config_original.py) if the shared
file is not available (e.g. development on a different machine).
"""

import os
import sys

_SHARED_SCRIPTS_DIR = os.environ.get("SHARED_SCRIPTS_DIR",r"C:/Users/BABED2P/Documents/WORKSPACE/Scripts")
if _SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS_DIR)

try:
    from logging_config import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401
except ImportError:
    # Fallback to local copy when shared path is not available
    from utils.logging_config import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401