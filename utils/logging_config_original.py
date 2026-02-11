"""Logging configuration for the MQ CMDB system.

Provides dual-output logging: user-friendly console output (preserving emoji indicators)
and structured file output with timestamps, levels, and rotation.

Includes a built-in ASCII art text generator and customizable startup banner.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Built-in ASCII Art Font  (6 rows per character, variable width)
# ──────────────────────────────────────────────────────────────────────────────
# Each character maps to a list of 6 strings (one per row).
# Uses Unicode block characters: █ ▀ ▄ ░
#
_FONT = {
    "A": [
        " ██████╗ ",
        "██╔══██╗",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ],
    "B": [
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔══██╗",
        "██████╔╝",
        "╚═════╝ ",
    ],
    "C": [
        " ██████╗",
        "██╔════╝",
        "██║     ",
        "██║     ",
        "╚██████╗",
        " ╚═════╝",
    ],
    "D": [
        "██████╗ ",
        "██╔══██╗",
        "██║  ██║",
        "██║  ██║",
        "██████╔╝",
        "╚═════╝ ",
    ],
    "E": [
        "███████╗",
        "██╔════╝",
        "█████╗  ",
        "██╔══╝  ",
        "███████╗",
        "╚══════╝",
    ],
    "F": [
        "███████╗",
        "██╔════╝",
        "█████╗  ",
        "██╔══╝  ",
        "██║     ",
        "╚═╝     ",
    ],
    "G": [
        " ██████╗ ",
        "██╔════╝ ",
        "██║  ███╗",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "H": [
        "██╗  ██╗",
        "██║  ██║",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ],
    "I": [
        "██╗",
        "██║",
        "██║",
        "██║",
        "██║",
        "╚═╝",
    ],
    "J": [
        "     ██╗",
        "     ██║",
        "     ██║",
        "██   ██║",
        "╚█████╔╝",
        " ╚════╝ ",
    ],
    "K": [
        "██╗  ██╗",
        "██║ ██╔╝",
        "█████╔╝ ",
        "██╔═██╗ ",
        "██║  ██╗",
        "╚═╝  ╚═╝",
    ],
    "L": [
        "██╗     ",
        "██║     ",
        "██║     ",
        "██║     ",
        "███████╗",
        "╚══════╝",
    ],
    "M": [
        "███╗   ███╗",
        "████╗ ████║",
        "██╔████╔██║",
        "██║╚██╔╝██║",
        "██║ ╚═╝ ██║",
        "╚═╝     ╚═╝",
    ],
    "N": [
        "███╗   ██╗",
        "████╗  ██║",
        "██╔██╗ ██║",
        "██║╚██╗██║",
        "██║ ╚████║",
        "╚═╝  ╚═══╝",
    ],
    "O": [
        " ██████╗ ",
        "██╔═══██╗",
        "██║   ██║",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "P": [
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔═══╝ ",
        "██║     ",
        "╚═╝     ",
    ],
    "Q": [
        " ██████╗ ",
        "██╔═══██╗",
        "██║   ██║",
        "██║▄▄ ██║",
        "╚██████╔╝",
        " ╚══▀▀═╝ ",
    ],
    "R": [
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔══██╗",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ],
    "S": [
        "███████╗",
        "██╔════╝",
        "███████╗",
        "╚════██║",
        "███████║",
        "╚══════╝",
    ],
    "T": [
        "████████╗",
        "╚══██╔══╝",
        "   ██║   ",
        "   ██║   ",
        "   ██║   ",
        "   ╚═╝   ",
    ],
    "U": [
        "██╗   ██╗",
        "██║   ██║",
        "██║   ██║",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "V": [
        "██╗   ██╗",
        "██║   ██║",
        "██║   ██║",
        "╚██╗ ██╔╝",
        " ╚████╔╝ ",
        "  ╚═══╝  ",
    ],
    "W": [
        "██╗    ██╗",
        "██║    ██║",
        "██║ █╗ ██║",
        "██║███╗██║",
        "╚███╔███╔╝",
        " ╚══╝╚══╝ ",
    ],
    "X": [
        "██╗  ██╗",
        "╚██╗██╔╝",
        " ╚███╔╝ ",
        " ██╔██╗ ",
        "██╔╝ ██╗",
        "╚═╝  ╚═╝",
    ],
    "Y": [
        "██╗   ██╗",
        "╚██╗ ██╔╝",
        " ╚████╔╝ ",
        "  ╚██╔╝  ",
        "   ██║   ",
        "   ╚═╝   ",
    ],
    "Z": [
        "███████╗",
        "╚══███╔╝",
        "  ███╔╝ ",
        " ███╔╝  ",
        "███████╗",
        "╚══════╝",
    ],
    "0": [
        " ██████╗ ",
        "██╔═████╗",
        "██║██╔██║",
        "████╔╝██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ],
    "1": [
        " ██╗",
        "███║",
        "╚██║",
        " ██║",
        " ██║",
        " ╚═╝",
    ],
    "2": [
        "██████╗ ",
        "╚════██╗",
        " █████╔╝",
        "██╔═══╝ ",
        "███████╗",
        "╚══════╝",
    ],
    "3": [
        "██████╗ ",
        "╚════██╗",
        " █████╔╝",
        " ╚═══██╗",
        "██████╔╝",
        "╚═════╝ ",
    ],
    "4": [
        "██╗  ██╗",
        "██║  ██║",
        "███████║",
        "╚════██║",
        "     ██║",
        "     ╚═╝",
    ],
    "5": [
        "███████╗",
        "██╔════╝",
        "███████╗",
        "╚════██║",
        "███████║",
        "╚══════╝",
    ],
    "6": [
        " ██████╗",
        "██╔════╝",
        "██████╗ ",
        "██╔══██╗",
        "╚█████╔╝",
        " ╚════╝ ",
    ],
    "7": [
        "███████╗",
        "╚════██║",
        "    ██╔╝",
        "   ██╔╝ ",
        "   ██║  ",
        "   ╚═╝  ",
    ],
    "8": [
        " █████╗ ",
        "██╔══██╗",
        "╚█████╔╝",
        "██╔══██╗",
        "╚█████╔╝",
        " ╚════╝ ",
    ],
    "9": [
        " █████╗ ",
        "██╔══██╗",
        "╚██████║",
        " ╚═══██║",
        " █████╔╝",
        " ╚════╝ ",
    ],
    " ": [
        "   ",
        "   ",
        "   ",
        "   ",
        "   ",
        "   ",
    ],
    "-": [
        "      ",
        "      ",
        "█████╗",
        "╚════╝",
        "      ",
        "      ",
    ],
    ".": [
        "   ",
        "   ",
        "   ",
        "   ",
        "██╗",
        "╚═╝",
    ],
    "_": [
        "        ",
        "        ",
        "        ",
        "        ",
        "████████",
        "╚═══════",
    ],
}

# Number of rows in the font
_FONT_ROWS = 6


def generate_ascii_art(text: str) -> List[str]:
    """
    Generate ASCII art from a text string using the built-in block font.

    Supported characters: A-Z, 0-9, space, dash, period, underscore.
    Unsupported characters are silently skipped.

    Args:
        text: The text to render (case-insensitive).

    Returns:
        A list of strings, one per row of the rendered text.

    Example:
        >>> lines = generate_ascii_art("MQ")
        >>> for line in lines:
        ...     print(line)
    """
    text = text.upper()
    rows = [""] * _FONT_ROWS
    for ch in text:
        glyph = _FONT.get(ch)
        if glyph is None:
            continue
        for i in range(_FONT_ROWS):
            rows[i] += glyph[i]
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Default ASCII Banner Configuration
# ──────────────────────────────────────────────────────────────────────────────
# Override any of these keys when calling setup_logging(banner_config={...})
#
# Two ways to specify the art:
#   1. "art": [list of pre-made art lines]    - use your own ASCII art
#   2. "art_text": "MY TEXT"                  - auto-generate from built-in font
#
# If both are provided, "art_text" takes priority.
#
DEFAULT_BANNER_CONFIG = {
    "enabled": True,
    "art_text": "LOG",
    "art": [],
    "title": "",
    "version": "",
    "subtitle": "",
    "border_char": "=",
    "border_width": 70,
    "show_timestamp": True,
    "show_log_path": True,
}


class EmojiFormatter(logging.Formatter):
    """Console formatter that preserves emoji-rich output style."""

    def format(self, record):
        if record.levelno == logging.INFO:
            return record.getMessage()
        msg = record.getMessage()
        if record.levelno == logging.WARNING:
            if not msg.startswith(('\u26a0', '!')):
                msg = f"\u26a0 {msg}"
            return msg
        if record.levelno >= logging.ERROR:
            if not msg.startswith(('\u2717', '\u2718', '\u2716')):
                msg = f"\u2717 {msg}"
            return msg
        if record.levelno == logging.DEBUG:
            return f"  [DEBUG] {msg}"
        return msg


def _add_text_lines(content_lines: list, text: str, indent: str = "        "):
    """Split a string on newlines, expand tabs, and append each line."""
    for line in text.split('\n'):
        line = line.expandtabs(8)
        content_lines.append(f"{indent}{line}")


def _build_banner(config: Dict, log_file_path: Optional[str] = None) -> str:
    """
    Build the ASCII banner string with a Unicode box border.

    If config["art_text"] is provided, the art is auto-generated.
    Otherwise config["art"] (a list of pre-made lines) is used.

    Subtitle and title may contain newlines to produce multi-line sections.

    Uses box-drawing characters: ╔ ═ ╗ ║ ╚ ╝
    """
    # Collect all content lines first
    content_lines = []

    # ASCII art - auto-generate from text or use provided lines
    if config.get("art_text"):
        art_lines = generate_ascii_art(config["art_text"])
        for art_line in art_lines:
            content_lines.append(f"       {art_line}")
    elif config.get("art"):
        for art_line in config["art"]:
            content_lines.append(f"  {art_line}")

    content_lines.append("")

    if config.get("title"):
        _add_text_lines(content_lines, config["title"])

    if config.get("version"):
        content_lines.append(f"        Version {config['version']}")

    if config.get("subtitle"):
        _add_text_lines(content_lines, config["subtitle"])

    content_lines.append("")

    if config.get("show_timestamp"):
        content_lines.append(f"        Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if config.get("show_log_path") and log_file_path:
        content_lines.append(f"        Log:     {log_file_path}")

    # Calculate inner width: use config width or expand to fit longest line
    max_content = max((len(line) for line in content_lines), default=0)
    inner_width = max(config["border_width"], max_content + 4)

    # Build the box
    top_border    = f"    ╔{'═' * inner_width}╗"
    bottom_border = f"    ╚{'═' * inner_width}╝"
    empty_line    = f"    ║{' ' * inner_width}║"

    def box_line(text):
        return f"    ║{text.ljust(inner_width)}║"

    lines = ["", top_border, empty_line]
    for content in content_lines:
        if content == "":
            lines.append(empty_line)
        else:
            lines.append(box_line(content))
    lines.extend([empty_line, bottom_border, ""])
    return "\n".join(lines)


def setup_logging(verbose=False, log_dir=None, log_prefix="mqcmdb",
                  banner_config: Optional[Dict] = None):
    """
    Initialize the dual-output logging system.

    Args:
        verbose: If True, set console handler to DEBUG level.
        log_dir: Directory for log files. Defaults to Config.LOGS_DIR.
        log_prefix: Prefix for log filenames.
        banner_config: Dict to override banner defaults. Examples:
            {"art_text": "MY APP"}          - auto-generate art from text
            {"art": [lines], "title": "X"}  - use pre-made art
            {"enabled": False}              - suppress the banner

    Returns:
        The configured root logger for the application.
    """
    logger = logging.getLogger("mqcmdb")

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

    # --- Banner ---
    cfg = dict(DEFAULT_BANNER_CONFIG)
    if banner_config:
        cfg.update(banner_config)

    if cfg["enabled"]:
        banner = _build_banner(cfg, log_file_path=str(log_file))
        logger.info(banner)

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
