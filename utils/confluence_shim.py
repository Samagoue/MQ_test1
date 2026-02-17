"""
Confluence integration shim for the MQ CMDB project.

Loads project-specific configuration from config/confluence_config.json
and delegates to the generic confluence_client in the shared scripts directory.

Usage:
    from utils.confluence_shim import publish_ea_documentation, publish_application_diagrams

    # Publish the EA doc to Confluence
    publish_ea_documentation("/path/to/EA_Documentation.txt")

    # Attach each application SVG to its own Confluence page (per diagram_pages mapping)
    publish_application_diagrams()

    # Sync input files from Confluence pages before pipeline runs
    from utils.confluence_shim import sync_input_files
    sync_input_files()
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from utils.logging_config import get_logger

logger = get_logger("utils.confluence_shim")

# Shared scripts directory (same convention as logging_config.py)
_SHARED_SCRIPTS_DIR = os.environ.get("SHARED_SCRIPTS_DIR", r"C:/Users/BABED2P/Documents/WORKSPACE/Scripts")
if _SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS_DIR)

# Resolve paths relative to project root
_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_FILE = _PROJECT_ROOT / "config" / "confluence_config.json"


def _load_config() -> Dict[str, Any]:
    """
    Load Confluence configuration.

    Priority:
        1. Environment variables (CONFLUENCE_BASE_URL, CONFLUENCE_PAT, etc.)
        2. config/confluence_config.json

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file is missing and env vars are not set
    """
    config = {}

    # Load from JSON file if it exists
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

    # Environment variable overrides (take precedence)
    env_mappings = {
        "CONFLUENCE_BASE_URL": "base_url",
        "CONFLUENCE_PAT": "personal_access_token",
        "CONFLUENCE_CERTIFICATE_PATH": "certificate_path",
        "CONFLUENCE_SPACE_KEY": "space_key",
        "CONFLUENCE_PAGE_ID": "page_id",
        "CONFLUENCE_PAGE_TITLE": "page_title",
    }
    for env_key, config_key in env_mappings.items():
        env_val = os.environ.get(env_key)
        if env_val:
            config[config_key] = env_val

    # Validate required fields
    if not config.get("base_url"):
        raise ValueError(
            "Confluence base_url is required. "
            "Set CONFLUENCE_BASE_URL env var or configure config/confluence_config.json"
        )
    if not config.get("personal_access_token"):
        raise ValueError(
            "Confluence personal_access_token is required. "
            "Set CONFLUENCE_PAT env var or configure config/confluence_config.json"
        )

    return config


def _get_client():
    """Create a ConfluenceClient from project config."""
    from confluence_client import ConfluenceClient

    config = _load_config()

    cert_path = config.get("certificate_path") or None
    if cert_path and not Path(cert_path).exists():
        logger.warning(f"Certificate path does not exist: {cert_path}, ignoring")
        cert_path = None

    return ConfluenceClient(
        base_url=config["base_url"],
        personal_access_token=config["personal_access_token"],
        certificate_path=cert_path,
        verify_ssl=config.get("verify_ssl", True),
        timeout=config.get("timeout", 30),
    ), config


def is_configured() -> bool:
    """Check whether Confluence integration is configured and ready."""
    try:
        _load_config()
        return True
    except (ValueError, FileNotFoundError):
        return False


def attach_diagrams_enabled() -> bool:
    """Check whether diagram attachment is enabled in config."""
    try:
        config = _load_config()
        return config.get("attach_diagrams", False)
    except (ValueError, FileNotFoundError):
        return False


def publish_ea_documentation(
    doc_file: str,
    page_id: Optional[str] = None,
    page_title: Optional[str] = None,
    version_comment: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Publish EA documentation to a Confluence page.

    Reads the wiki markup file and updates the target page using
    Confluence wiki representation.

    Args:
        doc_file: Path to the EA documentation .txt file (Confluence wiki markup)
        page_id: Override page ID (defaults to config)
        page_title: Override page title (defaults to config)
        version_comment: Version history comment

    Returns:
        Updated page data dict, or None on failure
    """
    from confluence_client import ConfluenceError

    try:
        client, config = _get_client()

        pid = page_id or config.get("page_id")
        title = page_title or config.get("page_title", "MQ Integration Architecture")

        if not pid:
            raise ValueError("page_id is required - set in config or pass as argument")

        if not Path(doc_file).exists():
            raise FileNotFoundError(f"Documentation file not found: {doc_file}")

        comment = version_comment or "Auto-updated by MQ CMDB pipeline"

        result = client.update_page_from_file(
            page_id=pid,
            title=title,
            file_path=doc_file,
            representation="wiki",
            version_comment=comment,
        )

        logger.info(f"Published EA documentation to Confluence page {pid}")
        return result

    except ConfluenceError as e:
        logger.error(f"Confluence API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to publish EA documentation: {e}")
        return None


def publish_application_diagrams(
    diagrams_dir: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Attach each application diagram SVG to its own Confluence page.

    Uses the "diagram_pages" mapping in config to match application names
    to Confluence page IDs. SVG files are discovered from the application
    diagrams directory.

    Config example:
        "diagram_pages": {
            "MyApp1": "111111111",
            "MyApp2": "222222222"
        }

    The lookup matches config keys against SVG filenames using the same
    sanitization as the diagram generator (spaces/special chars → underscores).

    Args:
        diagrams_dir: Override path to the application diagrams directory.
                      Defaults to output/diagrams/applications/
        comment: Attachment comment

    Returns:
        Dict with "attached", "skipped", and "errors" counts
    """
    from confluence_client import ConfluenceError

    summary = {"attached": 0, "skipped": 0, "errors": 0, "details": []}

    try:
        client, config = _get_client()

        page_map = config.get("diagram_pages", {})
        # Remove _comment key if present
        page_map = {k: v for k, v in page_map.items() if not k.startswith("_")}

        if not page_map:
            logger.warning("No diagram_pages mapping configured - skipping diagram publish")
            return summary

        # Resolve diagrams directory
        if diagrams_dir:
            svg_dir = Path(diagrams_dir)
        else:
            svg_dir = _PROJECT_ROOT / "output" / "diagrams" / "applications"

        if not svg_dir.exists():
            logger.warning(f"Application diagrams directory not found: {svg_dir}")
            return summary

        # Build a lookup: sanitized_name → svg_path
        svg_files = {}
        for svg_path in svg_dir.glob("*.svg"):
            svg_files[svg_path.stem] = svg_path

        att_comment = comment or "Auto-attached by MQ CMDB pipeline"

        for app_name, page_id in page_map.items():
            sanitized = _sanitize_filename(app_name)

            if sanitized not in svg_files:
                logger.info(f"  No SVG found for '{app_name}' (looked for {sanitized}.svg) - skipping")
                summary["skipped"] += 1
                continue

            svg_path = svg_files[sanitized]
            try:
                client.attach_file(
                    page_id=page_id,
                    file_path=str(svg_path),
                    comment=att_comment,
                )
                logger.info(f"  ✓ Attached {svg_path.name} → page {page_id} ({app_name})")
                summary["attached"] += 1
                summary["details"].append({"app": app_name, "page_id": page_id, "file": str(svg_path)})
            except ConfluenceError as e:
                logger.error(f"  ✗ Failed to attach {svg_path.name} to page {page_id}: {e}")
                summary["errors"] += 1

        return summary

    except ConfluenceError as e:
        logger.error(f"Confluence API error: {e}")
        return summary
    except Exception as e:
        logger.error(f"Failed to publish application diagrams: {e}")
        return summary


def _sanitize_filename(name: str) -> str:
    """Sanitize name to match the diagram generator's filename convention."""
    import re
    sanitized = re.sub(r'[^\w\s-]', '_', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')


# ------------------------------------------------------------------ #
#  Confluence → local JSON sync (input file management)
# ------------------------------------------------------------------ #

def _parse_html_table(html_body: str) -> List[Dict[str, str]]:
    """Parse the first HTML table in a Confluence storage-format page body.

    Extracts ``<th>`` cells as column headers and ``<td>`` cells as row
    values.  Returns a list of dicts (one per data row), keyed by header
    names.  Works with any number of columns.

    Args:
        html_body: Confluence page body in storage (XHTML) format

    Returns:
        List of row dicts, e.g. [{"QmgrName": "QM_01", "Application": "MyApp"}]
    """
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.headers: List[str] = []
            self.rows: List[List[str]] = []
            self._current_row: List[str] = []
            self._current_cell: List[str] = []
            self._in_th = False
            self._in_td = False
            self._in_table = False

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag == "table":
                self._in_table = True
            elif self._in_table and tag == "th":
                self._in_th = True
                self._current_cell = []
            elif self._in_table and tag == "td":
                self._in_td = True
                self._current_cell = []

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag == "table":
                self._in_table = False
            elif tag == "th" and self._in_th:
                self._in_th = False
                self.headers.append("".join(self._current_cell).strip())
            elif tag == "td" and self._in_td:
                self._in_td = False
                self._current_row.append("".join(self._current_cell).strip())
            elif tag == "tr" and self._current_row:
                self.rows.append(self._current_row)
                self._current_row = []

        def handle_data(self, data):
            if self._in_th or self._in_td:
                self._current_cell.append(data)

    parser = _TableParser()
    parser.feed(html_body)

    if not parser.headers:
        return []

    result = []
    for row in parser.rows:
        if len(row) == len(parser.headers):
            result.append(dict(zip(parser.headers, row)))
    return result


def sync_confluence_table(page_id: str, output_path: str) -> bool:
    """Fetch a Confluence page table and write it as a JSON array.

    This is the generic building block for syncing any Confluence table
    page to a local JSON input file.  The page should contain a single
    table whose header row (``<th>``) matches the JSON keys expected by
    the downstream consumer.

    Args:
        page_id: Confluence page ID containing the table
        output_path: Local file path to write the JSON array to

    Returns:
        True on success, False on failure (existing file is preserved)
    """
    from confluence_client import ConfluenceError

    try:
        client, _config = _get_client()
        html_body = client.get_page_body(page_id)
        rows = _parse_html_table(html_body)

        if not rows:
            logger.warning(f"No table data found on Confluence page {page_id} — keeping existing file")
            return False

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

        logger.info(f"  Synced {len(rows)} records from page {page_id} → {output_path}")
        return True

    except ConfluenceError as e:
        logger.warning(f"  Confluence API error syncing page {page_id}: {e} — keeping existing file")
        return False
    except Exception as e:
        logger.warning(f"  Failed to sync page {page_id}: {e} — keeping existing file")
        return False


def sync_input_files() -> Dict[str, Any]:
    """Sync all configured input files from Confluence pages.

    Reads the ``input_pages`` mapping from ``confluence_config.json`` and
    fetches each table page, writing the result to the configured local
    file path.  Non-blocking: failures are logged and skipped so the
    pipeline can continue with existing local files.

    Config example::

        "input_pages": {
            "app_to_qmgr": {
                "page_id": "123456",
                "output_file": "input/app_to_qmgr.json"
            },
            "gateways": {
                "page_id": "789012",
                "output_file": "input/gateways.json"
            }
        }

    Returns:
        Summary dict with "synced", "skipped", and "errors" counts
    """
    summary = {"synced": 0, "skipped": 0, "errors": 0}

    try:
        config = _load_config()
    except (ValueError, FileNotFoundError):
        logger.warning("Confluence not configured — skipping input file sync")
        return summary

    input_pages = config.get("input_pages", {})
    if not input_pages:
        logger.info("  No input_pages configured — skipping sync")
        return summary

    for name, page_config in input_pages.items():
        page_id = page_config.get("page_id", "")
        output_file = page_config.get("output_file", "")

        if not page_id or not output_file:
            logger.info(f"  Skipping '{name}': missing page_id or output_file")
            summary["skipped"] += 1
            continue

        # Resolve relative paths against project root
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = _PROJECT_ROOT / output_path

        if sync_confluence_table(page_id, str(output_path)):
            summary["synced"] += 1
        else:
            summary["errors"] += 1

    return summary
