"""Configuration settings for MQ CMDB automation system."""

import os
import random
from pathlib import Path
from typing import Dict, List


def generate_department_colors(num_departments: int) -> List[Dict[str, str]]:
    """
    Generate random, distinct colors for departments.

    Args:
        num_departments: Number of department color schemes to generate

    Returns:
        List of color dictionaries for departments
    """
    # Base hues to ensure good distribution and distinction
    base_hues = []
    hue_step = 360 / num_departments

    # Start at a random offset for variety
    start_hue = random.randint(0, 360)

    for i in range(num_departments):
        hue = (start_hue + i * hue_step) % 360
        base_hues.append(hue)

    # Shuffle to avoid gradual progression
    random.shuffle(base_hues)

    color_schemes = []
    for hue in base_hues:
        # Generate color scheme with varying saturation and lightness
        colors = {
            'dept_bg': hsl_to_hex(hue, 0.45, 0.92),      # Light background
            'dept_border': hsl_to_hex(hue, 0.65, 0.45),  # Darker border
            'biz_bg': hsl_to_hex(hue, 0.40, 0.88),       # Slightly darker for nesting
            'biz_border': hsl_to_hex(hue, 0.70, 0.40),   # Even darker border
            'app_bg': hsl_to_hex(hue, 0.35, 0.85),       # More nested
            'app_border': hsl_to_hex(hue, 0.75, 0.35),   # Darker border
            'qm_bg': hsl_to_hex(hue, 0.40, 0.88),        # Same as biz
            'qm_border': hsl_to_hex(hue, 0.75, 0.35),    # Darker
            'qm_text': hsl_to_hex(hue, 0.80, 0.20)       # Dark text
        }
        color_schemes.append(colors)

    return color_schemes


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """
    Convert HSL to hex color.

    Args:
        h: Hue (0-360)
        s: Saturation (0-1)
        l: Lightness (0-1)

    Returns:
        Hex color string (e.g., '#ff5733')
    """
    h = h / 360.0

    def hue_to_rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1/6:
            return p + (q - p) * 6 * t
        if t < 1/2:
            return q
        if t < 2/3:
            return p + (q - p) * (2/3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

    return '#{:02x}{:02x}{:02x}'.format(
        int(r * 255),
        int(g * 255),
        int(b * 255)
    )


class Config:
    """Central configuration for the MQ CMDB system."""
   
    # ==================== PATHS ====================
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_DIR = BASE_DIR / "Database"
    INPUT_DIR = BASE_DIR / "input"
    OUTPUT_DIR = BASE_DIR / "output"
    LOGS_DIR = BASE_DIR / "logs"
    INDIVIDUAL_DIAGRAMS_DIR = OUTPUT_DIR / "individual_diagrams"
   
    # Credential files
    CREDENTIALS_FILE = BASE_DIR / "db_credentials.enc"
    SALT_FILE = BASE_DIR / "db_credentials.salt"
   
    # Data files
    INPUT_JSON = OUTPUT_DIR / "all_MQCMDB_assets.json"
    PROCESSED_JSON = OUTPUT_DIR / "mq_cmdb_processed.json"
    TOPOLOGY_DOT = OUTPUT_DIR / "mq_topology.dot"
    TOPOLOGY_PDF = OUTPUT_DIR / "mq_topology.pdf"
   
    # Hierarchy input files
    ORG_HIERARCHY_JSON = INPUT_DIR / "org_hierarchy.json"
    APP_TO_QMGR_JSON = INPUT_DIR / "app_to_qmgr.json"
    GATEWAYS_JSON = INPUT_DIR / "gateways.json"
   
    # ==================== DATABASE ====================
    DEFAULT_PROFILE = "production"
    DEFAULT_DB_PORT = 3306
   
    # ==================== EXPORT SETTINGS ====================
    DEFAULT_FORMAT = "json"
    LOG_RETENTION_DAYS = 7

    # Output Cleanup Settings
    ENABLE_OUTPUT_CLEANUP = True       # Enable automatic cleanup of old output files
    OUTPUT_RETENTION_DAYS = 30         # Delete output files older than this many days
    # File patterns to clean up (timestamped files only)
    OUTPUT_CLEANUP_PATTERNS = [
        "change_report_*.html",
        "changes_*.json",
        "gateway_analytics_*.html",
        "gateway_analytics_*.json",
        "mqcmdb_inventory_*.xlsx",
        "EA_Documentation_*.txt"
    ]

    # Multi-Format Export Settings
    EXPORT_SVG = True  # Export diagrams to SVG format
    EXPORT_PNG = True  # Export diagrams to PNG format
    PNG_DPI = 200      # Resolution for PNG exports
    EXPORT_EXCEL = True  # Generate Excel inventory report

    # Change Detection Settings
    ENABLE_CHANGE_DETECTION = True  # Enable change detection and diff reports
    CHANGE_THRESHOLD_PERCENT = 20   # Report queue count changes > this percentage

    # Gateway Analytics Settings
    ENABLE_GATEWAY_ANALYTICS = True  # Enable gateway analytics reports

    # ==================== CONFLUENCE SETTINGS ====================
    # Set CONFLUENCE_ENABLED = True to auto-publish to Confluence after pipeline runs
    CONFLUENCE_ENABLED = False
    CONFLUENCE_URL = ""              # e.g., "https://company.atlassian.net/wiki" or "https://confluence.company.com"
    CONFLUENCE_SPACE_KEY = ""        # e.g., "MQCMDB"
    CONFLUENCE_PAGE_TITLE = "MQ CMDB - Enterprise Architecture Documentation"
    CONFLUENCE_PARENT_PAGE_ID = None  # Optional: ID of parent page to nest under

    # Authentication (choose one method):
    # Method 1: Basic Auth (Cloud uses email + API token, Server uses username + password)
    CONFLUENCE_USERNAME = ""         # Email for Cloud, username for Server
    CONFLUENCE_API_TOKEN = ""        # API token (Cloud) or password (Server)
    # Method 2: Personal Access Token (Server/Data Center only)
    CONFLUENCE_PAT = ""              # Personal Access Token

    # Attachment settings
    CONFLUENCE_ATTACH_PDF = True     # Attach main topology PDF
    CONFLUENCE_ATTACH_EXCEL = True   # Attach Excel inventory

    # Deduplication
    DEDUP_ASSET_FIELD = "asset"
    DEDUP_IGNORE_TYPE = "QCluster"
   
    # ==================== GRAPHVIZ SETTINGS ====================
    # Standard layout settings
    GRAPHVIZ_RANKDIR = "LR"
    GRAPHVIZ_BGCOLOR = "#f7f9fb"
    GRAPHVIZ_NODESEP = 0.8
    GRAPHVIZ_RANKSEP = 1.1
   
    # Hierarchical layout settings (sfdp)
    HIERARCHICAL_LAYOUT = "sfdp"
    HIERARCHICAL_OVERLAP = "false"
    HIERARCHICAL_PACK = "true"
    HIERARCHICAL_PACKMODE = "clust"
    HIERARCHICAL_NODESEP = 0.9
    HIERARCHICAL_RANKSEP = 1.5
   
    # ==================== COLOR SCHEMES ====================
    # External Organization Colors (Purple/Lavender)
    EXTERNAL_ORG_COLORS = {
        'org_bg': '#daeca8',
        'org_border': '#6a3fa0',
        'dept_bg': '#e8ddf5',
        'dept_border': '#5a2f90',
        'biz_bg': '#e8ddf5',
        'biz_border': '#5a2f90',
        'app_bg': '#dfd2f3',
        'app_border': '#4f2788',
        'qm_bg': '#e8ddf5',
        'qm_border': '#4f2788',
        'qm_text': '#2d1b4a'
    }
   
    # Internal Organization Colors
    INTERNAL_ORG_COLORS = [
        # Finance/First Department - Blue
        {
            'org_bg': '#FEDCDB',
            'org_border': '#2d3e50',
            'dept_bg': '#e6f2ff',
            'dept_border': '#1f78d1',
            'biz_bg': '#d3e7ff',
            'biz_border': '#1c6ecf',
            'app_bg': '#c7ddff',
            'app_border': '#155fb3',
            'qm_bg': '#d3e7ff',
            'qm_border': '#155fb3',
            'qm_text': '#0f2a45'
        },
        # Operations/Second Department - Green
        {
            'org_bg': '#FEDCDB',
            'org_border': '#2d3e50',
            'dept_bg': '#e3f7ef',
            'dept_border': '#1fa463',
            'biz_bg': '#c9f2dd',
            'biz_border': '#1c9e55',
            'app_bg': '#bdf0d3',
            'app_border': '#158a4b',
            'qm_bg': '#c9f2dd',
            'qm_border': '#158a4b',
            'qm_text': '#145a32'
        }
    ]

    # Internal Gateway Colors (Orange/Amber - for inter-departmental gateways)
    INTERNAL_GATEWAY_COLORS = {
        'gateway_bg': '#fff3e0',      # Light orange background
        'gateway_border': '#ff9800',  # Orange border
        'qm_bg': '#ffe0b2',           # Slightly darker orange for MQ managers
        'qm_border': '#f57c00',       # Dark orange border
        'qm_text': '#e65100'          # Dark orange text
    }

    # External Gateway Colors (Teal/Cyan - for external organization gateways)
    EXTERNAL_GATEWAY_COLORS = {
        'gateway_bg': '#e0f7fa',      # Light teal background
        'gateway_border': '#00bcd4',  # Cyan border
        'qm_bg': '#b2ebf2',           # Slightly darker teal for MQ managers
        'qm_border': '#0097a7',       # Dark cyan border
        'qm_text': '#006064'          # Dark cyan text
    }

    INDIVIDUAL_DIAGRAM_COLORS = {
        "central": {"fill": "#ffd700", "border": "#ff8c00", "text": "#000000"},
        "inbound": {"fill": "#d5f5e3", "border": "#82e0aa", "arrow": "#28a745"},
        "outbound": {"fill": "#d6eaf8", "border": "#85c1e9", "arrow": "#2874a6"},
        "external": {"fill": "#fef9e7", "border": "#f39c12", "arrow": "#f39c12"}
    }
   
    # ==================== FIELD MAPPINGS ====================
    FIELD_MAPPINGS = {
        "mqmanager": "MQmanager",
        "asset": "asset",
        "asset_type": "asset_type",
        "directorate": "directorate",
        "kalala_comments": "Kalala_Comments1",
        "mq_host": "MQ_host",
        "extrainfo": "extrainfo",
        "impact": "impact",
        "appgroup": "APPGroup"
    }
   
    # Asset type keywords
    ASSET_TYPE_LOCAL = "local"
    ASSET_TYPE_REMOTE = "remote"
    ASSET_TYPE_ALIAS = "alias"
   
    # Kalala comments values
    COMMENT_SENDER = "SENDER"
    COMMENT_RECEIVER = "RECEIVER"
   
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        for directory in [cls.DATABASE_DIR, cls.INPUT_DIR, cls.OUTPUT_DIR,
                         cls.LOGS_DIR, cls.INDIVIDUAL_DIAGRAMS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
   
    @classmethod
    def get_log_file(cls, prefix="export"):
        """Generate timestamped log filename."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls.LOGS_DIR / f"{prefix}_{timestamp}.log"
