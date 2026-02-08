#!/usr/bin/env python3
"""
MQ CMDB Hierarchical Automation System - Unified CLI

Provides a modern command-line interface for all system operations:
  - run:      Execute the full pipeline
  - export:   Database export operations
  - diagrams: Regenerate diagrams from existing processed data
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import click

from utils.logging_config import setup_logging, get_logger, cleanup_old_logs
from utils.common import setup_utf8_output

logger = get_logger("cli")


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose/debug output')
@click.option('--dry-run', is_flag=True, help='Show what would be executed without running')
@click.pass_context
def cli(ctx, verbose, dry_run):
    """MQ CMDB Hierarchical Automation System.

    Process IBM MQ CMDB data and generate topology diagrams,
    change reports, and multi-format exports.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['dry_run'] = dry_run

    setup_utf8_output()
    from config.settings import Config
    setup_logging(verbose=verbose, banner_config=Config.BANNER_CONFIG)


@cli.command()
@click.option('--skip-export', is_flag=True, help='Skip database export, use existing data')
@click.option('--diagrams-only', is_flag=True, help='Only regenerate diagrams from existing processed data')
@click.option('--workers', '-w', type=int, default=None, help='Number of parallel workers for diagram generation')
@click.option('--profile', default='production', help='Database credential profile')
@click.pass_context
def run(ctx, skip_export, diagrams_only, workers, profile):
    """Run the full MQ CMDB pipeline.

    Executes the complete workflow: data loading, processing, enrichment,
    change detection, diagram generation, analytics, and exports.

    \b
    Examples:
      python cli.py run                          # Full pipeline
      python cli.py run --skip-export            # Skip DB export
      python cli.py run --diagrams-only          # Only regenerate diagrams
      python cli.py run --workers 4              # Use 4 parallel workers
      python cli.py -v run                       # Verbose output
    """
    from orchestrator import MQCMDBOrchestrator

    dry_run = ctx.obj.get('dry_run', False)

    if dry_run:
        logger.info("[DRY-RUN] Would execute full pipeline with:")
        logger.info(f"  skip_export={skip_export}")
        logger.info(f"  diagrams_only={diagrams_only}")
        logger.info(f"  workers={workers}")
        logger.info(f"  profile={profile}")
        return

    # Clean up old logs
    cleanup_old_logs()

    orchestrator = MQCMDBOrchestrator(
        skip_export=skip_export,
        diagrams_only=diagrams_only,
        workers=workers,
        dry_run=dry_run,
    )
    success = orchestrator.run_full_pipeline()
    sys.exit(0 if success else 1)


@cli.group()
@click.pass_context
def export(ctx):
    """Database export operations.

    Export data from MariaDB/MySQL to JSON files using encrypted credentials.
    """
    pass


@export.command()
@click.option('--profile', default='production', help='Credential profile name')
@click.option('--skip-dedup', is_flag=True, help='Skip deduplication')
@click.pass_context
def batch(ctx, profile, skip_dedup):
    """Batch export all SQL queries in the Database directory.

    \b
    Examples:
      python cli.py export batch
      python cli.py export batch --profile staging
      python cli.py export batch --skip-dedup
    """
    import argparse

    from config.settings import Config
    from core.credentials import CredentialsManager
    from core.database import DatabaseConnection
    from db_export import process_batch_queries, load_credentials

    creds = load_credentials(profile)
    if not creds:
        logger.error(f"No credentials found for profile '{profile}'.")
        logger.info("Run: python cli.py export setup --profile %s", profile)
        sys.exit(1)

    logger.info("Connecting to database...")
    db_conn = DatabaseConnection(
        host=creds['host'],
        user=creds['user'],
        password=creds['password'],
        database=creds['database'],
        port=creds.get('port', 3306)
    )

    if not db_conn.connect():
        sys.exit(1)

    try:
        args = argparse.Namespace(skip_dedup=skip_dedup)
        success = process_batch_queries(db_conn, args)
        sys.exit(0 if success else 1)
    finally:
        db_conn.close()


@export.command()
@click.option('--profile', default='production', help='Credential profile name')
@click.option('--table', default=None, help='Table name to export')
@click.option('--query', default=None, help='Custom SQL query')
@click.option('--query-file', type=click.Path(exists=True), default=None, help='Path to SQL query file')
@click.option('--output', '-o', required=True, type=click.Path(), help='Output file path')
@click.option('--skip-dedup', is_flag=True, help='Skip deduplication')
@click.pass_context
def query(ctx, profile, table, query, query_file, output, skip_dedup):
    """Export a single query result to JSON.

    \b
    Examples:
      python cli.py export query --table myTable -o output/data.json
      python cli.py export query --query-file Database/my_query.sql -o output/result.json
      python cli.py export query --query "SELECT * FROM t LIMIT 10" -o output/sample.json
    """
    import argparse

    from core.database import DatabaseConnection
    from db_export import process_single_query, load_credentials

    creds = load_credentials(profile)
    if not creds:
        logger.error(f"No credentials found for profile '{profile}'.")
        sys.exit(1)

    logger.info("Connecting to database...")
    db_conn = DatabaseConnection(
        host=creds['host'],
        user=creds['user'],
        password=creds['password'],
        database=creds['database'],
        port=creds.get('port', 3306)
    )

    if not db_conn.connect():
        sys.exit(1)

    try:
        args = argparse.Namespace(
            table=table, query=query, query_file=query_file,
            output=output, skip_dedup=skip_dedup
        )
        success = process_single_query(db_conn, args)
        sys.exit(0 if success else 1)
    finally:
        db_conn.close()


@export.command()
@click.option('--profile', default='production', help='Profile name to configure')
def setup(profile):
    """Setup encrypted database credentials interactively.

    \b
    Example:
      python cli.py export setup --profile production
    """
    from db_export import setup_credentials
    setup_credentials(profile)


@cli.command()
@click.option('--workers', '-w', type=int, default=None, help='Number of parallel workers')
@click.pass_context
def diagrams(ctx, workers):
    """Regenerate diagrams from existing processed data.

    Loads the previously processed JSON and runs only diagram generation
    steps (topology, application, individual, filtered views, exports).

    \b
    Examples:
      python cli.py diagrams
      python cli.py diagrams --workers 4
      python cli.py -v diagrams
    """
    from orchestrator import MQCMDBOrchestrator

    dry_run = ctx.obj.get('dry_run', False)

    if dry_run:
        logger.info("[DRY-RUN] Would regenerate diagrams with workers=%s", workers)
        return

    cleanup_old_logs()

    orchestrator = MQCMDBOrchestrator(
        diagrams_only=True,
        workers=workers,
        dry_run=dry_run,
    )
    success = orchestrator.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    cli()
