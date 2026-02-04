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

    # Collect all unique fieldnames from all records to handle varying keys
    all_keys = set()
    for record in data:
        all_keys.update(record.keys())
    fieldnames = sorted(all_keys)

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, extrasaction='ignore')
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


def backup_file(filepath: Path, suffix: str = '.bak') -> bool:
    """
    Create a backup of a file.

    Args:
        filepath: Path to file to backup
        suffix: Suffix for backup file (default: '.bak')

    Returns:
        True if backup was created successfully, False otherwise
    """
    from shutil import copy2

    if not filepath.exists():
        return False

    try:
        backup_path = filepath.with_suffix(filepath.suffix + suffix)
        copy2(filepath, backup_path)
        return True
    except Exception:
        return False


def clean_old_files(directory: Path, days: int, pattern: str = '*') -> int:
    """
    Delete files older than specified number of days.

    Args:
        directory: Directory to clean
        days: Files older than this many days will be deleted
        pattern: File pattern to match (default: '*')

    Returns:
        Number of files deleted
    """
    from datetime import datetime, timedelta

    if not directory.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for filepath in directory.glob(pattern):
        if filepath.is_file():
            file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            if file_time < cutoff:
                filepath.unlink()
                deleted_count += 1

    return deleted_count


def cleanup_output_directory(directory: Path, days: int, patterns: List[str]) -> Dict[str, Any]:
    """
    Clean up old output files based on configured patterns.

    Args:
        directory: Output directory to clean
        days: Files older than this many days will be deleted
        patterns: List of file patterns to clean up

    Returns:
        Dictionary with cleanup results including total deleted and per-pattern counts
    """
    from datetime import datetime, timedelta
    import time

    if not directory.exists():
        return {'total_deleted': 0, 'patterns': {}, 'errors': [], 'deleted_files': []}

    cutoff = datetime.now() - timedelta(days=days)
    # Safety buffer: don't delete files modified in the last 60 seconds
    # to avoid deleting files currently being written
    safety_buffer = time.time() - 60

    results = {
        'total_deleted': 0,
        'patterns': {},
        'deleted_files': [],
        'errors': []
    }

    for pattern in patterns:
        pattern_deleted = 0
        try:
            for filepath in directory.glob(pattern):
                if filepath.is_file():
                    try:
                        stat_info = filepath.stat()
                        file_mtime = stat_info.st_mtime
                        file_time = datetime.fromtimestamp(file_mtime)

                        # Check if file is old enough AND not recently modified
                        if file_time < cutoff and file_mtime < safety_buffer:
                            filepath.unlink()
                            pattern_deleted += 1
                            results['deleted_files'].append(str(filepath.name))
                    except OSError as e:
                        # File might be in use or already deleted
                        results['errors'].append(f"Failed to delete {filepath}: {e}")
        except Exception as e:
            results['errors'].append(f"Error processing pattern {pattern}: {e}")

        results['patterns'][pattern] = pattern_deleted
        results['total_deleted'] += pattern_deleted

    return results
