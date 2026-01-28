"""Configuration settings for MQ CMDB automation system."""

import os
from pathlib import Path

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
   
    # ==================== DATABASE ====================
    DEFAULT_PROFILE = "production"
    DEFAULT_DB_PORT = 3306
   
    # ==================== EXPORT SETTINGS ====================
    DEFAULT_FORMAT = "json"
    LOG_RETENTION_DAYS = 7
   
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
