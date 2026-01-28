"""File I/O utilities for the MQ CMDB system."""

import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(filepath: Path) -> Any:
    """
    Load JSON data from file.
   
    Args:
        filepath: Path to JSON file
   
    Returns:
        Parsed JSON data
   
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
   
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {filepath}: {e.msg}",
            e.doc,
            e.pos
        )


def save_json(data: Any, filepath: Path, indent: int = 2):
    """
    Save data to JSON file.
   
    Args:
        data: Data to save
        filepath: Destination file path
        indent: JSON indentation level (default: 2)
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
   
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_text(filepath: Path) -> str:
    """
    Load text content from file.
   
    Args:
        filepath: Path to text file
   
    Returns:
        File contents as string
   
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
   
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def save_text(content: str, filepath: Path):
    """
    Save text content to file.
   
    Args:
        content: Text content to save
        filepath: Destination file path
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
   
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def append_text(content: str, filepath: Path):
    """
    Append text content to file.
   
    Args:
        content: Text content to append
        filepath: Destination file path
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
   
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(content)


def load_csv(filepath: Path, delimiter: str = ',') -> List[Dict[str, str]]:
    """
    Load CSV file into list of dictionaries.
   
    Args:
        filepath: Path to CSV file
        delimiter: CSV delimiter (default: ',')
   
    Returns:
        List of dictionaries (one per row)
   
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    import csv
   
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
   
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader)


def save_csv(data: List[Dict[str, Any]], filepath: Path, delimiter: str = ','):
    """
    Save list of dictionaries to CSV file.
   
    Args:
        data: List of dictionaries to save
        filepath: Destination file path
        delimiter: CSV delimiter (default: ',')
    """
    import csv
   
    if not data:
        return
   
    filepath.parent.mkdir(parents=True, exist_ok=True)
   
    fieldnames = list(data[0].keys())
   
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(data)


def list_files(directory: Path, pattern: str = '*') -> List[Path]:
    """
    List files in directory matching pattern.
   
    Args:
        directory: Directory to search
        pattern: Glob pattern (default: '*')
   
    Returns:
        List of matching file paths
    """
    if not directory.exists():
        return []
   
    return sorted(directory.glob(pattern))


def file_exists(filepath: Path) -> bool:
    """
    Check if file exists.
   
    Args:
        filepath: Path to check
   
    Returns:
        True if file exists, False otherwise
    """
    return Path(filepath).exists()


def get_file_size(filepath: Path) -> int:
    """
    Get file size in bytes.
   
    Args:
        filepath: Path to file
   
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    path = Path(filepath)
    if path.exists():
        return path.stat().st_size
    return 0


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
   
    Args:
        size_bytes: Size in bytes
   
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def backup_file(filepath: Path, suffix: str = '.bak'):
    """
    Create a backup of a file.
   
    Args:
        filepath: Path to file to backup
        suffix: Suffix for backup file (default: '.bak')
    """
    from shutil import copy2
   
    if not filepath.exists():
        return
   
    backup_path = filepath.with_suffix(filepath.suffix + suffix)
    copy2(filepath, backup_path)


def clean_old_files(directory: Path, days: int, pattern: str = '*'):
    """
    Delete files older than specified number of days.
   
    Args:
        directory: Directory to clean
        days: Files older than this many days will be deleted
        pattern: File pattern to match (default: '*')
    """
    from datetime import datetime, timedelta
    import time
   
    if not directory.exists():
        return
   
    cutoff = datetime.now() - timedelta(days=days)
   
    for filepath in directory.glob(pattern):
        if filepath.is_file():
            file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            if file_time < cutoff:
                filepath.unlink()
