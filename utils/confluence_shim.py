"""
Confluence integration shim for the MQ CMDB project.

Loads project-specific configuration from config/confluence_config.json
and delegates to the generic scripts.common.confluence_client.

Usage:
    from utils.confluence_shim import publish_ea_documentation, publish_application_diagrams

    # Publish the EA doc to Confluence
    publish_ea_documentation("/path/to/EA_Documentation.txt")

    # Attach each application SVG to its own Confluence page (per diagram_pages mapping)
    publish_application_diagrams()
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from utils.logging_config import get_logger

logger = get_logger("utils.confluence_shim")

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
    from scripts.common.confluence_client import ConfluenceClient

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
    from scripts.common.confluence_client import ConfluenceError

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
    from scripts.common.confluence_client import ConfluenceError

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
