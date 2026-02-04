#!/bin/bash
#===============================================================================
# MQ CMDB Automation System - RHEL Installation Script
#
# This script installs all dependencies and configures the MQ CMDB system
# on Red Hat Enterprise Linux (RHEL 7/8/9)
#
# Usage: sudo ./install.sh [OPTIONS]
#
# Options:
#   --install-dir DIR    Installation directory (default: /opt/mqcmdb)
#   --user USER          Service user (default: mqcmdb)
#   --skip-graphviz      Skip GraphViz installation
#   --skip-python        Skip Python installation (use existing)
#   --help               Show this help message
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
INSTALL_DIR="/opt/mqcmdb"
SERVICE_USER="mqcmdb"
SKIP_GRAPHVIZ=false
SKIP_PYTHON=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------

print_banner() {
    echo -e "${BLUE}"
    echo "    =================================================================="
    echo "       MQ CMDB Automation System - RHEL Installer"
    echo "    =================================================================="
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}[STEP]${NC} $1"
    echo "------------------------------------------------------------------------"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

detect_rhel_version() {
    if [ -f /etc/redhat-release ]; then
        RHEL_VERSION=$(rpm -q --queryformat '%{VERSION}' redhat-release-server 2>/dev/null || \
                       rpm -q --queryformat '%{VERSION}' centos-release 2>/dev/null || \
                       rpm -q --queryformat '%{VERSION}' rocky-release 2>/dev/null || \
                       rpm -q --queryformat '%{VERSION}' almalinux-release 2>/dev/null || \
                       cat /etc/redhat-release | grep -oE '[0-9]+' | head -1)
        RHEL_MAJOR=$(echo "$RHEL_VERSION" | cut -d. -f1)
        log_info "Detected RHEL/CentOS version: $RHEL_MAJOR"
    else
        log_error "This script is designed for RHEL/CentOS systems"
        exit 1
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --user)
                SERVICE_USER="$2"
                shift 2
                ;;
            --skip-graphviz)
                SKIP_GRAPHVIZ=true
                shift
                ;;
            --skip-python)
                SKIP_PYTHON=true
                shift
                ;;
            --help)
                echo "Usage: sudo ./install.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --install-dir DIR    Installation directory (default: /opt/mqcmdb)"
                echo "  --user USER          Service user (default: mqcmdb)"
                echo "  --skip-graphviz      Skip GraphViz installation"
                echo "  --skip-python        Skip Python installation (use existing)"
                echo "  --help               Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

install_system_packages() {
    log_step "Installing system packages..."

    # Update package cache
    yum makecache -y || dnf makecache -y

    # Install EPEL repository if not present
    if ! rpm -q epel-release &>/dev/null; then
        log_info "Installing EPEL repository..."
        yum install -y epel-release || dnf install -y epel-release
    fi

    # Base packages
    PACKAGES="wget curl git"

    # Python packages (if not skipping)
    if [ "$SKIP_PYTHON" = false ]; then
        if [ "$RHEL_MAJOR" -ge 8 ]; then
            PACKAGES="$PACKAGES python3 python3-pip python3-devel"
        else
            PACKAGES="$PACKAGES python3 python3-pip python3-devel"
        fi
    fi

    # MariaDB/MySQL client for database connectivity
    PACKAGES="$PACKAGES mariadb-devel gcc"

    log_info "Installing packages: $PACKAGES"
    yum install -y $PACKAGES || dnf install -y $PACKAGES
}

install_graphviz() {
    if [ "$SKIP_GRAPHVIZ" = true ]; then
        log_warn "Skipping GraphViz installation (--skip-graphviz specified)"
        return
    fi

    log_step "Installing GraphViz..."

    if command -v dot &>/dev/null; then
        log_info "GraphViz is already installed: $(dot -V 2>&1)"
    else
        yum install -y graphviz || dnf install -y graphviz
        log_info "GraphViz installed: $(dot -V 2>&1)"
    fi
}

create_service_user() {
    log_step "Creating service user..."

    if id "$SERVICE_USER" &>/dev/null; then
        log_info "User '$SERVICE_USER' already exists"
    else
        useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$SERVICE_USER"
        log_info "Created user '$SERVICE_USER'"
    fi
}

setup_installation_directory() {
    log_step "Setting up installation directory..."

    # Create directory structure
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/output"
    mkdir -p "$INSTALL_DIR/output/data"
    mkdir -p "$INSTALL_DIR/output/diagrams"
    mkdir -p "$INSTALL_DIR/output/reports"
    mkdir -p "$INSTALL_DIR/output/exports"
    mkdir -p "$INSTALL_DIR/input"
    mkdir -p "$INSTALL_DIR/credentials"

    # Copy project files
    log_info "Copying project files to $INSTALL_DIR..."
    cp -r "$PROJECT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_DIR"/requirements.txt "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/config "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/core "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/processors "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/generators "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/analytics "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/utils "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/Database "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/input/* "$INSTALL_DIR/input/" 2>/dev/null || true
    cp -r "$PROJECT_DIR"/deploy "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR"/tools "$INSTALL_DIR/" 2>/dev/null || true

    # Create email config directory
    mkdir -p /etc/mqcmdb

    # Copy email config example if tools directory exists
    if [ -f "$PROJECT_DIR/tools/email_config.ini.example" ]; then
        cp "$PROJECT_DIR/tools/email_config.ini.example" /etc/mqcmdb/email_config.ini.example
        log_info "Email config example copied to /etc/mqcmdb/"
    fi

    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

    log_info "Installation directory: $INSTALL_DIR"
}

install_python_dependencies() {
    log_step "Installing Python dependencies..."

    # Upgrade pip
    python3 -m pip install --upgrade pip

    # Install requirements
    python3 -m pip install -r "$INSTALL_DIR/requirements.txt"

    log_info "Python dependencies installed"
}

setup_environment_file() {
    log_step "Creating environment configuration..."

    ENV_FILE="$INSTALL_DIR/.env"

    cat > "$ENV_FILE" << 'EOF'
# MQ CMDB Environment Configuration
# Edit this file to configure the application

# Database Master Password (set this securely)
# This is used to decrypt database credentials
# DB_MASTER_PASSWORD=your_secure_password

# Python settings
PYTHONIOENCODING=utf-8
PYTHONUNBUFFERED=1

# Logging
LOG_LEVEL=INFO

# ============================================
# Email Notification Settings
# ============================================
# Set EMAIL_ENABLED=true to enable notifications

# Enable/disable email notifications
EMAIL_ENABLED=false

# Recipients (comma-separated for multiple)
# EMAIL_RECIPIENTS=ops-team@company.com,admin@company.com

# Email configuration file (alternative to env vars below)
# EMAIL_CONFIG_FILE=/etc/mqcmdb/email_config.ini

# SMTP server settings (if not using config file)
# SMTP_SERVER=smtp.company.com
# SMTP_PORT=587
# SMTP_USER=your_username
# SMTP_PASSWORD=your_password
# SMTP_FROM=mqcmdb@company.com
# SMTP_USE_TLS=true

# Optional: Confluence credentials for sync
# CONFLUENCE_USER=your.email@company.com
# CONFLUENCE_TOKEN=your-api-token
EOF

    chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    log_info "Environment file created: $ENV_FILE"
    log_warn "IMPORTANT: Edit $ENV_FILE and set DB_MASTER_PASSWORD"
}

setup_systemd_service() {
    log_step "Setting up systemd service..."

    # Create service file
    cat > /etc/systemd/system/mqcmdb.service << EOF
[Unit]
Description=MQ CMDB Automation Pipeline
After=network.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/deploy/run_pipeline.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Create timer for scheduled execution
    cat > /etc/systemd/system/mqcmdb.timer << EOF
[Unit]
Description=Run MQ CMDB Pipeline Daily

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

    # Reload systemd
    systemctl daemon-reload

    log_info "Systemd service created: mqcmdb.service"
    log_info "Systemd timer created: mqcmdb.timer"
    log_info "Enable with: systemctl enable --now mqcmdb.timer"
}

setup_logrotate() {
    log_step "Setting up log rotation..."

    cat > /etc/logrotate.d/mqcmdb << EOF
$INSTALL_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $SERVICE_USER $SERVICE_USER
}
EOF

    log_info "Log rotation configured"
}

print_summary() {
    echo ""
    echo -e "${GREEN}=================================================================="
    echo "  Installation Complete!"
    echo "==================================================================${NC}"
    echo ""
    echo "Installation Directory: $INSTALL_DIR"
    echo "Service User:           $SERVICE_USER"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo ""
    echo "1. Configure database credentials:"
    echo "   sudo -u $SERVICE_USER bash"
    echo "   cd $INSTALL_DIR"
    echo "   export DB_MASTER_PASSWORD='your_secure_password'"
    echo "   python3 db_export.py --setup --profile production"
    echo ""
    echo "2. Edit environment file with master password:"
    echo "   sudo vi $INSTALL_DIR/.env"
    echo ""
    echo "3. Place input configuration files:"
    echo "   - $INSTALL_DIR/input/gateways.json"
    echo "   - $INSTALL_DIR/input/app_to_qmgr.json"
    echo "   - $INSTALL_DIR/input/org_hierarchy.json"
    echo ""
    echo "4. (Optional) Configure email notifications:"
    echo "   sudo cp /etc/mqcmdb/email_config.ini.example /etc/mqcmdb/email_config.ini"
    echo "   sudo vi /etc/mqcmdb/email_config.ini"
    echo "   # Then in $INSTALL_DIR/.env, set:"
    echo "   #   EMAIL_ENABLED=true"
    echo "   #   EMAIL_RECIPIENTS=your-team@company.com"
    echo "   #   EMAIL_CONFIG_FILE=/etc/mqcmdb/email_config.ini"
    echo ""
    echo "5. Test the pipeline manually:"
    echo "   sudo -u $SERVICE_USER $INSTALL_DIR/deploy/run_pipeline.sh"
    echo ""
    echo "6. Enable scheduled execution:"
    echo "   sudo systemctl enable --now mqcmdb.timer"
    echo ""
    echo "7. Check status:"
    echo "   sudo systemctl status mqcmdb.timer"
    echo "   sudo systemctl list-timers mqcmdb.timer"
    echo ""
    echo -e "${BLUE}For manual execution:${NC}"
    echo "   sudo systemctl start mqcmdb.service"
    echo ""
    echo -e "${BLUE}View logs:${NC}"
    echo "   journalctl -u mqcmdb.service -f"
    echo "   ls -la $INSTALL_DIR/logs/"
    echo ""
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

main() {
    print_banner
    parse_args "$@"
    check_root
    detect_rhel_version

    log_info "Installation directory: $INSTALL_DIR"
    log_info "Service user: $SERVICE_USER"

    install_system_packages
    install_graphviz
    create_service_user
    setup_installation_directory
    install_python_dependencies
    setup_environment_file
    setup_systemd_service
    setup_logrotate

    print_summary
}

main "$@"
