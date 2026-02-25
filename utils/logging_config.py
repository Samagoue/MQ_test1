
"""Logging configuration - re-exports from shared scripts directory.

The actual implementation lives at /data/app/Scripts/logging_config.py
so it can be reused across multiple projects. This module adds that path
and re-exports all public symbols so existing imports continue to work.

Falls back to the local scripts/common/ copy if the shared path is not
available (e.g. development on a different machine).
"""

import os
import sys
from pathlib import Path

_SHARED_SCRIPTS_DIR = os.environ.get("SHARED_SCRIPTS_DIR", "/data/app/Scripts")
if _SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS_DIR)

try:
    from logging_config import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401
except ImportError:
    # Fallback to local scripts/common/ copy when shared path is not available
    _local_scripts = str(Path(__file__).parent.parent / "scripts" / "common")
    if _local_scripts not in sys.path:
        sys.path.insert(0, _local_scripts)
    from logging_config import setup_logging, get_logger, cleanup_old_logs, EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401

