
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
from utils.logging_config import setup_logging, get_logger

logger = get_logger("main")


def print_banner():
    """Print application banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║       ███╗   ███╗ ██████╗     ██████╗███╗   ███╗██████╗ ██████╗      ║
    ║       ████╗ ████║██╔═══██╗   ██╔════╝████╗ ████║██╔══██╗██╔══██╗     ║
    ║       ██╔████╔██║██║   ██║   ██║     ██╔████╔██║██║  ██║██████╔╝     ║
    ║       ██║╚██╔╝██║██║▄▄ ██║   ██║     ██║╚██╔╝██║██║  ██║██╔══██╗     ║
    ║       ██║ ╚═╝ ██║╚██████╔╝   ╚██████╗██║ ╚═╝ ██║██████╔╝██████╔╝     ║
    ║       ╚═╝     ╚═╝ ╚══▀▀═╝     ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═════╝      ║
    ║                                                                      ║
    ║        MQ CMDB HIERARCHICAL AUTOMATION SYSTEM                        ║
    ║        Version 1.0                                                   ║
    ║        Processes IBM MQ CMDB data and generates:                     ║
    ║        • Hierarchical organization topology diagrams                 ║
    ║        • Application-focused connection diagrams                     ║
    ║        • Individual MQ manager connection diagrams                   ║
    ║        • JSON data with full organizational enrichment               ║
    ║                                                                      ║
    ║        Started: 2026-02-12 08:09:33                                  ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝

    """
    logger.info(banner)


def print_usage():
    """Print usage information."""
    usage = """
USAGE:
    python main.py                    # Run full pipeline (processing only)
    python main.py --help             # Show this help message

    # For database export (run first):
    python db_export.py --batch --profile production

REQUIRED INPUT FILES:
    output/all_MQCMDB_assets.json     # MQ CMDB export data (from db_export.py)
    input/org_hierarchy.json          # Organizational hierarchy
    input/app_to_qmgr.json            # Application to MQ manager mapping

OUTPUT DIRECTORIES:
    output/data/                      # JSON data files (processed, baseline, changes)
    output/diagrams/topology/         # Main topology diagrams (DOT, SVG, PDF)
    output/diagrams/applications/     # Application-focused diagrams
    output/diagrams/individual/       # Per-MQ-manager diagrams
    output/diagrams/filtered/         # Filtered view diagrams
    output/reports/                   # HTML reports (change, gateway analytics)
    output/exports/                   # Excel exports and EA documentation

BATCH EXECUTION:
    Windows:  run_batch_export.bat    # Runs db_export + orchestrator
    Linux:    deploy/run_pipeline.sh  # Runs db_export + orchestrator

REQUIREMENTS:
    • Python 3.7+
    • GraphViz (dot and sfdp commands) - optional for PDF generation

For more information, see README.md
    """
    logger.info(usage)


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
        logger.warning("\nWARNINGS:\n")
        for warning in warnings:
            logger.warning(f"  ! {warning}")
        logger.info("")

    # Display blocking issues
    if issues:
        logger.error("\nPREREQUISITES NOT MET:\n")
        for issue in issues:
            logger.error(f"  ✗ {issue}")
        logger.info("\nPlease resolve these issues before running the pipeline.\n")
        return False

    return True


def main():
    """Main entry point."""
    # Handle help argument
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        setup_logging(banner_config={"enabled": False})
        print_usage()
        return 0

    # Initialize logging
    from config.settings import Config
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    setup_logging(verbose=verbose, banner_config=Config.BANNER_CONFIG)

    # Print banner
    print_banner()

    # Check prerequisites
    logger.info("Checking prerequisites...")
    if not check_prerequisites():
        return 1

    logger.info("✓ All prerequisites met\n")

    # Run pipeline
    try:
        orchestrator = MQCMDBOrchestrator()
        orchestrator.run_full_pipeline()
        return 0

    except KeyboardInterrupt:
        logger.warning("\n\nPipeline interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"\nFATAL ERROR: {e}")
        logger.exception("Fatal pipeline error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
