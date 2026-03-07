
"""Logging configuration - re-exports from shared scripts directory.

The actual implementation lives in a shared scripts directory (configured
via the SHARED_SCRIPTS_DIR environment variable) so it can be reused
across multiple projects. This module adds that path and re-exports all
public symbols so existing imports continue to work.

Falls back to the local copy (logging_config_original.py) if the shared
file is not available (e.g. development on a different machine).
"""

import os
import sys

_CANDIDATE_DIRS = list(filter(None, [
    os.environ.get("SHARED_SCRIPTS_DIR"),            # explicit override (any platform)
    r"C:\Users\BABED2P\Documents\WORKSPACE\Scripts",  # Windows dev machine
    "/data/app/Scripts",                              # production server
]))
# Add in reverse so the highest-priority entry ends up at sys.path[0]
for _dir in reversed(_CANDIDATE_DIRS):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

try:
    from logging_config import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401
except ImportError:
    # Fallback to local copy when shared path is not available
    from utils.logging_config_original import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401



