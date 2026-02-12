
"""Common utility functions for the MQ CMDB system."""

import sys
import re
import hashlib


def setup_utf8_output():
    """Configure system to handle UTF-8 output properly."""
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')


def safe_print(text: str):
    """
    Safely print text, handling encoding issues gracefully.
 
 
    Args:
        text: String to print
    """
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)


def sanitize_id(name: str) -> str:
    """
    Convert a name into a valid GraphViz identifier.
 
 
    Rules:
    - Replace spaces and special chars with underscores
    - Remove any remaining invalid characters
    - Ensure it starts with a letter or underscore
 
 
    Args:
        name: Original name string
 
 
    Returns:
        Sanitized identifier suitable for GraphViz
    """
    if not name:
        return "unknown"
 
 
    # Replace spaces and common special chars with underscores
    sanitized = re.sub(r'[\s\-\.\(\)\[\]\{\}\/\\:;,<>!@#$%^&*+=|~`"\'?]+', '_', name)
 
 
    # Remove any remaining non-alphanumeric characters except underscores
    sanitized = re.sub(r'[^\w]', '', sanitized)
 
 
    # Ensure it starts with a letter or underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
 
 
    # Handle empty result - use deterministic hash (hashlib) instead of
    # Python's built-in hash() which is randomized per session
    if not sanitized:
        # MD5 is sufficient for generating a short identifier (not for security)
        hash_val = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
        sanitized = 'node_' + hash_val

    return sanitized


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate text to maximum length, adding ellipsis if needed.
 
    Args:
        text: Text to truncate
        max_length: Maximum length (default: 50)
 
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'


def normalize_string(text: str) -> str:
    """
    Normalize string for comparison (lowercase, stripped, collapsed whitespace).
 
 
    Args:
        text: String to normalize
 
 
    Returns:
        Normalized string
    """
    if not text:
        return ''
    return ' '.join(str(text).strip().lower().split())


def format_count(count: int) -> str:
    """
    Format count with thousands separators.
 
 
    Args:
        count: Integer count
 
 
    Returns:
        Formatted string (e.g., "1,234")
    """
    return f"{count:,}"


def get_percentage(part: int, total: int, decimals: int = 1) -> str:
    """
    Calculate and format percentage.
 
 
    Args:
        part: Part value
        total: Total value
        decimals: Number of decimal places (default: 1)
 
 
    Returns:
        Formatted percentage string (e.g., "25.5%")
    """
    if total == 0:
        return "0.0%"
    percentage = (part / total) * 100
    return f"{percentage:.{decimals}f}%"


def create_table_row(columns: list, widths: list = None) -> str:
    """
    Create a formatted table row.
 
 
    Args:
        columns: List of column values
        widths: List of column widths (optional)
 
 
    Returns:
        Formatted row string
    """
    if not widths:
        widths = [20] * len(columns)
 
 
    row_parts = []
    for col, width in zip(columns, widths):
        col_str = str(col)
        if len(col_str) > width:
            col_str = col_str[:width-3] + '...'
        row_parts.append(col_str.ljust(width))
 
 
    return ' | '.join(row_parts)


def create_separator(total_width: int, char: str = '-') -> str:
    """
    Create a separator line.
 
 
    Args:
        total_width: Width of the separator
        char: Character to use (default: '-')
 
 
    Returns:
        Separator string
    """
    return char * total_width


def validate_file_exists(filepath, file_type: str = "file") -> bool:
    """
    Validate that a file exists and print appropriate message.
 
 
    Args:
        filepath: Path to file
        file_type: Type description for error message
 
 
    Returns:
        True if file exists, False otherwise
    """
    from pathlib import Path
 
 
    path = Path(filepath)
    if not path.exists():
        safe_print(f"✗ ERROR: {file_type} not found: {filepath}")
        safe_print(f"✗ ERROR: {file_type} not found: {filepath}")
        return False
    return True


def ensure_directory(dirpath) -> bool:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        dirpath: Path to directory

    Returns:
        True if successful
    """
    from pathlib import Path

    try:
        Path(dirpath).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        safe_print(f"✗ ERROR: Could not create directory {dirpath}: {e}")
        safe_print(f"✗ ERROR: Could not create directory {dirpath}: {e}")
        return False


def lighten_color(hex_color: str, factor: float = 0.15) -> str:
    """
    Lighten a hex color by a factor for gradient effects.

    Args:
        hex_color: Hex color string (e.g., '#ff5733' or 'ff5733')
        factor: Lightening factor between 0 and 1 (default: 0.15)

    Returns:
        Lightened hex color string (e.g., '#ff8866')
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))

    return f'#{r:02x}{g:02x}{b:02x}'


def darken_color(hex_color: str, factor: float = 0.15) -> str:
    """
    Darken a hex color by a factor for gradient effects.

    Args:
        hex_color: Hex color string (e.g., '#ff5733' or 'ff5733')
        factor: Darkening factor between 0 and 1 (default: 0.15)

    Returns:
        Darkened hex color string (e.g., '#cc4629')
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))

    return f'#{r:02x}{g:02x}{b:02x}'

