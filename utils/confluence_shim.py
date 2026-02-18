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


def app_docs_enabled() -> bool:
    """Check whether per-application doc publishing is enabled in config."""
    try:
        config = _load_config()
        value = config.get("publish_app_docs", False)
        logger.info(f"  publish_app_docs config value: {value!r} (type: {type(value).__name__})")
        return bool(value)
    except (ValueError, FileNotFoundError) as e:
        logger.warning(f"  app_docs_enabled check failed: {e}")
        return False


def publish_app_documentation(
    enriched_data: dict,
    version_comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish per-application EA documentation to Confluence pages.

    Uses the ``diagram_pages`` mapping in config to find the Confluence
    page for each application.  Generates wiki markup via
    ``ApplicationDocGenerator`` and updates the page body.

    The SVG diagram attachment is handled separately by
    ``publish_application_diagrams()`` — both use the same pages.

    Args:
        enriched_data: The enriched hierarchical MQ CMDB data
        version_comment: Optional version history comment

    Returns:
        Dict with "published", "skipped", and "errors" counts
    """
    from confluence_client import ConfluenceError
    from generators.app_doc_generator import ApplicationDocGenerator

    summary = {"published": 0, "skipped": 0, "errors": 0}

    try:
        client, config = _get_client()

        page_map = config.get("diagram_pages", {})
        page_map = {k: v for k, v in page_map.items() if not k.startswith("_")}

        if not page_map:
            logger.warning("No diagram_pages mapping configured — skipping app doc publish")
            return summary

        doc_gen = ApplicationDocGenerator(enriched_data)
        comment = version_comment or "Auto-updated by MQ CMDB pipeline"

        known_apps = doc_gen.get_known_apps()
        logger.info(f"  {len(known_apps)} application(s) in data, {len(page_map)} configured in diagram_pages")
        logger.info(f"  Config app names: {list(page_map.keys())}")
        logger.info(f"  Known data apps:  {known_apps[:15]}" + (f" ... +{len(known_apps)-15} more" if len(known_apps) > 15 else ""))

        for app_name, page_id in page_map.items():
            markup = doc_gen.generate_app_page(app_name)
            if not markup:
                logger.warning(
                    f"  No data for '{app_name}' — skipping. "
                    f"Known apps: {', '.join(known_apps[:10])}"
                    + (f" ... and {len(known_apps)-10} more" if len(known_apps) > 10 else "")
                )
                summary["skipped"] += 1
                continue

            try:
                client.update_page(
                    page_id=page_id,
                    title=f"EA_{app_name}",
                    body=markup,
                    representation="wiki",
                    version_comment=comment,
                )
                logger.info(f"  Published doc for '{app_name}' → page {page_id}")
                summary["published"] += 1
            except ConfluenceError as e:
                logger.error(f"  Failed to publish doc for '{app_name}' to page {page_id}: {e}")
                summary["errors"] += 1

        return summary

    except ConfluenceError as e:
        logger.error(f"Confluence API error: {e}")
        return summary
    except Exception as e:
        logger.error(f"Failed to publish app documentation: {e}")
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

def _parse_html_table(
    html_body: str,
    required_header: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Parse an HTML table from a Confluence storage-format page body.

    Extracts ``<th>`` cells as column headers and ``<td>`` cells as row
    values.  Returns a list of dicts (one per data row), keyed by header
    names.  Works with any number of columns.

    When *required_header* is given (e.g. ``"QmgrName"``), the parser
    collects all tables on the page and returns data from the first table
    whose headers contain that column.  This allows pages to have
    decorative or reference tables alongside the data table.

    When *required_header* is ``None``, the first table is used.

    Args:
        html_body: Confluence page body in storage (XHTML) format
        required_header: Optional column name that must be present in
            the target table's header row

    Returns:
        List of row dicts, e.g. [{"QmgrName": "QM_01", "Application": "MyApp"}]
    """
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables: List[dict] = []      # [{"headers": [...], "rows": [[...]]}]
            self._current_headers: List[str] = []
            self._current_rows: List[List[str]] = []
            self._current_row: List[str] = []
            self._current_cell: List[str] = []
            self._in_th = False
            self._in_td = False
            self._in_table = False

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag == "table":
                self._in_table = True
                self._current_headers = []
                self._current_rows = []
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
                if self._current_headers:
                    self.tables.append({
                        "headers": self._current_headers,
                        "rows": self._current_rows,
                    })
            elif tag == "th" and self._in_th:
                self._in_th = False
                self._current_headers.append("".join(self._current_cell).strip())
            elif tag == "td" and self._in_td:
                self._in_td = False
                self._current_row.append("".join(self._current_cell).strip())
            elif tag == "tr" and self._current_row:
                self._current_rows.append(self._current_row)
                self._current_row = []

        def handle_data(self, data):
            if self._in_th or self._in_td:
                self._current_cell.append(data)

    parser = _TableParser()
    parser.feed(html_body)

    if not parser.tables:
        return []

    # Select the right table
    table = None
    if required_header:
        for t in parser.tables:
            if required_header in t["headers"]:
                table = t
                break
        if table is None:
            logger.warning(f"No table with header '{required_header}' found on page")
            return []
    else:
        table = parser.tables[0]

    result = []
    for row in table["rows"]:
        if len(row) == len(table["headers"]):
            result.extend(_expand_csv_row(table["headers"], row))
    return result


def _expand_csv_row(headers: List[str], row: List[str]) -> List[Dict[str, str]]:
    """Expand a row with comma-delimited cell values into multiple rows.

    If any cell contains commas, it is split and a separate row is
    produced for each value.  Non-comma cells are duplicated across all
    expanded rows.  When multiple cells contain commas, the cartesian
    product is produced.

    Examples::

        headers: ["QmgrName", "Application"]
        row:     ["QM_01, QM_02, QM_03", "MyApp"]
        result:  [{"QmgrName": "QM_01", "Application": "MyApp"},
                  {"QmgrName": "QM_02", "Application": "MyApp"},
                  {"QmgrName": "QM_03", "Application": "MyApp"}]
    """
    from itertools import product

    split_values = []
    for val in row:
        if "," in val:
            split_values.append([v.strip() for v in val.split(",") if v.strip()])
        else:
            split_values.append([val])

    rows = []
    for combo in product(*split_values):
        rows.append(dict(zip(headers, combo)))
    return rows


def sync_confluence_table(
    page_id: str,
    output_path: str,
    required_header: Optional[str] = None,
) -> bool:
    """Fetch a Confluence page table and write it as a JSON array.

    This is the generic building block for syncing any Confluence table
    page to a local JSON input file.  The page should contain a table
    whose header row (``<th>``) matches the JSON keys expected by the
    downstream consumer.

    When *required_header* is given, the parser selects the table whose
    headers contain that column — useful when the page has additional
    reference or decorative tables.

    Args:
        page_id: Confluence page ID containing the table
        output_path: Local file path to write the JSON array to
        required_header: Optional column name to identify the correct
            table (e.g. ``"QmgrName"``)

    Returns:
        True on success, False on failure (existing file is preserved)
    """
    from confluence_client import ConfluenceError

    try:
        client, _config = _get_client()
        html_body = client.get_page_body(page_id)
        rows = _parse_html_table(html_body, required_header=required_header)

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
        if not isinstance(page_config, dict):
            continue
        page_id = page_config.get("page_id", "")
        output_file = page_config.get("output_file", "")
        required_header = page_config.get("required_header")

        if not page_id or not output_file:
            logger.info(f"  Skipping '{name}': missing page_id or output_file")
            summary["skipped"] += 1
            continue

        # Resolve relative paths against project root
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = _PROJECT_ROOT / output_path

        if sync_confluence_table(page_id, str(output_path), required_header=required_header):
            summary["synced"] += 1
        else:
            summary["errors"] += 1

    return summary
