#!/bin/bash
#===============================================================================
# MQ CMDB Automation System - Pipeline Runner Script
#
# This script runs the complete MQ CMDB pipeline including:
#   1. Database export (db_export.py)
#   2. Processing pipeline (orchestrator.py)
#
# Usage: ./run_pipeline.sh [OPTIONS]
#
# Options:
#   --skip-export      Skip database export, use existing data
#   --diagrams-only    Only regenerate diagrams (skip data processing)
#   --dry-run          Show what would be executed without running
#   --verbose          Enable verbose output
#   --help             Show this help message
#
# Environment Variables:
#   DB_MASTER_PASSWORD   Master password for encrypted credentials (required)
#   MQCMDB_HOME          Installation directory (default: script directory)
#   MQCMDB_PROFILE       Database profile name (default: production)
#
#===============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MQCMDB_HOME="${MQCMDB_HOME:-$(dirname "$SCRIPT_DIR")}"
MQCMDB_PROFILE="${MQCMDB_PROFILE:-production}"

# Flags
SKIP_EXPORT=false
DIAGRAMS_ONLY=false
DRY_RUN=false
VERBOSE=false

# Runtime variables
LOG_DIR="$MQCMDB_HOME/logs"
LOG_FILE=""
START_TIME=""
EXIT_CODE=0

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'

     ╔════════════════════════════════════════════════════════════════════╗
     ║                                                                    ║
     ║       ███╗   ███╗ ██████╗      ██████╗███╗   ███╗██████╗ ██████╗   ║
     ║       ████╗ ████║██╔═══██╗    ██╔════╝████╗ ████║██╔══██╗██╔══██╗  ║
     ║       ██╔████╔██║██║   ██║    ██║     ██╔████╔██║██████╔╝██████╔╝  ║
     ║       ██║╚██╔╝██║██║   ██║    ██║     ██║╚██╔╝██║██╔══██╗██╔══██╗  ║
     ║       ██║ ╚═╝ ██║╚██████╔╝    ╚██████╗██║ ╚═╝ ██║██████╔╝██║  ██║  ║
     ║       ╚═╝     ╚═╝ ╚═════╝      ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝  ║
     ║        MQ CMDB HIERARCHICAL AUTOMATION SYSTEM                      ║
     ║        Pipeline Runner v1.0                                        ║
     ║                                                                    ║
     ╚════════════════════════════════════════════════════════════════════╝

EOF
    echo -e "${NC}"
}

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case "$level" in
        INFO)  color="${GREEN}" ;;
        WARN)  color="${YELLOW}" ;;
        ERROR) color="${RED}" ;;
        STEP)  color="${BLUE}" ;;
        *)     color="${NC}" ;;
    esac

    # Console output
    echo -e "${color}[$level]${NC} $message"

    # File output (without colors)
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    fi
}

log_info()  { log "INFO" "$@"; }
log_warn()  { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_step()  { echo ""; log "STEP" "$@"; echo "------------------------------------------------------------------------"; }

show_help() {
    cat << EOF
MQ CMDB Pipeline Runner

Usage: $(basename "$0") [OPTIONS]

Options:
  --skip-export      Skip database export, use existing data
  --diagrams-only    Only regenerate diagrams (skip data processing)
  --dry-run          Show what would be executed without running
  --verbose          Enable verbose output
  --help             Show this help message

Environment Variables:
  DB_MASTER_PASSWORD   Master password for encrypted credentials (required)
  MQCMDB_HOME          Installation directory (default: $MQCMDB_HOME)
  MQCMDB_PROFILE       Database profile name (default: production)

Examples:
  # Full pipeline run
  export DB_MASTER_PASSWORD='your_password'
  ./run_pipeline.sh

  # Skip export, use existing data
  ./run_pipeline.sh --skip-export

  # Regenerate diagrams only
  ./run_pipeline.sh --diagrams-only

EOF
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-export)
                SKIP_EXPORT=true
                shift
                ;;
            --diagrams-only)
                DIAGRAMS_ONLY=true
                SKIP_EXPORT=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &>/dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_info "Python: $(python3 --version)"

    # Check GraphViz (optional but recommended)
    if command -v dot &>/dev/null; then
        log_info "GraphViz: $(dot -V 2>&1)"
    else
        log_warn "GraphViz not found - PDF generation will be skipped"
    fi

    # Check MQCMDB_HOME
    if [ ! -d "$MQCMDB_HOME" ]; then
        log_error "MQCMDB_HOME directory does not exist: $MQCMDB_HOME"
        exit 1
    fi
    log_info "MQCMDB_HOME: $MQCMDB_HOME"

    # Check required files
    if [ ! -f "$MQCMDB_HOME/orchestrator.py" ]; then
        log_error "orchestrator.py not found in $MQCMDB_HOME"
        exit 1
    fi

    if [ ! -f "$MQCMDB_HOME/db_export.py" ]; then
        log_error "db_export.py not found in $MQCMDB_HOME"
        exit 1
    fi

    # Check DB_MASTER_PASSWORD (required for database export)
    if [ "$SKIP_EXPORT" = false ] && [ -z "${DB_MASTER_PASSWORD:-}" ]; then
        log_error "DB_MASTER_PASSWORD environment variable is not set"
        log_error "Set it with: export DB_MASTER_PASSWORD='your_password'"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

setup_environment() {
    log_step "Setting up environment..."

    # Create directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$MQCMDB_HOME/output"

    # Set up log file
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    LOG_FILE="$LOG_DIR/pipeline_${timestamp}.log"

    # Load environment file if exists
    if [ -f "$MQCMDB_HOME/.env" ]; then
        log_info "Loading environment from $MQCMDB_HOME/.env"
        set -a
        source "$MQCMDB_HOME/.env"
        set +a
    fi

    # Set Python encoding
    export PYTHONIOENCODING=utf-8
    export PYTHONUNBUFFERED=1

    # Change to working directory
    cd "$MQCMDB_HOME"

    log_info "Working directory: $(pwd)"
    log_info "Log file: $LOG_FILE"

    START_TIME=$(date +%s)
}

cleanup_old_logs() {
    log_step "Cleaning up old logs..."

    # Remove logs older than 7 days
    local deleted_count=0
    if [ -d "$LOG_DIR" ]; then
        while IFS= read -r -d '' file; do
            if [ "$DRY_RUN" = true ]; then
                log_info "[DRY-RUN] Would delete: $file"
            else
                rm -f "$file"
            fi
            ((deleted_count++)) || true
        done < <(find "$LOG_DIR" -name "*.log" -type f -mtime +7 -print0 2>/dev/null)
    fi

    if [ $deleted_count -gt 0 ]; then
        log_info "Cleaned up $deleted_count old log file(s)"
    else
        log_info "No old logs to clean up"
    fi
}

run_database_export() {
    if [ "$SKIP_EXPORT" = true ]; then
        log_info "Skipping database export (--skip-export specified)"
        return 0
    fi

    log_step "Running database export..."

    local cmd="python3 db_export.py --profile $MQCMDB_PROFILE --batch"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would execute: $cmd"
        return 0
    fi

    if [ "$VERBOSE" = true ]; then
        $cmd 2>&1 | tee -a "$LOG_FILE"
    else
        $cmd >> "$LOG_FILE" 2>&1
    fi

    local exit_code=${PIPESTATUS[0]:-$?}
    if [ $exit_code -ne 0 ]; then
        log_error "Database export failed with exit code: $exit_code"
        return $exit_code
    fi

    log_info "Database export completed successfully"
    return 0
}

run_orchestrator() {
    log_step "Running processing pipeline..."

    local cmd="python3 orchestrator.py"
    if [ "$DIAGRAMS_ONLY" = true ]; then
        cmd="$cmd --mode diagrams-only"
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would execute: $cmd"
        return 0
    fi

    if [ "$VERBOSE" = true ]; then
        $cmd 2>&1 | tee -a "$LOG_FILE"
    else
        $cmd >> "$LOG_FILE" 2>&1
    fi

    local exit_code=${PIPESTATUS[0]:-$?}
    if [ $exit_code -ne 0 ]; then
        log_error "Pipeline processing failed with exit code: $exit_code"
        return $exit_code
    fi

    log_info "Pipeline processing completed successfully"
    return 0
}

print_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    echo ""
    echo "========================================================================"
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}Pipeline completed successfully${NC}"
    else
        echo -e "${RED}Pipeline completed with errors (exit code: $EXIT_CODE)${NC}"
    fi
    echo "========================================================================"
    echo ""
    echo "Duration: ${minutes}m ${seconds}s"
    echo "Log file: $LOG_FILE"
    echo ""

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Output files:"
        echo "  - Data:     $MQCMDB_HOME/output/data/"
        echo "  - Diagrams: $MQCMDB_HOME/output/diagrams/"
        echo "  - Reports:  $MQCMDB_HOME/output/reports/"
        echo "  - Exports:  $MQCMDB_HOME/output/exports/"
        echo ""

        # Show recent reports
        if [ -d "$MQCMDB_HOME/output/reports" ]; then
            echo "Recent reports:"
            ls -lt "$MQCMDB_HOME/output/reports"/*.html 2>/dev/null | head -3 | awk '{print "  - " $NF}'
        fi
    else
        echo "Check the log file for details:"
        echo "  tail -100 $LOG_FILE"
    fi
    echo ""
}

send_notification() {
    # Placeholder for email/Slack/Teams notification
    # Uncomment and configure as needed

    # Example: Send email notification
    # if [ $EXIT_CODE -ne 0 ]; then
    #     echo "Pipeline failed. Check $LOG_FILE" | mail -s "MQ CMDB Pipeline Failed" ops-team@company.com
    # fi

    :  # No-op
}

cleanup() {
    # Cleanup function called on exit
    local exit_code=$?

    if [ $exit_code -ne 0 ] && [ "$DRY_RUN" = false ]; then
        log_error "Pipeline terminated with exit code: $exit_code"
    fi

    EXIT_CODE=$exit_code
    print_summary
    send_notification
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

main() {
    # Set up trap for cleanup
    trap cleanup EXIT

    # Parse command line arguments
    parse_args "$@"

    # Print banner
    print_banner

    # Run pipeline steps
    check_prerequisites
    setup_environment
    cleanup_old_logs
    run_database_export
    run_orchestrator

    log_info "Pipeline execution completed"
}

# Run main function
main "$@"
