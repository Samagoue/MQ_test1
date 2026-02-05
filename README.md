# MQ CMDB Automation System

A modular Python system for processing IBM MQ CMDB data, generating topology diagrams, and automating database exports.

## Project Structure

```
MQCMDB_Scripts/
├── config/
│   └── settings.py              # Configuration & color schemes
├── core/
│   ├── database.py              # Database operations
│   ├── credentials.py           # Encrypted credentials
│   └── data_processing.py       # Data transformations
├── processors/
│   ├── mqmanager_processor.py   # MQ relationship processing
│   ├── hierarchy_mashup.py      # Org hierarchy enrichment
│   ├── deduplication.py         # Deduplication logic
│   └── change_detector.py       # Change detection & HTML reports
├── generators/
│   ├── graphviz_hierarchical.py # Main topology diagram
│   ├── graphviz_individual.py   # Individual MQ diagrams
│   ├── application_diagram_generator.py  # App-focused diagrams
│   └── doc_generator.py         # TOGAF EA documentation
├── analytics/
│   └── gateway_analyzer.py      # Gateway analytics & reports
├── utils/
│   ├── common.py                # Common utilities
│   ├── file_io.py               # File I/O operations
│   ├── export_formats.py        # Multi-format export (SVG, PNG, Excel)
│   ├── confluence_sync.py       # Confluence table sync
│   ├── smart_filter.py          # Filtered view generation
│   ├── email_notifier.py        # Email notification module
│   └── logger.py                # Logging utilities
├── tools/
│   ├── send_email.py            # Standalone email utility (CLI)
│   └── email_config.ini.example # Email configuration template
├── input/
│   ├── gateways.json            # Gateway definitions
│   ├── app_to_qmgr.json         # Application to Queue Manager mapping
│   ├── org_hierarchy.json       # Organizational hierarchy
│   └── confluence_config_sample.json  # Confluence sync config template
├── db_export.py                 # Database export script (SQL to JSON)
├── main.py                      # Pipeline runner entry point
├── orchestrator.py              # Main pipeline coordinator (14-step process)
├── Database/                    # SQL query files (*.sql)
├── output/                      # Generated files
└── logs/                        # Log files
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Graphviz

- **Windows**: Download from https://graphviz.org/download/
- **macOS**: `brew install graphviz`
- **Linux**: `sudo apt-get install graphviz`

### 3. Setup Database Credentials

```bash
python main.py --setup --profile production
```

## Usage

### Database Export

```bash
# Export all queries in Database/ folder
python main.py --batch --format json

# Export single query
python main.py --query-file Database/my_query.sql --output output/result.json --format json

# Export single table
python main.py --table my_table --output output/table.csv --format csv
```

### Process and Generate Diagrams

```bash
# Full pipeline (requires all_MQCMDB_assets.json in output/)
python orchestrator.py --mode full

# Regenerate diagrams only
python orchestrator.py --mode diagrams-only
```

### Confluence Data Sync

Sync table data from Confluence to update local JSON configuration files.

```bash
# Interactive setup
python -m utils.confluence_sync --setup

# Sync with config file
python -m utils.confluence_sync --config input/confluence_config.json

# Sync single table
python -m utils.confluence_sync --config input/confluence_config.json --table gateways

# Generate sample config
python -m utils.confluence_sync --sample-config input/confluence_config.json
```

#### Confluence Table Formats

Create tables in Confluence with the following columns:

| Table | Required Columns | Optional Columns |
|-------|-----------------|------------------|
| **app_to_qmgr** | QmgrName, Application | - |
| **gateways** | QmgrName, Scope (Internal/External) | Description |
| **org_hierarchy** | Biz_Ownr, Organization, Department | Org_Type (Internal/External) |

The sync utility supports flexible column naming (e.g., "Queue Manager" or "QmgrName").

#### Environment Variables

```bash
export CONFLUENCE_USER="your.email@company.com"
export CONFLUENCE_TOKEN="your-api-token"
```

## Input Files

| File | Description |
|------|-------------|
| `input/gateways.json` | Defines which Queue Managers are gateways (Internal/External) |
| `input/app_to_qmgr.json` | Maps Queue Managers to their owning Applications |
| `input/org_hierarchy.json` | Organizational hierarchy (Biz_Ownr → Department → Organization) |

## Features

- **Modular Architecture** - Clean separation of concerns
- **Encrypted Credentials** - Secure password storage
- **Batch Processing** - Process multiple SQL queries
- **Automatic Deduplication** - Remove duplicate records
- **Hierarchical Topology** - Full MQ topology with org hierarchy
- **Application Diagrams** - App-focused views with related MQ managers
- **Individual Diagrams** - Per-MQ manager focused views
- **Clickable SVG Diagrams** - Click on nodes to navigate to individual diagrams
- **Change Detection** - Compare snapshots and generate HTML change reports
- **Gateway Analytics** - Analyze gateway usage patterns
- **Multi-Format Export** - SVG, PNG, PDF, and Excel reports
- **Confluence Integration** - Sync configuration from Confluence tables
- **TOGAF Documentation** - Generate EA documentation in Confluence markup
- **Filtered Views** - Organization and gateway-specific filtered diagrams

## Output Directory Structure

```
output/
├── all_MQCMDB_assets.json              # Raw export from database
│
├── data/                               # JSON data files
│   ├── mq_cmdb_processed.json          # Processed & enriched data
│   ├── mq_cmdb_baseline.json           # Baseline for change detection
│   ├── changes_*.json                  # Change detection data
│   └── gateway_analytics_*.json        # Gateway analytics data
│
├── diagrams/                           # All visual outputs
│   ├── topology/                       # Main topology diagram
│   │   ├── mq_topology.dot
│   │   ├── mq_topology.pdf
│   │   ├── mq_topology.svg
│   │   └── mq_topology.png
│   ├── applications/                   # Per-application diagrams
│   │   └── {app_name}.[dot|pdf|svg]
│   ├── individual/                     # Per-MQ-manager diagrams
│   │   └── {mqmgr}.[dot|pdf|svg]
│   └── filtered/                       # Filtered view diagrams
│       └── [org_|dept_|gateways_]*.[dot|svg]
│
├── reports/                            # HTML reports
│   ├── change_report_*.html            # Change detection report
│   └── gateway_analytics_*.html        # Gateway analytics report
│
└── exports/                            # Excel & documentation
    ├── mqcmdb_inventory_*.xlsx         # Excel inventory (4 sheets)
    └── EA_Documentation_*.txt          # TOGAF EA documentation
```

## Configuration

Edit `config/settings.py` to customize:

- File paths
- Color schemes (Internal/External organizations, Gateways)
- Field mappings
- GraphViz settings
- Deduplication rules

## Pipeline Steps

The orchestrator runs a 14-step pipeline:

1. **Output Cleanup** - Remove old files (if enabled)
2. **Load Data** - Read `all_MQCMDB_assets.json`
3. **Process Relationships** - Extract MQ manager connections
4. **Convert to JSON** - Structure relationships
5. **Enrich Hierarchy** - Mashup with org hierarchy, gateways, apps
6. **Change Detection** - Compare vs baseline, generate HTML report
7. **Hierarchical Topology** - Generate main DOT & PDF diagram
8. **Application Diagrams** - Create app-focused diagrams
9. **Individual Diagrams** - Create per-MQ-manager diagrams
10. **Filtered Views** - Generate organization/gateway filtered views
11. **Gateway Analytics** - Analyze gateway usage, generate HTML report
12. **Multi-Format Export** - Export to SVG, PNG, Excel
13. **EA Documentation** - Generate Confluence markup documentation
14. **Email Notification** - Send completion notification with log attachment

## RHEL/Linux Deployment

### Quick Start (RHEL/CentOS)

```bash
# Clone or copy the project to the server
cd /path/to/MQ_test1

# Run the installer (as root)
sudo ./deploy/install.sh

# Configure database credentials
sudo -u mqcmdb bash
cd /opt/mqcmdb
export DB_MASTER_PASSWORD='your_secure_password'
python3 db_export.py --setup --profile production

# Edit environment file
sudo vi /opt/mqcmdb/.env
# Set: DB_MASTER_PASSWORD=your_secure_password

# Test the pipeline
sudo -u mqcmdb /opt/mqcmdb/deploy/run_pipeline.sh

# Enable scheduled execution
sudo systemctl enable --now mqcmdb.timer
```

### Installation Script Options

```bash
sudo ./deploy/install.sh [OPTIONS]

Options:
  --install-dir DIR    Installation directory (default: /opt/mqcmdb)
  --user USER          Service user (default: mqcmdb)
  --skip-graphviz      Skip GraphViz installation
  --skip-python        Skip Python installation (use existing)
  --help               Show help message
```

### Running the Pipeline (Linux)

```bash
# Set required environment variable
export DB_MASTER_PASSWORD='your_secure_password'

# Full pipeline (export + process)
./deploy/run_pipeline.sh

# Skip database export (use existing data)
./deploy/run_pipeline.sh --skip-export

# Regenerate diagrams only
./deploy/run_pipeline.sh --diagrams-only

# Verbose output
./deploy/run_pipeline.sh --verbose

# Dry run (show what would be executed)
./deploy/run_pipeline.sh --dry-run
```

### Scheduling with Systemd (Recommended)

The installer creates systemd service and timer files:

```bash
# Enable scheduled execution (daily at 6 AM)
sudo systemctl enable --now mqcmdb.timer

# Check timer status
sudo systemctl status mqcmdb.timer
sudo systemctl list-timers mqcmdb.timer

# Run manually
sudo systemctl start mqcmdb.service

# View logs
journalctl -u mqcmdb.service -f

# Disable scheduled execution
sudo systemctl disable mqcmdb.timer
```

Edit the timer schedule:
```bash
sudo systemctl edit mqcmdb.timer
```

Add custom schedule (example: 7 AM weekdays):
```ini
[Timer]
OnCalendar=Mon-Fri *-*-* 07:00:00
```

### Scheduling with Cron (Alternative)

```bash
# Install cron job (default: daily at 6 AM)
./deploy/setup_cron.sh

# Custom schedule (weekdays at 7:30 AM)
./deploy/setup_cron.sh --schedule "30 7 * * 1-5"

# List current cron jobs
./deploy/setup_cron.sh --list

# Remove cron jobs
./deploy/setup_cron.sh --remove
```

### Directory Structure (After Installation)

```
/opt/mqcmdb/                        # Installation directory
├── .env                            # Environment configuration
├── credentials/                    # Encrypted database credentials
├── deploy/
│   ├── install.sh                  # Installation script
│   ├── run_pipeline.sh             # Pipeline runner
│   ├── setup_cron.sh               # Cron setup utility
│   └── cron_wrapper.sh             # Cron environment wrapper
├── input/                          # Configuration files
│   ├── gateways.json
│   ├── app_to_qmgr.json
│   └── org_hierarchy.json
├── output/                         # Generated files
│   ├── data/
│   ├── diagrams/
│   ├── reports/
│   └── exports/
└── logs/                           # Log files
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DB_MASTER_PASSWORD` | Master password for encrypted credentials | Yes |
| `MQCMDB_HOME` | Installation directory | No (default: /opt/mqcmdb) |
| `MQCMDB_PROFILE` | Database credential profile | No (default: production) |
| `CONFLUENCE_USER` | Confluence username for sync | No |
| `CONFLUENCE_TOKEN` | Confluence API token | No |

### Email Notification Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMAIL_ENABLED` | Enable email notifications | `false` |
| `EMAIL_RECIPIENTS` | Comma-separated list of recipients | - |
| `EMAIL_RECIPIENTS_SUCCESS` | Recipients for success notifications only | - |
| `EMAIL_RECIPIENTS_FAILURE` | Recipients for failure notifications only | - |
| `SMTP_SERVER` | SMTP server hostname | `localhost` |
| `SMTP_PORT` | SMTP server port | `25` |
| `SMTP_USER` | SMTP username for authentication | - |
| `SMTP_PASSWORD` | SMTP password for authentication | - |
| `SMTP_FROM` | Sender email address | `mqcmdb@localhost` |
| `SMTP_USE_TLS` | Use STARTTLS encryption | `false` |
| `SMTP_USE_SSL` | Use SSL/TLS encryption | `false` |
| `EMAIL_CONFIG_FILE` | Path to email config INI file | - |

#### Email Configuration Example

```bash
# Enable email notifications
export EMAIL_ENABLED=true
export EMAIL_RECIPIENTS='ops-team@company.com,alerts@company.com'
export SMTP_SERVER='smtp.company.com'
export SMTP_PORT=587
export SMTP_FROM='mqcmdb@company.com'
export SMTP_USE_TLS=true

# Optional: SMTP authentication
export SMTP_USER='smtp_username'
export SMTP_PASSWORD='smtp_password'
```

Alternatively, use a config file (`email_config.ini`):

```ini
[smtp]
server = smtp.company.com
port = 587
user = smtp_username
password = smtp_password
from = mqcmdb@company.com
use_tls = true

[notifications]
enabled = true
recipients = ops-team@company.com
recipients_failure = alerts@company.com
```

The pipeline automatically attaches the log file to email notifications.

### Troubleshooting

**Check service status:**
```bash
sudo systemctl status mqcmdb.service
sudo systemctl status mqcmdb.timer
```

**View recent logs:**
```bash
# Systemd logs
journalctl -u mqcmdb.service --since "1 hour ago"

# Application logs
tail -100 /opt/mqcmdb/logs/pipeline_*.log
```

**Test database connection:**
```bash
sudo -u mqcmdb bash
cd /opt/mqcmdb
export DB_MASTER_PASSWORD='your_password'
python3 -c "from core.database import DatabaseConnection; print('OK')"
```

**Verify GraphViz:**
```bash
dot -V
```

## Maintenance

```bash
# Cleanup old logs (Python)
python -c "from pathlib import Path; import time; [f.unlink() for f in Path('logs').glob('*.log') if time.time() - f.stat().st_mtime > 7*86400]"

# Cleanup old logs (Linux)
find /opt/mqcmdb/logs -name "*.log" -mtime +7 -delete

# Check disk usage
du -sh /opt/mqcmdb/output/*
```

## License

Internal use only.
