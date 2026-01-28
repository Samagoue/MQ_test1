#!/usr/bin/env python3
"""
MQ CMDB Hierarchical Automation System - Main Entry Point

This is the main entry point for the MQ CMDB hierarchical automation pipeline.
It orchestrates the complete workflow from data loading through diagram generation.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from orchestrator import MQCMDBOrchestrator
from utils.common import safe_print


def print_banner():
    """Print application banner."""
    banner = """

    ╔════════════════════════════════════════════════════════════════════╗
    ║                                                                    ║
    ║       ███╗   ███╗ ██████╗      ██████╗███╗   ███╗██████╗ ██████╗   ║
    ║       ████╗ ████║██╔═══██╗    ██╔════╝████╗ ████║██╔══██╗██╔══██╗  ║
    ║       ██╔████╔██║██║   ██║    ██║     ██╔████╔██║██████╔╝██████╔╝  ║
    ║       ██║╚██╔╝██║██║   ██║    ██║     ██║╚██╔╝██║██╔══██╗██╔══██╗  ║
    ║       ██║ ╚═╝ ██║╚██████╔╝    ╚██████╗██║ ╚═╝ ██║██████╔╝██║  ██║  ║
    ║       ╚═╝     ╚═╝ ╚═════╝      ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝  ║
    ║        MQ CMDB HIERARCHICAL AUTOMATION SYSTEM                      ║
    ║        Version 1.0                                                 ║
    ║                                                                    ║
    ║        Processes IBM MQ CMDB data and generates:                   ║
    ║        • Hierarchical organization topology diagrams               ║
    ║        • Individual MQ manager connection diagrams                 ║
    ║        • JSON data with full organizational enrichment             ║
    ║                                                                    ║
    ╚════════════════════════════════════════════════════════════════════╝
    """
    safe_print(banner)


def print_usage():
    """Print usage information."""
    usage = """
USAGE:
    python main.py                    # Run full pipeline
    python main.py --help             # Show this help message

REQUIRED INPUT FILES:
    output/all_MQCMDB_assets.json    # MQ CMDB export data
    input/org_hierarchy.json          # Organizational hierarchy
    input/app_to_qmgr.json            # Application to MQ manager mapping

OUTPUT FILES:
    output/mq_cmdb_processed.json     # Enriched data with hierarchy
    output/mq_topology.dot            # GraphViz DOT file
    output/mq_topology.pdf            # Hierarchical topology diagram
    output/individual_diagrams/*.pdf  # Individual MQ manager diagrams

DIRECTORY STRUCTURE:
    project_root/
    ├── main.py                       # This file
    ├── orchestrator.py               # Main orchestrator
    ├── config/
    │   └── settings.py               # Configuration
    ├── processors/
    │   ├── mqmanager_processor.py    # MQ relationship processing
    │   └── hierarchy_mashup.py       # Hierarchy enrichment
    ├── generators/
    │   ├── graphviz_hierarchical.py  # Hierarchical diagram generator
    │   └── graphviz_individual.py    # Individual diagram generator
    ├── utils/
    │   ├── common.py                 # Common utilities
    │   └── file_io.py                # File I/O utilities
    ├── input/                        # Input data files
    ├── output/                       # Generated outputs
    └── logs/                         # Processing logs

REQUIREMENTS:
    • Python 3.7+
    • GraphViz (dot and sfdp commands)

For more information, see README.md
    """
    safe_print(usage)


def check_prerequisites():
    """Check if prerequisites are met."""
    import shutil
    from config.settings import Config
   
    issues = []
    warnings = []
   
    # Check GraphViz (warning only, not blocking)
    if not shutil.which('dot') and not shutil.which('sfdp'):
        warnings.append("GraphViz not found - DOT files will be created but PDFs will be skipped")
        warnings.append("  Install from: https://graphviz.org/download/")
   
    # Check required input files
    if not Config.INPUT_JSON.exists():
        issues.append(f"Required file not found: {Config.INPUT_JSON}")
   
    if not Config.ORG_HIERARCHY_JSON.exists():
        issues.append(f"Required file not found: {Config.ORG_HIERARCHY_JSON}")
   
    if not Config.APP_TO_QMGR_JSON.exists():
        issues.append(f"Required file not found: {Config.APP_TO_QMGR_JSON}")
   
    # Display warnings
    if warnings:
        safe_print("\n⚠ WARNINGS:\n")
        for warning in warnings:
            safe_print(f"  ! {warning}")
        safe_print("")
   
    # Display blocking issues
    if issues:
        safe_print("\n⚠ PREREQUISITES NOT MET:\n")
        for issue in issues:
            safe_print(f"  ✗ {issue}")
        safe_print("\nPlease resolve these issues before running the pipeline.\n")
        return False
   
    return True


def main():
    """Main entry point."""
    # Handle help argument
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        print_usage()
        return 0
   
    # Print banner
    print_banner()
   
    # Check prerequisites
    safe_print("Checking prerequisites...")
    if not check_prerequisites():
        return 1
   
    safe_print("✓ All prerequisites met\n")
   
    # Run pipeline
    try:
        orchestrator = MQCMDBOrchestrator()
        orchestrator.run_full_pipeline()
        return 0
   
    except KeyboardInterrupt:
        safe_print("\n\n⚠ Pipeline interrupted by user")
        return 130
   
    except Exception as e:
        safe_print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())