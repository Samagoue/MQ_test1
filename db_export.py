
#!/usr/bin/env python3
"""
Database Export Script - Batch Process SQL Queries
Exports data from MariaDB to JSON files with encrypted credentials
Processes all SQL files in the Database directory
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import Config
from core.credentials import CredentialsManager
from core.database import DatabaseConnection
from utils.common import setup_utf8_output
from utils.logging_config import setup_logging, get_logger

logger = get_logger("db_export")


def process_batch_queries(db_conn: DatabaseConnection, args):
    """Process all SQL files in the query directory."""
    query_dir = Config.DATABASE_DIR
    output_dir = Config.OUTPUT_DIR

    # Check if query directory exists
    if not query_dir.exists():
        logger.error(f"Error: Query directory '{query_dir}' does not exist.")
        return False

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Find all SQL files
    sql_files = list(query_dir.glob('*.sql'))

    if not sql_files:
        logger.info(f"No SQL files found in '{query_dir}'")
        return False

    logger.info(f"\nFound {len(sql_files)} SQL file(s) to process")
    logger.info("=" * 70)

    # Process each SQL file
    success_count = 0
    fail_count = 0

    for sql_file in sql_files:
        try:
            # Get query name from filename (without extension)
            query_name = sql_file.stem

            # Determine output filename
            output_file = output_dir / f"{query_name}.json"

            logger.info(f"\nProcessing: {query_name}")
            logger.info("-" * 70)

            # Read query from file
            with open(sql_file, 'r', encoding='utf-8') as f:
                query = f.read().strip()

            # Execute query and process
            result = execute_and_save_query(db_conn, query, output_file, args)

            if result:
                success_count += 1
                logger.info(f"[SUCCESS] Saved to: {output_file}")
            else:
                fail_count += 1
                logger.warning(f"[FAILED] Could not process: {query_name}")

        except Exception as e:
            fail_count += 1
            logger.error(f"[ERROR] Processing {sql_file}: {str(e)}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info(f"BATCH PROCESSING COMPLETE")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Total: {len(sql_files)}")
    logger.info("=" * 70)

    return success_count > 0


def execute_and_save_query(db_conn: DatabaseConnection, query: str,
                           output_file: Path, args) -> bool:
    """Execute query and save to JSON file."""
    try:
        # Fetch data
        logger.info(f"Executing query...")
        columns, rows = db_conn.execute_query(query)

        if columns is None or rows is None:
            return False

        logger.info(f"Fetched {len(rows)} rows with {len(columns)} columns")

        # Convert to list of dictionaries
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert bytes to string if necessary
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='replace')
                row_dict[col] = value
            data.append(row_dict)

        # Apply deduplication if requested
        if not args.skip_dedup and data:
            from processors.deduplication import deduplicate_assets
            original_count = len(data)
            data = deduplicate_assets(data)
            dedup_count = original_count - len(data)
            if dedup_count > 0:
                logger.info(f"Removed {dedup_count} duplicate record(s)")

        logger.info(f"Final dataset: {len(data)} rows")

        # Save to JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        return True

    except Exception as e:
        logger.exception(f"Query executio failed: {e}")
        return False


def process_single_query(db_conn: DatabaseConnection, args):
    """Process a single query."""
    # Determine query
    if args.query_file:
        with open(args.query_file, 'r', encoding='utf-8') as f:
            query = f.read().strip()
    elif args.query:
        query = args.query
    elif args.table:
        # Validate table name to prevent SQL injection
        # Only allow alphanumeric characters and underscores
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.table):
            logger.error(f"Error: Invalid table name '{args.table}'. Table names must contain only letters, numbers, and underscores.")
            return False
        query = f"SELECT * FROM {args.table}"
    else:
        logger.error("Error: No query, query file, or table specified")
        return False

    # Execute and save
    return execute_and_save_query(db_conn, query, Path(args.output), args)


def setup_credentials(profile: str):
    """Setup encrypted credentials."""
    creds_manager = CredentialsManager(Config.CREDENTIALS_FILE, Config.SALT_FILE)
    creds_manager.setup_interactive(profile)


def load_credentials(profile: str) -> Optional[dict]:
    """Load encrypted credentials."""
    creds_manager = CredentialsManager(Config.CREDENTIALS_FILE, Config.SALT_FILE)
    return creds_manager.load_credentials(profile)


def main():
    """Main entry point."""
    setup_utf8_output()
    from config.settings import Config
    setup_logging(banner_config=Config.BANNER_CONFIG)
   
    parser = argparse.ArgumentParser(
        description='Export MariaDB data to JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup credentials
  python db_export.py --setup --profile production

  # Batch export all SQL queries in Database directory
  python db_export.py --profile production --batch

  # Export single table
  python db_export.py --profile production --table myTable --output output/data.json

  # Export custom query
  python db_export.py --profile production --query "SELECT * FROM myTable LIMIT 10" --output output/sample.json
        """
    )

    parser.add_argument('--setup', action='store_true',
                       help='Setup encrypted credentials')
    parser.add_argument('--profile', default='production',
                       help='Credential profile name (default: production)')
    parser.add_argument('--batch', action='store_true',
                       help='Process all SQL files in Database directory')
    parser.add_argument('--table', help='Table name to export')
    parser.add_argument('--query', help='Custom SQL query')
    parser.add_argument('--query-file', help='Path to SQL query file')
    parser.add_argument('--output', help='Output filename (for single query mode)')
    parser.add_argument('--skip-dedup', action='store_true',
                       help='Skip deduplication')

    args = parser.parse_args()

    # Setup mode
    if args.setup:
        setup_credentials(args.profile)
        return 0

    # Load credentials
    creds = load_credentials(args.profile)
    if not creds:
        logger.info(f"No credentials found for profile '{args.profile}'.")
        logger.info("Run with --setup to configure credentials first.")
        return 1

    # Connect to database
    logger.info(f"\nConnecting to database...")
    db_conn = DatabaseConnection(
        host=creds['host'],
        user=creds['user'],
        password=creds['password'],
        database=creds['database'],
        port=creds.get('port', 3306)
    )

    if not db_conn.connect():
        return 1

    try:
        # Process queries
        if args.batch:
            success = process_batch_queries(db_conn, args)
        else:
            if not args.output:
                logger.error("Error: --output is required for single query mode")
                return 1
            success = process_single_query(db_conn, args)

        return 0 if success else 1

    finally:
        db_conn.close()


if __name__ == "__main__":
    sys.exit(main())


