# MQ CMDB Deployment Guide

This guide covers deploying the MQ CMDB automation pipeline on a Linux server with automatic Confluence publishing.

## Prerequisites

- Python 3.8+
- GraphViz (for diagram generation)
- Network access to Confluence (if publishing enabled)

## Quick Start

### 1. Install System Dependencies

```bash
# RHEL/CentOS/Rocky
sudo dnf install python3 python3-pip graphviz

# Ubuntu/Debian
sudo apt-get install python3 python3-pip python3-venv graphviz
```

### 2. Deploy Application

```bash
# Create application directory
sudo mkdir -p /opt/mqcmdb
sudo chown $USER:$USER /opt/mqcmdb

# Clone or copy project files
cp -r /path/to/MQ_test1/* /opt/mqcmdb/

# Create virtual environment
cd /opt/mqcmdb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Confluence Publishing

Edit `/opt/mqcmdb/config/settings.py`:

```python
# Enable Confluence publishing
CONFLUENCE_ENABLED = True
CONFLUENCE_URL = "https://your-company.atlassian.net/wiki"  # or your Server URL
CONFLUENCE_SPACE_KEY = "MQCMDB"
CONFLUENCE_PAGE_TITLE = "MQ CMDB - Enterprise Architecture Documentation"
```

For credentials, use environment variables (recommended) or edit settings.py:

```bash
# Create environment file
cat > /opt/mqcmdb/.env << 'EOF'
CONFLUENCE_USERNAME=your.email@company.com
CONFLUENCE_API_TOKEN=your-api-token
EOF
chmod 600 /opt/mqcmdb/.env
```

### 4. Test Run

```bash
cd /opt/mqcmdb
./deploy/run_pipeline.sh
```

## Scheduling Options

### Option A: Systemd Timer (Recommended)

```bash
# Copy service files
sudo cp deploy/systemd/mqcmdb-pipeline.service /etc/systemd/system/
sudo cp deploy/systemd/mqcmdb-pipeline.timer /etc/systemd/system/

# Create service user
sudo useradd -r -s /bin/false mqcmdb

# Set ownership
sudo chown -R mqcmdb:mqcmdb /opt/mqcmdb

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable mqcmdb-pipeline.timer
sudo systemctl start mqcmdb-pipeline.timer

# Check status
sudo systemctl status mqcmdb-pipeline.timer
sudo systemctl list-timers mqcmdb-pipeline.timer
```

To run manually:
```bash
sudo systemctl start mqcmdb-pipeline.service
```

View logs:
```bash
journalctl -u mqcmdb-pipeline.service -f
```

### Option B: Cron

```bash
# Edit crontab
crontab -e

# Add entry to run daily at 6 AM
0 6 * * * /opt/mqcmdb/deploy/run_pipeline.sh --quiet >> /opt/mqcmdb/logs/cron.log 2>&1
```

## Confluence Authentication

### For Confluence Cloud

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create an API token
3. Use your email as username and the token as password

### For Confluence Server/Data Center

**Option 1: Personal Access Token (Recommended)**
1. Go to your Confluence profile → Personal Access Tokens
2. Create a new token
3. Set `CONFLUENCE_PAT` in your environment

**Option 2: Basic Auth**
1. Use your Confluence username
2. Use your password or an app-specific password

## Directory Structure

```
/opt/mqcmdb/
├── config/
│   └── settings.py          # Configuration
├── input/
│   ├── org_hierarchy.json   # Organization structure
│   ├── app_to_qmgr.json     # Application mappings
│   └── gateways.json        # Gateway definitions
├── output/
│   ├── all_MQCMDB_assets.json
│   ├── mq_topology.pdf
│   ├── EA_Documentation_*.txt
│   └── ...
├── logs/
│   └── pipeline_*.log
├── deploy/
│   ├── run_pipeline.sh
│   └── systemd/
├── venv/
└── .env                      # Credentials (create this)
```

## Monitoring

### Log Files

- Pipeline logs: `/opt/mqcmdb/logs/pipeline_YYYYMMDD.log`
- Systemd logs: `journalctl -u mqcmdb-pipeline.service`

### Health Checks

```bash
# Check last run status
tail -20 /opt/mqcmdb/logs/pipeline_$(date +%Y%m%d).log

# Check timer status
systemctl status mqcmdb-pipeline.timer

# List next scheduled runs
systemctl list-timers --all | grep mqcmdb
```

## Troubleshooting

### Pipeline fails with "Connection error"

- Check network connectivity to database and Confluence
- Verify firewall rules allow outbound HTTPS (port 443)

### Confluence publishing fails

1. Test credentials:
   ```bash
   curl -u "user:token" "https://your-confluence/rest/api/space/SPACEKEY"
   ```

2. Check space permissions - user needs "Add Pages" permission

3. Verify URL format:
   - Cloud: `https://company.atlassian.net/wiki`
   - Server: `https://confluence.company.com` (no /wiki usually)

### GraphViz errors

```bash
# Check if installed
which dot

# Install if missing
sudo dnf install graphviz  # or apt-get
```

## Security Considerations

1. **Credentials**: Store in `.env` file with `chmod 600`
2. **Service User**: Run as dedicated `mqcmdb` user, not root
3. **File Permissions**: Restrict access to config and credentials
4. **Network**: Use HTTPS for all external connections
