#!/bin/bash
#
# MQ CMDB Pipeline Runner
#
# This script runs the MQ CMDB automation pipeline.
# Can be run manually or scheduled via cron/systemd.
#
# Usage:
#   ./run_pipeline.sh              # Run pipeline
#   ./run_pipeline.sh --quiet      # Run with minimal output (for cron)
#   ./run_pipeline.sh --help       # Show help
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/venv"
LOG_DIR="${PROJECT_DIR}/logs"
PYTHON_BIN="${VENV_DIR}/bin/python"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
QUIET=false
for arg in "$@"; do
    case $arg in
        --quiet|-q)
            QUIET=true
            shift
            ;;
        --help|-h)
            echo "MQ CMDB Pipeline Runner"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --quiet, -q    Run with minimal output (for cron jobs)"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  CONFLUENCE_USERNAME    Confluence username/email"
            echo "  CONFLUENCE_API_TOKEN   Confluence API token"
            echo "  CONFLUENCE_PAT         Confluence Personal Access Token (alternative)"
            exit 0
            ;;
    esac
done

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    if [ "$QUIET" = false ]; then
        case $level in
            INFO)  echo -e "${GREEN}[INFO]${NC} $message" ;;
            WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
            ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        esac
    fi

    # Always log to file
    echo "[$timestamp] [$level] $message" >> "${LOG_DIR}/pipeline_$(date '+%Y%m%d').log"
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log INFO "Starting MQ CMDB Pipeline..."
log INFO "Project directory: $PROJECT_DIR"

# Check Python virtual environment
if [ ! -f "$PYTHON_BIN" ]; then
    log ERROR "Python virtual environment not found at $VENV_DIR"
    log INFO "Create it with: python3 -m venv $VENV_DIR && $VENV_DIR/bin/pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Change to project directory
cd "$PROJECT_DIR"

# Check for required input files
if [ ! -f "output/all_MQCMDB_assets.json" ]; then
    log WARN "Input file 'output/all_MQCMDB_assets.json' not found"
    log INFO "Running database export first..."

    # Try to run db_export if credentials exist
    if [ -f "db_credentials.enc" ]; then
        python db_export.py || {
            log ERROR "Database export failed"
            exit 1
        }
    else
        log ERROR "No input data and no database credentials configured"
        exit 1
    fi
fi

# Override Confluence credentials from environment if provided
if [ -n "$CONFLUENCE_USERNAME" ]; then
    export CONFLUENCE_USERNAME
fi
if [ -n "$CONFLUENCE_API_TOKEN" ]; then
    export CONFLUENCE_API_TOKEN
fi
if [ -n "$CONFLUENCE_PAT" ]; then
    export CONFLUENCE_PAT
fi

# Run the pipeline
log INFO "Running main pipeline..."
python main.py

PIPELINE_EXIT_CODE=$?

if [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    log INFO "Pipeline completed successfully"
else
    log ERROR "Pipeline failed with exit code $PIPELINE_EXIT_CODE"
    exit $PIPELINE_EXIT_CODE
fi

# Cleanup old logs (keep last 30 days)
log INFO "Cleaning up old log files..."
find "$LOG_DIR" -name "pipeline_*.log" -mtime +30 -delete 2>/dev/null || true

log INFO "Done!"
