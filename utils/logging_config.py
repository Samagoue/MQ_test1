# -*- coding: utf-8 -*-
"""Logging re-exports via ea_shared (single source of truth in shared scripts)."""

from ea_shared import setup_logging, get_logger, cleanup_old_logs  # noqa: F401

# Additional symbols that some callers import
try:
    from logging_config import EmojiFormatter, DEFAULT_BANNER_CONFIG, generate_ascii_art  # noqa: F401
except ImportError:
    pass
