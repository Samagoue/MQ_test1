"""
Confluence Data Sync Utility

Fetches table data from Confluence pages and updates local JSON files:
- app_to_qmgr.json (Application to Queue Manager mapping)
- gateways.json (Gateway definitions)
- org_hierarchy.json (Organizational hierarchy)

Usage:
    python -m utils.confluence_sync --config confluence_config.json

Or import and use programmatically:
    from utils.confluence_sync import ConfluenceSync
    sync = ConfluenceSync(config)
    sync.sync_all()
"""

import json
import os
import re
import getpass
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    requests = None
    print("⚠ requests library not installed. Install with: pip install requests")


class HTMLTableParser(HTMLParser):
    """Parse HTML tables into structured data."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ""
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_header = False
        self.headers = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
            self.headers = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.in_header = (tag == 'th')
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag == 'table':
            if self.current_table:
                self.tables.append(self.current_table)
            self.in_table = False
        elif tag == 'tr' and self.in_table:
            if self.current_row:
                if self.headers:
                    self.current_table.append(self.current_row)
                elif all(isinstance(c, str) for c in self.current_row):
                    # First row with content becomes headers
                    self.headers = self.current_row
            self.in_row = False
        elif tag in ('td', 'th') and self.in_cell:
            cell_value = self.current_cell.strip()
            self.current_row.append(cell_value)
            self.in_cell = False
            self.in_header = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def get_tables_as_dicts(self) -> List[List[Dict[str, str]]]:
        """Convert parsed tables to list of dictionaries."""
        result = []
        for table in self.tables:
            if not table:
                continue
            # Use first row as headers if available
            headers = self.headers if self.headers else [f"col_{i}" for i in range(len(table[0]))]
            rows = []
            for row in table:
                if len(row) == len(headers):
                    rows.append(dict(zip(headers, row)))
            result.append(rows)
        return result


class ConfluenceSync:
    """Sync data from Confluence tables to local JSON files."""

    # Expected column mappings for each table type
    TABLE_SCHEMAS = {
        'app_to_qmgr': {
            'required_columns': ['QmgrName', 'Application'],
            'column_aliases': {
                'Queue Manager': 'QmgrName',
                'QueueManager': 'QmgrName',
                'MQ Manager': 'QmgrName',
                'MQManager': 'QmgrName',
                'App': 'Application',
                'AppName': 'Application',
                'Application Name': 'Application'
            }
        },
        'gateways': {
            'required_columns': ['QmgrName', 'Scope'],
            'optional_columns': ['Description'],
            'column_aliases': {
                'Queue Manager': 'QmgrName',
                'QueueManager': 'QmgrName',
                'MQ Manager': 'QmgrName',
                'Gateway': 'QmgrName',
                'Gateway Name': 'QmgrName',
                'Type': 'Scope',
                'Gateway Type': 'Scope',
                'Desc': 'Description'
            }
        },
        'org_hierarchy': {
            'required_columns': ['Biz_Ownr', 'Organization', 'Department'],
            'optional_columns': ['Org_Type'],
            'column_aliases': {
                'Business Owner': 'Biz_Ownr',
                'BizOwner': 'Biz_Ownr',
                'Directorate': 'Biz_Ownr',
                'Org': 'Organization',
                'Org Name': 'Organization',
                'Dept': 'Department',
                'Department Name': 'Department',
                'Type': 'Org_Type',
                'OrgType': 'Org_Type',
                'Organization Type': 'Org_Type'
            }
        }
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Confluence sync.

        Args:
            config: Configuration dictionary with:
                - base_url: Confluence base URL (e.g., https://confluence.company.com)
                - username: Confluence username (or set CONFLUENCE_USER env var)
                - api_token: API token or password (or set CONFLUENCE_TOKEN env var)
                - pages: Dict mapping table type to page ID or page title
                    - app_to_qmgr: Page ID/title for application mapping
                    - gateways: Page ID/title for gateways
                    - org_hierarchy: Page ID/title for org hierarchy
                - output_dir: Directory for output JSON files (default: input/)
                - space_key: Confluence space key (required if using page titles)
        """
        self.base_url = config.get('base_url', '').rstrip('/')
        self.username = config.get('username') or os.environ.get('CONFLUENCE_USER')
        self.api_token = config.get('api_token') or os.environ.get('CONFLUENCE_TOKEN')
        self.space_key = config.get('space_key')
        self.pages = config.get('pages', {})
        self.output_dir = Path(config.get('output_dir', 'input'))
        self.verify_ssl = config.get('verify_ssl', True)

        # Validate configuration
        if not self.base_url:
            raise ValueError("Confluence base_url is required")
        if not self.username or not self.api_token:
            raise ValueError("Confluence credentials required (username/api_token or env vars)")

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Confluence REST API."""
        if requests is None:
            raise ImportError("requests library required. Install with: pip install requests")

        url = f"{self.base_url}/rest/api{endpoint}"

        response = requests.get(
            url,
            params=params,
            auth=(self.username, self.api_token),
            headers={'Accept': 'application/json'},
            verify=self.verify_ssl
        )

        response.raise_for_status()
        return response.json()

    def _get_page_content(self, page_identifier: str) -> str:
        """
        Get HTML content of a Confluence page.

        Args:
            page_identifier: Page ID (numeric) or page title

        Returns:
            HTML content of the page body
        """
        # Check if identifier is a page ID (numeric)
        if page_identifier.isdigit():
            endpoint = f"/content/{page_identifier}"
            params = {'expand': 'body.storage'}
        else:
            # Search by title
            if not self.space_key:
                raise ValueError("space_key required when using page titles")
            endpoint = "/content"
            params = {
                'type': 'page',
                'spaceKey': self.space_key,
                'title': page_identifier,
                'expand': 'body.storage'
            }

        data = self._make_request(endpoint, params)

        # Handle search results vs direct page fetch
        if 'results' in data:
            if not data['results']:
                raise ValueError(f"Page not found: {page_identifier}")
            page_data = data['results'][0]
        else:
            page_data = data

        return page_data.get('body', {}).get('storage', {}).get('value', '')

    def _parse_table_from_html(self, html_content: str) -> List[Dict[str, str]]:
        """Parse first table from HTML content into list of dictionaries."""
        parser = HTMLTableParser()
        parser.feed(html_content)
        tables = parser.get_tables_as_dicts()

        if not tables:
            return []

        # Return first table found
        return tables[0]

    def _normalize_columns(self, data: List[Dict], table_type: str) -> List[Dict]:
        """Normalize column names to match expected schema."""
        schema = self.TABLE_SCHEMAS.get(table_type, {})
        aliases = schema.get('column_aliases', {})

        normalized = []
        for row in data:
            new_row = {}
            for key, value in row.items():
                # Check if this column has an alias
                normalized_key = aliases.get(key, key)
                new_row[normalized_key] = value
            normalized.append(new_row)

        return normalized

    def _validate_data(self, data: List[Dict], table_type: str) -> bool:
        """Validate that data has required columns."""
        schema = self.TABLE_SCHEMAS.get(table_type, {})
        required = schema.get('required_columns', [])

        if not data:
            print(f"  ⚠ No data found for {table_type}")
            return False

        # Check first row for required columns
        columns = set(data[0].keys())
        missing = set(required) - columns

        if missing:
            print(f"  ⚠ Missing required columns for {table_type}: {missing}")
            print(f"    Available columns: {columns}")
            return False

        return True

    def sync_table(self, table_type: str) -> Optional[List[Dict]]:
        """
        Sync a specific table from Confluence.

        Args:
            table_type: One of 'app_to_qmgr', 'gateways', 'org_hierarchy'

        Returns:
            List of dictionaries representing the table data, or None on failure
        """
        page_identifier = self.pages.get(table_type)
        if not page_identifier:
            print(f"  ⚠ No page configured for {table_type}")
            return None

        print(f"  Fetching {table_type} from page: {page_identifier}")

        try:
            html_content = self._get_page_content(str(page_identifier))
            data = self._parse_table_from_html(html_content)
            data = self._normalize_columns(data, table_type)

            if not self._validate_data(data, table_type):
                return None

            # Save to JSON file
            output_file = self.output_dir / f"{table_type}.json"
            self.output_dir.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"  ✓ Saved {len(data)} records to {output_file}")
            return data

        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTP error fetching {table_type}: {e}")
            return None
        except Exception as e:
            print(f"  ✗ Error syncing {table_type}: {e}")
            return None

    def sync_all(self) -> Dict[str, bool]:
        """
        Sync all configured tables from Confluence.

        Returns:
            Dictionary mapping table type to success status
        """
        print("\n" + "="*60)
        print("  CONFLUENCE DATA SYNC")
        print("="*60)
        print(f"  Source: {self.base_url}")
        print(f"  Output: {self.output_dir}")
        print("="*60 + "\n")

        results = {}

        for table_type in ['app_to_qmgr', 'gateways', 'org_hierarchy']:
            print(f"\n[{table_type}]")
            data = self.sync_table(table_type)
            results[table_type] = data is not None

        print("\n" + "="*60)
        print("  SYNC COMPLETE")
        print("="*60)

        success_count = sum(results.values())
        total = len(results)
        print(f"  Result: {success_count}/{total} tables synced successfully")

        for table_type, success in results.items():
            status = "✓" if success else "✗"
            print(f"    {status} {table_type}")

        print("="*60 + "\n")

        return results


def create_sample_config(output_path: Path = None) -> Dict:
    """
    Create a sample configuration file.

    Args:
        output_path: Optional path to save the config file

    Returns:
        Sample configuration dictionary
    """
    sample_config = {
        "_comment": "Confluence sync configuration",
        "base_url": "https://confluence.yourcompany.com",
        "space_key": "MQCMDB",
        "username": "your.username@company.com",
        "api_token": "your-api-token-here",
        "verify_ssl": True,
        "output_dir": "input",
        "pages": {
            "app_to_qmgr": "12345678",
            "gateways": "12345679",
            "org_hierarchy": "12345680"
        },
        "_instructions": {
            "base_url": "Your Confluence base URL (no trailing slash)",
            "space_key": "Confluence space key (required if using page titles instead of IDs)",
            "username": "Your Confluence username/email (or set CONFLUENCE_USER env var)",
            "api_token": "Your Confluence API token (or set CONFLUENCE_TOKEN env var)",
            "pages": "Map each table type to either a page ID (numeric) or page title",
            "verify_ssl": "Set to false to disable SSL verification (not recommended)"
        },
        "_table_formats": {
            "app_to_qmgr": {
                "description": "Maps Queue Managers to Applications",
                "required_columns": ["QmgrName (or 'Queue Manager')", "Application (or 'App')"],
                "example_row": {"QmgrName": "QM_PROD_01", "Application": "Trading System"}
            },
            "gateways": {
                "description": "Defines which Queue Managers are gateways",
                "required_columns": ["QmgrName (or 'Gateway')", "Scope (Internal/External)"],
                "optional_columns": ["Description"],
                "example_row": {"QmgrName": "QM_GATEWAY_01", "Scope": "External", "Description": "External partner gateway"}
            },
            "org_hierarchy": {
                "description": "Organizational hierarchy mapping",
                "required_columns": ["Biz_Ownr (or 'Business Owner')", "Organization", "Department"],
                "optional_columns": ["Org_Type (Internal/External)"],
                "example_row": {"Biz_Ownr": "Trading Desk", "Organization": "Finance", "Department": "Capital Markets", "Org_Type": "Internal"}
            }
        }
    }

    if output_path:
        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2)
        print(f"✓ Sample config saved to: {output_path}")

    return sample_config


def interactive_setup() -> Dict:
    """Run interactive setup to create configuration."""
    print("\n" + "="*60)
    print("  CONFLUENCE SYNC - INTERACTIVE SETUP")
    print("="*60 + "\n")

    config = {}

    # Get Confluence URL
    config['base_url'] = input("Confluence base URL (e.g., https://confluence.company.com): ").strip()

    # Get space key
    config['space_key'] = input("Confluence space key (e.g., MQCMDB): ").strip()

    # Get credentials
    print("\nCredentials (leave blank to use environment variables):")
    config['username'] = input("  Username/email: ").strip() or None
    config['api_token'] = getpass.getpass("  API token: ").strip() or None

    # Get page identifiers
    print("\nPage identifiers (enter page ID or title):")
    config['pages'] = {}

    page_id = input("  App-to-QMgr mapping page: ").strip()
    if page_id:
        config['pages']['app_to_qmgr'] = page_id

    page_id = input("  Gateways page: ").strip()
    if page_id:
        config['pages']['gateways'] = page_id

    page_id = input("  Org hierarchy page: ").strip()
    if page_id:
        config['pages']['org_hierarchy'] = page_id

    # Output directory
    config['output_dir'] = input("\nOutput directory (default: input): ").strip() or "input"

    # Save config?
    save_path = input("\nSave config to file? (enter path or leave blank): ").strip()
    if save_path:
        with open(save_path, 'w', encoding='utf-8') as f:
            # Don't save credentials to file
            save_config = {k: v for k, v in config.items() if k not in ['api_token']}
            save_config['_note'] = "API token should be set via CONFLUENCE_TOKEN environment variable"
            json.dump(save_config, f, indent=2)
        print(f"✓ Config saved to: {save_path}")

    print("\n" + "="*60 + "\n")

    return config


def main():
    """Command-line interface for Confluence sync."""
    parser = argparse.ArgumentParser(
        description='Sync table data from Confluence to local JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with config file
  python -m utils.confluence_sync --config confluence_config.json

  # Interactive setup
  python -m utils.confluence_sync --setup

  # Generate sample config
  python -m utils.confluence_sync --sample-config my_config.json

  # Sync specific table only
  python -m utils.confluence_sync --config conf.json --table gateways

Environment Variables:
  CONFLUENCE_USER   - Confluence username/email
  CONFLUENCE_TOKEN  - Confluence API token
        """
    )

    parser.add_argument('--config', '-c', type=str, help='Path to configuration file')
    parser.add_argument('--setup', action='store_true', help='Run interactive setup')
    parser.add_argument('--sample-config', type=str, metavar='PATH', help='Generate sample config file')
    parser.add_argument('--table', '-t', type=str,
                       choices=['app_to_qmgr', 'gateways', 'org_hierarchy'],
                       help='Sync only specified table')

    args = parser.parse_args()

    # Generate sample config
    if args.sample_config:
        create_sample_config(Path(args.sample_config))
        return

    # Interactive setup
    if args.setup:
        config = interactive_setup()
        try:
            sync = ConfluenceSync(config)
            sync.sync_all()
        except Exception as e:
            print(f"✗ Error: {e}")
        return

    # Load config from file
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"✗ Config file not found: {config_path}")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        parser.print_help()
        return

    try:
        sync = ConfluenceSync(config)

        if args.table:
            sync.sync_table(args.table)
        else:
            sync.sync_all()

    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == '__main__':
    main()
