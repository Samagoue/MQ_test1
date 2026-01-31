# CLAUDE.md

This file provides context for Claude Code when working with this repository.

## Project Overview

MQ CMDB Automation System - A Python application that processes IBM MQ CMDB data, generates topology diagrams, and creates enterprise architecture documentation.

## Architecture

```
orchestrator.py          # Main 13-step pipeline coordinator
├── processors/          # Data processing modules
│   ├── hierarchy_mashup.py    # Enriches data with org hierarchy
│   ├── mqmanager_processor.py # Extracts MQ relationships
│   └── change_detector.py     # Detects changes between snapshots
├── generators/          # Output generators
│   ├── graphviz_hierarchical.py    # Main topology diagram
│   ├── graphviz_individual.py      # Per-MQ manager diagrams
│   ├── application_diagram_generator.py  # App-focused diagrams
│   └── doc_generator.py            # TOGAF EA documentation
├── analytics/           # Analysis modules
│   └── gateway_analyzer.py    # Gateway usage analytics
├── utils/               # Utilities
│   ├── export_formats.py      # SVG/PNG/Excel export
│   ├── confluence_sync.py     # Sync from Confluence tables
│   └── file_io.py             # JSON file operations
└── config/
    └── settings.py      # Colors, paths, field mappings
```

## Key Data Flow

1. **Input**: `output/all_MQCMDB_assets.json` (raw MQ data from database)
2. **Config files** (in `input/`):
   - `gateways.json` - Gateway definitions (Internal/External)
   - `app_to_qmgr.json` - Application to Queue Manager mapping
   - `org_hierarchy.json` - Organizational hierarchy
3. **Output**: Organized in subdirectories (see below)

## Output Directory Structure

```
output/
├── all_MQCMDB_assets.json     # Raw database export
├── data/                      # JSON data files
│   ├── mq_cmdb_processed.json
│   ├── mq_cmdb_baseline.json
│   └── *.json (timestamped)
├── diagrams/                  # All visual outputs
│   ├── topology/              # Main topology (dot/pdf/svg/png)
│   ├── applications/          # Per-app diagrams
│   ├── individual/            # Per-MQ-manager diagrams
│   └── filtered/              # Filtered view diagrams
├── reports/                   # HTML reports
│   ├── change_report_*.html
│   └── gateway_analytics_*.html
└── exports/                   # Excel & documentation
    ├── mqcmdb_inventory_*.xlsx
    └── EA_Documentation_*.txt
```

## Coding Conventions

- **Python 3.8+** compatible
- **Type hints** used throughout
- **Pathlib** for all file paths
- **docstrings** for all public functions
- Print statements use emoji prefixes: `✓` success, `✗` error, `⚠` warning

## Common Commands

```bash
# Run full pipeline
python orchestrator.py --mode full

# Sync from Confluence
python -m utils.confluence_sync --config input/confluence_config.json

# Generate diagrams only
python orchestrator.py --mode diagrams-only
```

## Important Patterns

### GraphViz Generation
- DOT files generated first, then converted to SVG/PDF
- SVG files post-processed to remove link underlines (see `_remove_svg_link_underlines`)
- Nodes have clickable URLs linking to individual diagrams

### Color Schemes
- Internal orgs: Blue/Green palette (defined in `INTERNAL_ORG_COLORS`)
- External orgs: Purple/Lavender palette (`EXTERNAL_ORG_COLORS`)
- Gateways: Orange (Internal) / Teal (External)

### Hierarchy Structure
```
Organization
└── Department
    └── Business Owner (Biz_Ownr/Directorate)
        └── Application
            └── MQ Manager
```

## Testing

No formal test suite. Validate by running the pipeline and checking output files.

## Dependencies

See `requirements.txt`. Also requires GraphViz installed via system package manager.
