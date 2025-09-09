#!/bin/bash

# Quick Install Script for System Monitor
# Usage: curl -sSL https://raw.githubusercontent.com/yourusername/system-monitor/main/quick-install.sh | sudo bash -s "https://your-webhook-url.com"

set -e

WEBHOOK_URL="$1"
REPO_URL="https://raw.githubusercontent.com/yourusername/system-monitor/main"
TEMP_DIR="/tmp/system-monitor-$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

# Check if webhook URL provided
if [[ -z "$WEBHOOK_URL" ]]; then
    log_error "Webhook URL is required!"
    echo "Usage: curl -sSL https://raw.githubusercontent.com/yourusername/system-monitor/main/quick-install.sh | sudo bash -s \"https://your-webhook-url.com\""
    exit 1
fi

log_info "Starting quick installation of System Monitor..."
log_info "Webhook URL: $WEBHOOK_URL"

# Create temporary directory
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Download files
log_info "Downloading files from GitHub..."
curl -sSL -o system_monitor.py "$REPO_URL/system_monitor.py"
curl -sSL -o install.sh "$REPO_URL/install.sh"
curl -sSL -o monitor_config.json "$REPO_URL/monitor_config.json"

# Make scripts executable
chmod +x system_monitor.py install.sh

# Run installation
log_info "Running installation..."
./install.sh "$WEBHOOK_URL"

# Cleanup
cd /
rm -rf "$TEMP_DIR"

log_info "Quick installation completed!"
log_info "Monitor is now running and will check every minute via cron."
log_info "View logs: tail -f /var/log/system-monitor.log"
