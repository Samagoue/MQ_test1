#!/usr/bin/env python3
"""
=============================================================================
Confluence Round-Trip Demo
=============================================================================

PURPOSE
-------
Demonstrates the complete Confluence data round-trip in three steps:

  1. READ   — Fetch a Confluence page, parse its HTML table into Python dicts
  2. SAVE   — Write the extracted data to a local JSON file
  3. POST   — Create (or update) a new Confluence page with the data formatted
              as a nicely styled Confluence wiki table

This script is self-contained and reads its own configuration from
demo_config.json in the same directory. It does NOT depend on the project's
main config/ directory.

USAGE
-----
Before running, open Demo/demo_config.json and fill in:
  - confluence.base_url
  - confluence.personal_access_token
  - source_page.page_id          (page to read FROM)
  - target_page.parent_page_id   (parent of the new page)
  - target_page.space_key        (OPTIONAL — auto-resolved from parent page
                                   if left blank)

Then run from the project root:
  python Demo/confluence_roundtrip_demo.py

Or from inside the Demo directory:
  python confluence_roundtrip_demo.py

DEPENDENCIES
------------
  - confluence_client.py  (shared library, found via shared_scripts_dir in
                            demo_config.json or SHARED_SCRIPTS_DIR env var)
  - logging_config.py     (shared library, same search path)
  - Standard library only for everything else: json, sys, os, pathlib,
                                                html.parser, datetime
=============================================================================
"""

import json
import os
import sys
from datetime import datetime
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# SECTION 1 — BOOTSTRAP sys.path
# =============================================================================
# Both confluence_client.py and logging_config.py live in a shared scripts
# directory. We need them on sys.path BEFORE we can import them.
#
# Search order:
#   1. SHARED_SCRIPTS_DIR env var (set at runtime on RHEL by install.sh)
#   2. /data/app/Scripts          (default RHEL install path)
#   3. scripts/common/            (local copy inside this repo — works on any
#                                  developer machine without the RHEL install)
#
# All three paths are added to sys.path so either the shared or the local
# copy is found, whichever exists on this machine.

# __file__ resolves to this script; .parent is Demo/; .parent.parent is
# the project root.
DEMO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEMO_DIR.parent

_bootstrap_paths = [
    os.environ.get("SHARED_SCRIPTS_DIR", ""),   # env var — highest priority
    "/data/app/Scripts",                          # RHEL default install path
    str(PROJECT_ROOT / "scripts" / "common"),     # local repo copy — dev fallback
]
for _bp in _bootstrap_paths:
    if _bp and Path(_bp).is_dir() and _bp not in sys.path:
        sys.path.insert(0, _bp)


# =============================================================================
# SECTION 2 — IMPORT LOGGING (with bare fallback)
# =============================================================================
# Try to import the project's shared logging_config which gives us:
#   setup_logging() — initialises file + console handlers with a startup banner
#   get_logger()    — returns a named child logger under the demo namespace
#
# If the shared library isn't found yet (e.g. first run before install.sh),
# we fall back to Python's built-in logging so the script still works.

try:
    # type: ignore silences the Pylance "unresolved import" warning — logging_config
    # is not a PyPI package; it is found at runtime via the sys.path bootstrap above.
    from logging_config import setup_logging, get_logger  # type: ignore[import]
    _shared_logging = True
except ImportError:
    import logging as _stdlib_logging
    _stdlib_logging.basicConfig(
        level=_stdlib_logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    # Minimal stubs that match the real signatures.
    # **_kwargs absorbs log_dir / verbose / banner_config so callers need not change.
    def setup_logging(log_prefix: str = "demo", **_):  # type: ignore[misc]
        """Fallback: stdlib logger when shared logging_config is not installed."""
        return _stdlib_logging.getLogger(log_prefix)

    def get_logger(name: str):  # type: ignore[misc]
        """Fallback: stdlib logger when shared logging_config is not installed."""
        return _stdlib_logging.getLogger(f"demo.{name}")
    _shared_logging = False

# Module-level logger — created here so every function can use it.
# setup_logging() hasn't been called yet at this point; the logger will
# attach to the correct handlers once setup_logging() runs in main().
logger = get_logger("roundtrip_demo")

# Config file sits right beside this script in the Demo/ directory.
CONFIG_FILE = DEMO_DIR / "demo_config.json"


# =============================================================================
# SECTION 3 — LOAD CONFIGURATION
# =============================================================================

def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Read demo_config.json and return its contents as a Python dictionary.

    Validates that required fields are present and not still set to their
    'TODO_...' placeholder values, so the user gets a clear error message
    instead of a confusing Confluence API failure later.

    Args:
        config_path: Absolute path to demo_config.json

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If demo_config.json does not exist
        ValueError:        If required fields are missing or still placeholders
        json.JSONDecodeError: If the file contains malformed JSON
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Make sure demo_config.json is in the same directory as this script."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"demo_config.json contains invalid JSON at position {e.pos}: {e.msg}",
                e.doc, e.pos
            ) from e

    # Validate required fields (space_key is intentionally NOT required —
    # it is auto-resolved from the parent page when missing).
    _require_field(config, ["confluence", "base_url"],            "confluence.base_url")
    _require_field(config, ["confluence", "personal_access_token"], "confluence.personal_access_token")
    _require_field(config, ["source_page", "page_id"],            "source_page.page_id")
    _require_field(config, ["target_page", "parent_page_id"],     "target_page.parent_page_id")

    return config


def _require_field(config: dict, path: List[str], display_name: str) -> None:
    """
    Walk the nested config dict using `path` and raise ValueError if the field
    is missing or still contains the 'TODO_...' placeholder string.

    Args:
        config:       The full config dictionary
        path:         Sequence of nested keys, e.g. ["confluence", "base_url"]
        display_name: Human-readable dotted name used in the error message
    """
    value = config
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(
                f"Required config field '{display_name}' is missing from demo_config.json"
            )
        value = value[key]

    if not value or str(value).startswith("TODO_"):
        raise ValueError(
            f"Config field '{display_name}' still has a placeholder value. "
            f"Please edit demo_config.json and set your real value."
        )


# =============================================================================
# SECTION 4 — CONNECT TO CONFLUENCE
# =============================================================================

def connect_to_confluence(config: Dict[str, Any]):
    """
    Import ConfluenceClient from the shared library and return a connected instance.

    The sys.path was already bootstrapped at module level using the
    SHARED_SCRIPTS_DIR env var / /data/app/Scripts / scripts/common fallback.
    If the config specifies a different shared_scripts_dir, we add it here too.

    Args:
        config: The full config dictionary (must have 'confluence' sub-dict)

    Returns:
        A ConfluenceClient instance (connection is lazy — first API call
        triggers the actual HTTP connection)

    Raises:
        ImportError: If confluence_client.py cannot be found anywhere
    """
    conn = config["confluence"]

    # If demo_config.json specifies a shared_scripts_dir that differs from what
    # was bootstrapped at module level, add it now so it's also searched.
    extra_dir = config.get("shared_scripts_dir", "").strip()
    if extra_dir and Path(extra_dir).is_dir() and extra_dir not in sys.path:
        sys.path.insert(0, extra_dir)
        logger.info(f"  Added shared_scripts_dir to path: {extra_dir}")

    try:
        from confluence_client import ConfluenceClient
    except ImportError:
        raise ImportError(
            "Could not import 'confluence_client'. "
            "Make sure shared_scripts_dir in demo_config.json points to the "
            "directory containing confluence_client.py, or set the "
            "SHARED_SCRIPTS_DIR environment variable."
        )

    # Resolve certificate path — expand relative paths against the project root.
    cert_path = conn.get("certificate_path", "").strip() or None
    if cert_path:
        cert_obj = Path(cert_path)
        if not cert_obj.is_absolute():
            cert_obj = PROJECT_ROOT / cert_obj
        if cert_obj.exists():
            cert_path = str(cert_obj)
            logger.info(f"  Using SSL certificate: {cert_path}")
        else:
            logger.warning(f"  Certificate not found at '{cert_path}' — ignoring")
            cert_path = None

    # Build the client. No network call yet — the connection is lazy.
    client = ConfluenceClient(
        base_url=conn["base_url"].rstrip("/"),        # strip trailing slash for clean URLs
        personal_access_token=conn["personal_access_token"],
        certificate_path=cert_path,
        verify_ssl=conn.get("verify_ssl", True),
        timeout=conn.get("timeout", 30),
    )

    return client


# =============================================================================
# SECTION 5 — READ THE SOURCE PAGE
# =============================================================================

def read_source_page(client, page_id: str) -> str:
    """
    Fetch the HTML body of a Confluence page.

    Confluence stores page content in 'storage' format — a subset of XHTML.
    This is the format we parse to extract table data.

    Args:
        client:  A connected ConfluenceClient instance
        page_id: Numeric Confluence page ID (as a string)

    Returns:
        HTML body of the page as a string

    Raises:
        ValueError:       If the page body is empty
        ConfluenceError:  If the API call fails (e.g. page not found, no access)
    """
    logger.info(f"  Fetching page {page_id} from Confluence...")

    # get_page_body() fetches the page with body.storage expanded and returns
    # just the raw HTML string — the same format Confluence stores internally.
    html_body = client.get_page_body(page_id)

    if not html_body:
        raise ValueError(
            f"Page {page_id} returned an empty body. "
            f"Check the page ID and your access permissions."
        )

    logger.info(f"  Retrieved {len(html_body):,} characters of page content")
    return html_body


# =============================================================================
# SECTION 6 — PARSE THE HTML TABLE
# =============================================================================
# Confluence stores pages as XHTML-like 'storage format'. We use Python's
# built-in html.parser module to walk the tag stream and extract table rows —
# no third-party libraries (BeautifulSoup etc.) required.

class _TableParser(HTMLParser):
    """
    Minimal HTML table parser built on Python's standard HTMLParser.

    Walks the tag stream and collects every <table> found on the page.
    Stores each as:
        {"headers": ["Col1", "Col2", ...], "rows": [["val1", "val2"], ...]}

    <th> → column header
    <td> → data cell
    <tr> → row boundary
    """

    def __init__(self):
        super().__init__()
        self.tables: List[Dict] = []   # all parsed tables on the page

        # State flags — track which tag we're currently inside.
        self._in_table = False
        self._in_th    = False
        self._in_td    = False

        # Per-table working buffers.
        self._current_headers: List[str]       = []
        self._current_rows:    List[List[str]] = []
        self._current_row:     List[str]       = []   # cells in the current <tr>
        self._current_cell:    List[str]       = []   # text fragments inside one cell

    def handle_starttag(self, tag: str, attrs):
        """Fires when the parser sees an opening tag."""
        tag = tag.lower()   # normalise — Confluence HTML can be upper or lower case

        if tag == "table":
            self._in_table = True
            self._current_headers = []
            self._current_rows    = []

        elif self._in_table and tag == "th":
            self._in_th        = True
            self._current_cell = []

        elif self._in_table and tag == "td":
            self._in_td        = True
            self._current_cell = []

    def handle_endtag(self, tag: str):
        """Fires when the parser sees a closing tag."""
        tag = tag.lower()

        if tag == "table":
            self._in_table = False
            # Only store the table if it had at least one header column.
            if self._current_headers:
                self.tables.append({
                    "headers": self._current_headers[:],
                    "rows":    self._current_rows[:],
                })

        elif tag == "th" and self._in_th:
            self._in_th = False
            # Join any text fragments the parser split across multiple data events.
            self._current_headers.append("".join(self._current_cell).strip())

        elif tag == "td" and self._in_td:
            self._in_td = False
            self._current_row.append("".join(self._current_cell).strip())

        elif tag == "tr" and self._current_row:
            # End of a data row — save it and reset the row buffer.
            self._current_rows.append(self._current_row[:])
            self._current_row = []

    def handle_data(self, data: str):
        """Fires with the raw text between tags."""
        # A single cell can produce multiple data events (e.g. text around
        # an inner <strong> tag), so we accumulate into a list and join later.
        if self._in_th or self._in_td:
            self._current_cell.append(data)


def parse_table(html_body: str, required_column: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Parse HTML tables from a Confluence page body and return data rows as dicts.

    When `required_column` is given, picks the first table whose headers include
    that column name — useful when a page has a legend table alongside the real
    data table. When it is None/empty, the first table on the page is used.

    Args:
        html_body:       Raw XHTML from the Confluence page storage body
        required_column: Optional column header that identifies the target table

    Returns:
        List of dicts, one per data row.  E.g.:
            [{"Name": "Alice", "Role": "Engineer"}, ...]
        Returns [] if no matching table is found.
    """
    parser = _TableParser()
    parser.feed(html_body)

    if not parser.tables:
        logger.warning("No HTML tables found on the source page.")
        return []

    logger.info(f"  Found {len(parser.tables)} table(s) on the page")

    # Select the target table.
    target_table = None
    if required_column:
        for t in parser.tables:
            if required_column in t["headers"]:
                target_table = t
                break
        if target_table is None:
            logger.warning(
                f"No table with column '{required_column}' found. "
                f"Tables on page have headers: "
                + str([t["headers"] for t in parser.tables])
            )
            return []
        logger.info(
            f"  Using table with column '{required_column}' "
            f"({len(target_table['headers'])} columns, {len(target_table['rows'])} rows)"
        )
    else:
        target_table = parser.tables[0]
        logger.info(
            f"  Using first table "
            f"({len(target_table['headers'])} columns, {len(target_table['rows'])} rows)"
        )

    # Convert raw rows (list of lists) → list of dicts using headers as keys.
    # Rows with an unexpected cell count are skipped (colspan/rowspan artefacts).
    records = []
    skipped = 0
    for raw_row in target_table["rows"]:
        if len(raw_row) == len(target_table["headers"]):
            records.append(dict(zip(target_table["headers"], raw_row)))
        else:
            skipped += 1

    if skipped:
        logger.warning(
            f"Skipped {skipped} row(s) with unexpected column count "
            f"(likely colspan / merged cells)"
        )

    logger.info(f"  Parsed {len(records)} valid data records")
    return records


# =============================================================================
# SECTION 7 — SAVE DATA TO JSON
# =============================================================================

def save_to_json(records: List[Dict[str, str]], output_path: Path) -> None:
    """
    Write extracted records to a local JSON file.

    Wraps the data in a metadata envelope (timestamp + record count) so
    downstream consumers know when and where the data came from.

    Args:
        records:     List of dicts extracted from the Confluence table
        output_path: Where to write (parent directory is created if needed)
    """
    # mkdir -p equivalent: create any missing parent directories.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "_metadata": {
            "extracted_at":  datetime.now().isoformat(timespec="seconds"),
            "record_count":  len(records),
            "source":        "Confluence round-trip demo",
        },
        "data": records,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        # indent=2  → human-readable multi-line output
        # ensure_ascii=False → preserve Unicode characters as-is
        json.dump(payload, f, indent=2, ensure_ascii=False)

    size_bytes = output_path.stat().st_size
    size_label = f"{size_bytes:,} bytes"
    if size_bytes > 1024:
        size_label += f" ({size_bytes / 1024:.1f} KB)"
    logger.info(f"  Saved {len(records)} records → {output_path}  [{size_label}]")


# =============================================================================
# SECTION 8 — FORMAT DATA AS CONFLUENCE WIKI MARKUP
# =============================================================================
# Confluence accepts 'wiki' format (legacy wiki markup) and 'storage' format
# (XHTML). We use 'wiki' because it's compact and easy to verify by inspection.
#
# Wiki table syntax:
#   ||Header A||Header B||    ← double-pipe separates header cells
#   |value 1a|value 1b|       ← single-pipe separates data cells

def format_as_wiki_table(records: List[Dict[str, str]]) -> str:
    """
    Convert a list of dicts into a Confluence wiki markup table string.

    Args:
        records: Data records (all with the same keys — from the same table)

    Returns:
        Multi-line wiki markup string, or an italic 'no data' notice if empty
    """
    if not records:
        return "_No data records were extracted from the source page._"

    headers = list(records[0].keys())

    # Header row: each column name enclosed in double pipes.
    header_row = "||" + "||".join(headers) + "||"

    # Data rows: each cell value enclosed in single pipes.
    data_rows = []
    for record in records:
        cells = [str(record.get(h, "")) for h in headers]
        data_rows.append("|" + "|".join(cells) + "|")

    return header_row + "\n" + "\n".join(data_rows)


def build_page_body(
    records:        List[Dict[str, str]],
    source_page_id: str,
    base_url:       str,
    json_file_path: Path,
) -> str:
    """
    Build the complete Confluence wiki markup body for the new target page.

    Includes an intro section, a clickable link back to the source page,
    the data as a formatted wiki table, and a how-it-works explanation.

    Args:
        records:        Extracted data records
        source_page_id: ID of the page data was read from
        base_url:       Confluence base URL (for building links)
        json_file_path: Local path where the JSON was saved

    Returns:
        Complete wiki markup string ready to POST
    """
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record_count = len(records)

    # [Link Text|URL] is Confluence wiki syntax for a hyperlink.
    source_url  = f"{base_url}/pages/{source_page_id}"
    source_link = f"[Source Page (ID: {source_page_id})|{source_url}]"

    wiki_table = format_as_wiki_table(records)

    # h1., h2. are Confluence wiki heading markers.
    # *text* renders as bold.
    # # starts a numbered list item.
    return f"""h1. Demo - Data Imported from Confluence

This page was automatically generated by the *Confluence Round-Trip Demo* script.
It demonstrates reading a Confluence page, extracting its table data, saving it
to JSON, and posting it back to Confluence as a new page.

h2. Source Information

* *Source Page:* {source_link}
* *Records Extracted:* {record_count}
* *Generated At:* {now}
* *Local JSON File:* {json_file_path}

h2. Extracted Data

The table below contains all {record_count} records extracted from the source page.

{wiki_table}

h2. How This Works

# The script fetches the source page body in Confluence storage (XHTML) format.
# It parses the HTML table using Python's built-in html.parser — no third-party libraries.
# The extracted rows are saved to a local JSON file with a metadata envelope.
# The same data is formatted as Confluence wiki markup and posted as this page.
# Running the script again updates this page rather than creating a duplicate.

----
_Auto-generated by confluence_roundtrip_demo.py — safe to delete._
"""


# =============================================================================
# SECTION 9 — RESOLVE SPACE KEY
# =============================================================================

def resolve_space_key(client, config: Dict[str, Any]) -> str:
    """
    Return the Confluence space key to use for the target page.

    Lookup priority:
      1. target_page.space_key in demo_config.json (if set and non-empty)
      2. Auto-resolve from the parent page via the Confluence API

    This means space_key is fully optional in demo_config.json — the demo
    can figure it out itself as long as the parent page exists and is accessible.

    Args:
        client: A connected ConfluenceClient instance
        config: The full config dictionary

    Returns:
        Space key string (may be empty if resolution fails — caller logs a warning)
    """
    target    = config["target_page"]
    space_key = target.get("space_key", "").strip()

    if space_key:
        # Already set in config — use it directly.
        logger.info(f"  Using space_key '{space_key}' from config")
        return space_key

    # Auto-resolve: ask Confluence what space the parent page lives in.
    parent_id = target["parent_page_id"]
    logger.info(f"  space_key not set in config — resolving from parent page {parent_id}...")

    try:
        # expand="space" asks the API to include the page's space metadata
        # in the response rather than just returning the bare page content.
        parent_page = client.get_page(parent_id, expand="space")
        space_key   = parent_page.get("space", {}).get("key", "")

        if space_key:
            logger.info(f"  Resolved space_key '{space_key}' from parent page")
        else:
            logger.warning(
                "  Parent page response did not include a space key. "
                "Page creation may fail — try setting target_page.space_key "
                "manually in demo_config.json."
            )
    except Exception as e:
        logger.warning(
            f"  Could not resolve space_key from parent page {parent_id}: {e}. "
            "Page creation may fail — try setting target_page.space_key "
            "manually in demo_config.json."
        )

    return space_key


# =============================================================================
# SECTION 10 — POST THE NEW PAGE TO CONFLUENCE
# =============================================================================

def post_to_confluence(
    client,
    config:       Dict[str, Any],
    space_key:    str,
    body:         str,
    record_count: int,
) -> Optional[str]:
    """
    Create a new Confluence page or update it if one with the same title already
    exists under the same parent (making the demo idempotent — safe to re-run).

    Strategy:
      1. Fetch child pages under the target parent.
      2. If a page with our title exists → update it.
      3. Otherwise → create a new child page.

    Args:
        client:       A connected ConfluenceClient instance
        config:       The full config dictionary
        space_key:    Resolved space key (may be empty — logged as warning)
        body:         Confluence wiki markup for the page body
        record_count: Number of records (used in the version comment)

    Returns:
        Page ID of the created/updated page as a string, or None on failure
    """
    from confluence_client import ConfluenceError

    target         = config["target_page"]
    parent_page_id = target["parent_page_id"]
    page_title     = target["title"]
    version_comment = (
        f"Auto-updated by demo: {record_count} records, "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    logger.info(f"  Checking for existing page '{page_title}' under parent {parent_page_id}...")

    # get_child_pages() returns a list of dicts with at least 'id' and 'title'.
    # 'or []' guards against the API returning None on an empty child list.
    existing_children = client.get_child_pages(parent_page_id) or []

    # Build a dict for O(1) title lookup: {"Page Title": "page_id", ...}
    existing_by_title = {child["title"]: child["id"] for child in existing_children}

    if page_title in existing_by_title:
        # ---- UPDATE existing page ----
        existing_page_id = existing_by_title[page_title]
        logger.info(f"  Found existing page (id {existing_page_id}) — updating...")

        client.update_page(
            page_id        = existing_page_id,
            title          = page_title,
            body           = body,
            representation = "wiki",          # interpret body as wiki markup
            version_comment= version_comment,
        )
        logger.info(f"  ✓ Updated page id {existing_page_id}")
        return existing_page_id

    else:
        # ---- CREATE new page ----
        logger.info(f"  Page not found — creating new child page...")

        result = client.create_page(
            space_key      = space_key,
            title          = page_title,
            body           = body,
            parent_id      = parent_page_id,
            representation = "wiki",          # interpret body as wiki markup
        )

        # create_page() returns a dict containing the new page's metadata.
        # Guard against None in case the API returned an unexpected response.
        new_page_id = result.get("id") if result else None

        if not new_page_id:
            logger.error(
                "create_page() did not return a page ID. "
                "Check space_key, parent_page_id, and your write permissions."
            )
            return None

        logger.info(f"  ✓ Created page id {new_page_id}")
        return new_page_id


# =============================================================================
# SECTION 11 — PRINT FINAL SUMMARY
# =============================================================================

def print_summary(
    config:          Dict[str, Any],
    records:         List[Dict[str, str]],
    json_path:       Path,
    new_page_id:     Optional[str],
    elapsed_seconds: float,
) -> None:
    """
    Log a human-readable summary of what the demo did.

    Args:
        config:          Full config dictionary
        records:         Extracted data records
        json_path:       Path to the saved JSON file
        new_page_id:     Confluence page ID of the created/updated page (or None)
        elapsed_seconds: Total runtime in seconds
    """
    base_url     = config["confluence"]["base_url"].rstrip("/")
    source_id    = config["source_page"]["page_id"]
    target_title = config["target_page"]["title"]

    logger.info("")
    logger.info("=" * 60)
    logger.info("  DEMO COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Records extracted : {len(records)}")
    logger.info(f"  Source page       : {base_url}/pages/{source_id}")
    logger.info(f"  JSON saved to     : {json_path}")

    if new_page_id:
        target_url = f"{base_url}/pages/{new_page_id}"
        logger.info(f"  Target page       : {target_url}")
        logger.info(f"  Page title        : {target_title}")
    else:
        logger.warning("  Target page       : FAILED (check errors above)")

    logger.info(f"  Total time        : {elapsed_seconds:.1f}s")
    logger.info("=" * 60)

    if new_page_id:
        logger.info("")
        logger.info(f"  Open the new page in your browser:")
        logger.info(f"  {base_url}/pages/{new_page_id}")
        logger.info("")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> int:
    """
    Orchestrate the full Confluence round-trip demo.

    Returns:
        0 on success, 1 on any failure (so shell scripts / CI can detect errors)
    """
    import time
    start_time = time.monotonic()

    # ------------------------------------------------------------------
    # STEP 0: Initialise logging
    # Set up file + console handlers before doing any real work so that
    # everything — including any early errors — is captured in the log file.
    # ------------------------------------------------------------------
    log_dir = DEMO_DIR / "output" / "logs"
    setup_logging(
        log_dir     = str(log_dir),
        log_prefix  = "demo",
        # Show an ASCII art banner in the log so it's easy to spot where
        # a run starts when tailing log files.
        banner_config = {
            "art_text": "DEMO",
            "title":    "Confluence Round-Trip Demo",
            "subtitle": "Read → JSON → Post",
        },
    )

    if not _shared_logging:
        logger.warning(
            "Could not import shared logging_config — using stdlib fallback. "
            "Log output will go to the console only (no file)."
        )

    logger.info("")
    logger.info("=" * 60)
    logger.info("  Confluence Round-Trip Demo")
    logger.info("=" * 60)
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 1: Load configuration
    # ------------------------------------------------------------------
    logger.info("[Step 1] Loading configuration...")
    try:
        config = load_config(CONFIG_FILE)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        logger.error(str(e))
        return 1
    logger.info(f"  Config loaded from: {CONFIG_FILE}")
    logger.info(f"  Confluence server : {config['confluence']['base_url']}")
    logger.info(f"  Source page ID    : {config['source_page']['page_id']}")
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 2: Connect to Confluence
    # ------------------------------------------------------------------
    logger.info("[Step 2] Connecting to Confluence...")
    try:
        client = connect_to_confluence(config)
    except ImportError as e:
        logger.error(str(e))
        return 1
    logger.info("  Client initialised (first API call happens in Step 3)")
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 3: Read the source page
    # ------------------------------------------------------------------
    logger.info("[Step 3] Reading source Confluence page...")
    source_page_id = config["source_page"]["page_id"]
    try:
        html_body = read_source_page(client, source_page_id)
    except Exception as e:
        logger.error(str(e))
        return 1
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 4: Parse the HTML table
    # ------------------------------------------------------------------
    logger.info("[Step 4] Parsing HTML table from page body...")
    required_col = config["source_page"].get("required_column", "").strip() or None
    records = parse_table(html_body, required_column=required_col)

    if not records:
        logger.error(
            "No records could be extracted. "
            "Verify the source page contains a table and check the "
            "required_column setting in demo_config.json."
        )
        return 1
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 5: Save extracted data to a local JSON file
    # ------------------------------------------------------------------
    logger.info("[Step 5] Saving extracted data to JSON...")
    raw_json_path = config["output"]["json_file"]
    json_path = Path(raw_json_path)
    if not json_path.is_absolute():
        # Relative paths are relative to the project root (one level up from Demo/).
        json_path = PROJECT_ROOT / json_path
    try:
        save_to_json(records, json_path)
    except Exception as e:
        logger.error(f"Failed to save JSON: {e}")
        return 1
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 6: Resolve space_key (auto-fetched from parent page if not set)
    # ------------------------------------------------------------------
    logger.info("[Step 6] Resolving Confluence space key...")
    try:
        space_key = resolve_space_key(client, config)
    except Exception as e:
        logger.warning(f"Space key resolution failed: {e} — will attempt page creation anyway")
        space_key = ""
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 7: Build the target page body
    # ------------------------------------------------------------------
    logger.info("[Step 7] Formatting data as Confluence wiki markup...")
    base_url  = config["confluence"]["base_url"].rstrip("/")
    page_body = build_page_body(records, source_page_id, base_url, json_path)
    logger.info(f"  Page body: {len(page_body):,} characters, {len(records)} rows in table")
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 8: Post the page to Confluence (create or update)
    # ------------------------------------------------------------------
    logger.info("[Step 8] Posting data to Confluence...")
    try:
        new_page_id = post_to_confluence(client, config, space_key, page_body, len(records))
    except Exception as e:
        logger.error(f"Failed to post to Confluence: {e}")
        return 1
    logger.info("")

    # ------------------------------------------------------------------
    # STEP 9: Summary
    # ------------------------------------------------------------------
    elapsed = time.monotonic() - start_time
    print_summary(config, records, json_path, new_page_id, elapsed)

    return 0 if new_page_id else 1


# =============================================================================
# Script entry point
# =============================================================================
# sys.exit() passes the integer return value of main() to the shell as the
# process exit code: 0 = success, 1 = failure. This lets shell scripts and
# CI pipelines detect whether the demo ran successfully.

if __name__ == "__main__":
    sys.exit(main())
