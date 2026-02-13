
"""Configuration settings for MQ CMDB automation system."""

import random
from pathlib import Path
from typing import Dict, List


def generate_department_colors(num_departments: int, seed: int = None) -> List[Dict[str, str]]:
    """
    Generate distinct colors for departments with deterministic output.

    Args:
        num_departments: Number of department color schemes to generate
        seed: Optional seed for reproducibility. If None, uses a fixed seed
              based on num_departments for consistent colors across runs.

    Returns:
        List of color dictionaries for departments
    """
    # Use a deterministic seed for reproducible colors across runs
    # This ensures diagrams look the same each time they're generated
    if seed is None:
        seed = 42 + num_departments  # Fixed seed based on department count
    rng = random.Random(seed)

    # Base hues to ensure good distribution and distinction
    base_hues = []
    hue_step = 360 / max(num_departments, 1)

    # Start at a fixed offset for consistency
    start_hue = rng.randint(0, 360)

    for i in range(num_departments):
        hue = (start_hue + i * hue_step) % 360
        base_hues.append(hue)

    # Shuffle using the seeded RNG for deterministic but varied order
    rng.shuffle(base_hues)

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

    # Output subdirectories
    DATA_DIR = OUTPUT_DIR / "data"
    DIAGRAMS_DIR = OUTPUT_DIR / "diagrams"
    REPORTS_DIR = OUTPUT_DIR / "reports"
    EXPORTS_DIR = OUTPUT_DIR / "exports"

    # Diagram subdirectories
    TOPOLOGY_DIR = DIAGRAMS_DIR / "topology"
    INDIVIDUAL_DIAGRAMS_DIR = DIAGRAMS_DIR / "individual"
    APPLICATION_DIAGRAMS_DIR = DIAGRAMS_DIR / "applications"
    FILTERED_VIEWS_DIR = DIAGRAMS_DIR / "filtered"

    # Credential files
    CREDENTIALS_FILE = BASE_DIR / "db_credentials.enc"
    SALT_FILE = BASE_DIR / "db_credentials.salt"

    # Data files
    INPUT_JSON = OUTPUT_DIR / "all_MQCMDB_assets.json"
    PROCESSED_JSON = DATA_DIR / "mq_cmdb_processed.json"
    BASELINE_JSON = DATA_DIR / "mq_cmdb_baseline.json"
    TOPOLOGY_DOT = TOPOLOGY_DIR / "mq_topology.dot"
    TOPOLOGY_PDF = TOPOLOGY_DIR / "mq_topology.pdf"
 
    # Hierarchy input files
    ORG_HIERARCHY_JSON = INPUT_DIR / "org_hierarchy.json"
    APP_TO_QMGR_JSON = INPUT_DIR / "app_to_qmgr.json"
    GATEWAYS_JSON = INPUT_DIR / "gateways.json"
    MQMANAGER_ALIASES_JSON = INPUT_DIR / "mqmanager_aliases.json"
    EXTERNAL_APPS_JSON = INPUT_DIR / "external_apps.json"
 
    # ==================== DATABASE ====================
    DEFAULT_PROFILE = "production"
    DEFAULT_DB_PORT = 3306
 
    # ==================== EXPORT SETTINGS ====================
    DEFAULT_FORMAT = "json"
    LOG_RETENTION_DAYS = 7

    # ==================== BANNER ====================
    BANNER_CONFIG = {
        "art_text": "MQ CMDB",
        "title": "MQ CMDB HIERARCHICAL AUTOMATION SYSTEM",
        "subtitle": "Processes IBM MQ CMDB data and generates:\n• Hierarchical organization topology diagrams\n• Application-focused connection diagrams\n• Individual MQ manager connection diagrams\n• JSON data with full organizational enrichment",
        "version": "1.0",
    }

    # Output Cleanup Settings
    ENABLE_OUTPUT_CLEANUP = True       # Enable automatic cleanup of old output files
    OUTPUT_RETENTION_DAYS = 30         # Delete output files older than this many days
    # File patterns to clean up (timestamped files only, relative to OUTPUT_DIR)
    OUTPUT_CLEANUP_PATTERNS = [
        "reports/change_report_*.html",
        "reports/gateway_analytics_*.html",
        "data/changes_*.json",
        "data/gateway_analytics_*.json",
        "exports/mqcmdb_inventory_*.xlsx",
        "exports/EA_Documentation_*.txt"
    ]

    # Parallel Processing
    PARALLEL_WORKERS = None  # None = auto (min(4, cpu_count)); override with --workers or MQCMDB_WORKERS env var

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
        # First Department - Blue
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
        # Second Department - Green
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

    # ==================== CONNECTION COLORS ====================
    # Connection type colors for diagram edges
    CONNECTION_COLORS = {
        "same_dept": "#1f78d1",        # Blue - same department connections
        "cross_dept": "#ff6b5a",       # Coral - cross-department connections
        "cross_org": "#b455ff",        # Purple - cross-organization/external connections
        "bidirectional": "#00897b",    # Teal - bidirectional relationships
        "reverse": "#28a745",          # Green - reverse connections to focus
    }

    # Arrowhead styles by connection type
    # All unidirectional: pointed arrow at destination, bullet at origin
    CONNECTION_ARROWHEADS = {
        "same_dept": "normal",         # Pointed arrow at destination
        "cross_dept": "normal",        # Pointed arrow at destination
        "cross_org": "normal",         # Pointed arrow at destination
        "bidirectional": "normal",     # Pointed arrows both directions
    }

    # Arrowtail styles (bullet at origin for unidirectional)
    CONNECTION_ARROWTAILS = {
        "same_dept": "dot",            # Bullet at origin
        "cross_dept": "dot",           # Bullet at origin
        "cross_org": "dot",            # Bullet at origin
        "bidirectional": "dot",        # Bullet at both ends (with dir=both)
    }
 
    # ==================== FIELD MAPPINGS ====================
    FIELD_MAPPINGS = {
        "mqmanager": "MQmanager",
        "asset": "asset",
        "asset_type": "asset_type",
        "directorate": "directorate",
        "role": "Role",
        "mq_host": "MQ_host",
        "extrainfo": "extrainfo",
        "impact": "impact",
        "appgroup": "APPGroup"
    }
 
    # Asset type keywords
    ASSET_TYPE_LOCAL = "local"
    ASSET_TYPE_REMOTE = "remote"
    ASSET_TYPE_ALIAS = "alias"
 
    # Role field values
    ROLE_SENDER = "SENDER"
    ROLE_RECEIVER = "RECEIVER"
 
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        directories = [
            cls.DATABASE_DIR,
            cls.INPUT_DIR,
            cls.OUTPUT_DIR,
            cls.LOGS_DIR,
            # Output subdirectories
            cls.DATA_DIR,
            cls.DIAGRAMS_DIR,
            cls.REPORTS_DIR,
            cls.EXPORTS_DIR,
            # Diagram subdirectories
            cls.TOPOLOGY_DIR,
            cls.INDIVIDUAL_DIAGRAMS_DIR,
            cls.APPLICATION_DIAGRAMS_DIR,
            cls.FILTERED_VIEWS_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
 
    @classmethod
    def get_log_file(cls, prefix="export"):
        """Generate timestamped log filename."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls.LOGS_DIR / f"{prefix}_{timestamp}.log"


