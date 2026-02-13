#!/bin/bash
#===============================================================================
# MQ CMDB Automation System - Cron Setup Script
#
# This script sets up cron jobs for scheduled pipeline execution.
# Use this as an alternative to systemd timers.
#
# Usage: ./setup_cron.sh [OPTIONS]
#
# Options:
#   --schedule CRON      Cron schedule expression (default: "0 6 * * *" = 6 AM daily)
#   --user USER          User to run the cron job as (default: current user)
#   --install-dir DIR    Installation directory (default: /opt/mqcmdb)
#   --remove             Remove existing MQ CMDB cron jobs
#   --list               List current MQ CMDB cron jobs
#   --help               Show this help message
#
# Schedule Examples:
#   "0 6 * * *"          Daily at 6:00 AM
#   "0 6 * * 1-5"        Weekdays at 6:00 AM
#   "0 */4 * * *"        Every 4 hours
#   "0 6,18 * * *"       Twice daily at 6 AM and 6 PM
#   "0 6 * * 0"          Weekly on Sunday at 6 AM
#
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
CRON_SCHEDULE="0 6 * * *"
CRON_USER="${USER:-$(whoami)}"
INSTALL_DIR="/opt/mqcmdb"
ACTION="install"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
MQ CMDB Cron Setup Script

Usage: $(basename "$0") [OPTIONS]

Options:
  --schedule CRON      Cron schedule expression (default: "0 6 * * *" = 6 AM daily)
  --user USER          User to run the cron job as (default: $CRON_USER)
  --install-dir DIR    Installation directory (default: /opt/mqcmdb)
  --remove             Remove existing MQ CMDB cron jobs
  --list               List current MQ CMDB cron jobs
  --help               Show this help message

Schedule Examples:
  "0 6 * * *"          Daily at 6:00 AM
  "0 6 * * 1-5"        Weekdays at 6:00 AM
  "0 */4 * * *"        Every 4 hours
  "0 6,18 * * *"       Twice daily at 6 AM and 6 PM
  "0 6 * * 0"          Weekly on Sunday at 6 AM

Cron Format: minute hour day-of-month month day-of-week
  minute:       0-59
  hour:         0-23
  day-of-month: 1-31
  month:        1-12
  day-of-week:  0-7 (0 and 7 are Sunday)

Examples:
  # Install default schedule (daily at 6 AM)
  ./setup_cron.sh

  # Install custom schedule (weekdays at 7:30 AM)
  ./setup_cron.sh --schedule "30 7 * * 1-5"

  # List existing cron jobs
  ./setup_cron.sh --list

  # Remove cron jobs
  ./setup_cron.sh --remove

EOF
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --schedule)
                CRON_SCHEDULE="$2"
                shift 2
                ;;
            --user)
                CRON_USER="$2"
                shift 2
                ;;
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --remove)
                ACTION="remove"
                shift
                ;;
            --list)
                ACTION="list"
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

validate_cron_schedule() {
    # Basic validation of cron schedule format
    local schedule="$1"
    local field_count=$(echo "$schedule" | wc -w)

    if [ "$field_count" -ne 5 ]; then
        log_error "Invalid cron schedule: '$schedule'"
        log_error "Expected 5 fields: minute hour day-of-month month day-of-week"
        exit 1
    fi

    log_info "Cron schedule: $schedule"
}

get_cron_marker() {
    echo "# MQ CMDB Automation Pipeline"
}

list_cron_jobs() {
    log_info "Current MQ CMDB cron jobs for user '$CRON_USER':"
    echo ""

    local marker=$(get_cron_marker)
    local jobs=$(crontab -u "$CRON_USER" -l 2>/dev/null | grep -A1 "$marker" || true)

    if [ -z "$jobs" ]; then
        echo "  No MQ CMDB cron jobs found"
    else
        echo "$jobs" | sed 's/^/  /'
    fi
    echo ""
}

remove_cron_jobs() {
    log_info "Removing MQ CMDB cron jobs for user '$CRON_USER'..."

    local marker=$(get_cron_marker)
    local current_crontab=$(crontab -u "$CRON_USER" -l 2>/dev/null || true)

    if [ -z "$current_crontab" ]; then
        log_info "No crontab exists for user '$CRON_USER'"
        return 0
    fi

    # Remove marker line and the following job line
    local new_crontab=$(echo "$current_crontab" | grep -v "$marker" | grep -v "run_pipeline.sh")

    if [ "$new_crontab" = "$current_crontab" ]; then
        log_info "No MQ CMDB cron jobs found to remove"
        return 0
    fi

    echo "$new_crontab" | crontab -u "$CRON_USER" -

    log_info "MQ CMDB cron jobs removed successfully"
}

install_cron_job() {
    log_info "Installing MQ CMDB cron job..."

    # Validate schedule
    validate_cron_schedule "$CRON_SCHEDULE"

    # Check if install directory exists
    if [ ! -d "$INSTALL_DIR" ]; then
        log_warn "Installation directory does not exist: $INSTALL_DIR"
        log_warn "Using project directory: $PROJECT_DIR"
        INSTALL_DIR="$PROJECT_DIR"
    fi

    # Check if run_pipeline.sh exists
    local pipeline_script="$INSTALL_DIR/deploy/run_pipeline.sh"
    if [ ! -f "$pipeline_script" ]; then
        log_error "Pipeline script not found: $pipeline_script"
        exit 1
    fi

    # Make sure script is executable
    chmod +x "$pipeline_script"

    # Remove existing jobs first
    remove_cron_jobs

    # Get current crontab
    local current_crontab=$(crontab -u "$CRON_USER" -l 2>/dev/null || true)

    # Create new cron entry
    local marker=$(get_cron_marker)
    local cron_entry="$CRON_SCHEDULE $pipeline_script >> $INSTALL_DIR/logs/cron_\$(date +\\%Y\\%m\\%d).log 2>&1"

    # Add new job
    local new_crontab="$current_crontab
$marker
$cron_entry"

    echo "$new_crontab" | crontab -u "$CRON_USER" -

    log_info "Cron job installed successfully"
    echo ""
    echo "Schedule: $CRON_SCHEDULE"
    echo "Command:  $pipeline_script"
    echo "Log:      $INSTALL_DIR/logs/cron_YYYYMMDD.log"
    echo ""
    echo "The pipeline will run according to the schedule."
    echo ""
    echo -e "${YELLOW}IMPORTANT:${NC} Make sure the following environment variable is set:"
    echo "  DB_MASTER_PASSWORD"
    echo ""
    echo "Add to $CRON_USER's environment or use a wrapper script."
    echo ""

    # Create wrapper script with environment
    create_cron_wrapper
}

create_cron_wrapper() {
    local wrapper_script="$INSTALL_DIR/deploy/cron_wrapper.sh"

    cat > "$wrapper_script" << EOF
#!/bin/bash
#===============================================================================
# MQ CMDB Cron Wrapper Script
#
# This script sets up the environment and runs the pipeline.
# Edit this file to set your DB_MASTER_PASSWORD securely.
#
# Usage: Called by cron, not meant to be run manually
#===============================================================================

# Set the master password (KEEP THIS FILE SECURE!)
# Option 1: Set directly (less secure)
# export DB_MASTER_PASSWORD="your_secure_password"

# Option 2: Read from a secure file (more secure)
# if [ -f "$INSTALL_DIR/.db_password" ]; then
#     export DB_MASTER_PASSWORD=\$(cat "$INSTALL_DIR/.db_password")
# fi

# Option 3: Use environment file
if [ -f "$INSTALL_DIR/.env" ]; then
    set -a
    source "$INSTALL_DIR/.env"
    set +a
fi

# Check if password is set
if [ -z "\${DB_MASTER_PASSWORD:-}" ]; then
    echo "ERROR: DB_MASTER_PASSWORD is not set"
    echo "Edit $wrapper_script to configure the password"
    exit 1
fi

# Run the pipeline
exec "$INSTALL_DIR/deploy/run_pipeline.sh" "\$@"
EOF

    chmod 700 "$wrapper_script"
    log_info "Created cron wrapper script: $wrapper_script"
    log_warn "Edit $wrapper_script to configure DB_MASTER_PASSWORD"
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

main() {
    parse_args "$@"

    echo ""
    echo -e "${BLUE}MQ CMDB Cron Setup${NC}"
    echo "========================================"
    echo ""

    case "$ACTION" in
        list)
            list_cron_jobs
            ;;
        remove)
            remove_cron_jobs
            ;;
        install)
            install_cron_job
            ;;
    esac
}

main "$@"
