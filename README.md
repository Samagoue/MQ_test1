# ==============================================================================

# README.md - Documentation

# ==============================================================================

"""

# MQ CMDB Automation System

A modular Python system for processing IBM MQ CMDB data, generating topology diagrams, and automating database exports.

## Project Structure

```
MQCMDB_Scripts/
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuration
├── core/
│   ├── __init__.py
│   ├── database.py              # Database operations
│   ├── credentials.py           # Encrypted credentials
│   └── data_processing.py       # Data transformations
├── processors/
│   ├── __init__.py
│   ├── mqmanager_processor.py   # MQ relationship processing
│   └── deduplication.py         # Deduplication logic
├── generators/
│   ├── __init__.py
│   ├── graphviz_topology.py     # Full topology diagrams
│   └── graphviz_individual.py   # Individual MQ diagrams
├── utils/
│   ├── __init__.py
│   ├── common.py                # Common utilities
│   ├── file_io.py               # File I/O operations
│   └── logger.py                # Logging utilities
├── main.py                      # Database export entry point
├── orchestrator.py              # Main pipeline coordinator
├── Database/                    # SQL query files (*.sql)
├── output/                      # Generated files
├── logs/                        # Log files
├── run_batch_export.bat         # Windows automation script
└── cleanup_logs.bat             # Log cleanup script
```

## Setup

### 1. Install Dependencies

```bash
pip install mysql-connector-python cryptography
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

### Windows Automation

```batch
REM Edit run_batch_export.bat and set your password
SET DB_MASTER_PASSWORD=your_password

REM Run the automation
run_batch_export.bat
```

## Features

- ✅ **Modular Architecture** - Clean separation of concerns
- ✅ **Encrypted Credentials** - Secure password storage
- ✅ **Batch Processing** - Process multiple SQL queries
- ✅ **Automatic Deduplication** - Remove duplicate records
- ✅ **Topology Diagrams** - Full MQ topology visualization
- ✅ **Individual Diagrams** - Per-MQmanager focused views
- ✅ **PDF Generation** - Automatic PDF creation
- ✅ **Logging** - Comprehensive logging with auto-cleanup
- ✅ **UTF-8 Support** - Proper encoding handling

## Configuration

Edit `config/settings.py` to customize:

- File paths
- Color schemes
- Field mappings
- GraphViz settings
- Deduplication rules

## Output Files

- `output/all_MQCMDB_assets.json` - Raw export from database
- `output/mq_cmdb_processed.json` - Processed relationships
- `output/mq_topology.dot` - GraphViz topology diagram
- `output/mq_topology.pdf` - PDF topology diagram
- `output/individual_diagrams/*.pdf` - Individual MQ diagrams

## Maintenance

```bash
# Cleanup old logs (Windows)
cleanup_logs.bat

# Cleanup old logs (Python)
python -c "from pathlib import Path; import time; [f.unlink() for f in Path('logs').glob('*.log') if time.time() - f.stat().st_mtime > 7*86400]"
```

## License

Internal use only.
"""

# ==============================================================================

# COMPLETE FILE STRUCTURE SUMMARY

# ==============================================================================

"""
ALL FILES CREATED:

1. config/settings.py - Configuration management
2. utils/common.py - Common utilities
3. utils/file_io.py - File I/O operations
4. core/database.py - Database connections
5. core/credentials.py - Encrypted credentials
6. processors/deduplication.py - Deduplication logic
7. processors/mqmanager_processor.py - MQ relationship processing
8. generators/graphviz_topology.py - Full topology diagrams
9. generators/graphviz_individual.py - Individual diagrams
10. main.py - Database export CLI
11. orchestrator.py - Main pipeline coordinator
12. run_batch_export.bat - Windows automation
13. cleanup_logs.bat - Log cleanup
14. README.md - Documentation

USAGE:

1. Setup: python main.py --setup
2. Export: python main.py --batch --format json
3. Process: python orchestrator.py --mode full
4. Automate: run_batch_export.bat (Windows)
   """
