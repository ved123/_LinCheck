#!/bin/bash

# System Monitor Installation Script
# This script installs the system monitor and sets up a cron job

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/system-monitor"
SERVICE_USER="root"
WEBHOOK_URL=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
System Monitor Installation Script

Usage: $0 [WEBHOOK_URL] [OPTIONS]
   or: $0 [OPTIONS]

POSITIONAL ARGUMENTS:
    WEBHOOK_URL             The webhook URL for alerts (optional)

OPTIONS:
    -w, --webhook-url URL   Set the webhook URL for alerts
    -h, --help              Show this help message
    -u, --uninstall         Uninstall the system monitor

EXAMPLES:
    $0 "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    $0 --webhook-url "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    $0 --uninstall

The script will:
1. Install required Python packages
2. Copy monitor files to $INSTALL_DIR
3. Set up a cron job to run every minute
4. Configure the webhook URL

EOF
}

check_requirements() {
    log_info "Checking system requirements..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check if Python 3 is installed
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check if pip is installed
    if ! command -v pip3 &> /dev/null; then
        log_warn "pip3 not found, attempting to install..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y python3-pip
        elif command -v yum &> /dev/null; then
            yum install -y python3-pip
        elif command -v dnf &> /dev/null; then
            dnf install -y python3-pip
        else
            log_error "Could not install pip3. Please install it manually."
            exit 1
        fi
    fi
}

install_python_packages() {
    log_info "Installing required Python packages..."
    pip3 install psutil requests
}

create_install_directory() {
    log_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
}

copy_files() {
    log_info "Copying monitor files..."
    
    # Copy the main script
    if [[ -f "$SCRIPT_DIR/system_monitor.py" ]]; then
        cp "$SCRIPT_DIR/system_monitor.py" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/system_monitor.py"
    else
        log_error "system_monitor.py not found in $SCRIPT_DIR"
        exit 1
    fi
    
    # Copy or create config file
    if [[ -f "$SCRIPT_DIR/monitor_config.json" ]]; then
        cp "$SCRIPT_DIR/monitor_config.json" "$INSTALL_DIR/"
    else
        log_warn "monitor_config.json not found, creating default config"
        cat > "$INSTALL_DIR/monitor_config.json" << EOF
{
  "webhook_url": "",
  "cpu_threshold": 90,
  "memory_threshold": 90,
  "disk_threshold": 90,
  "alert_duration_minutes": 15,
  "check_interval_seconds": 60,
  "disk_partitions": ["/"]
}
EOF
    fi
}

configure_webhook() {
    if [[ -n "$WEBHOOK_URL" ]]; then
        log_info "Configuring webhook URL..."
        python3 << EOF
import json
config_file = "$INSTALL_DIR/monitor_config.json"
with open(config_file, 'r') as f:
    config = json.load(f)
config['webhook_url'] = "$WEBHOOK_URL"
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
EOF
        log_info "Webhook URL configured successfully"
    else
        log_warn "No webhook URL provided. You'll need to edit $INSTALL_DIR/monitor_config.json manually"
    fi
}

setup_cron() {
    log_info "Setting up cron job..."
    
    # Create cron job that runs every minute
    CRON_JOB="* * * * * cd $INSTALL_DIR && python3 system_monitor.py --once >> /var/log/system-monitor.log 2>&1"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "system_monitor.py"; then
        log_warn "Cron job already exists, removing old one..."
        crontab -l 2>/dev/null | grep -v "system_monitor.py" | crontab -
    fi
    
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    
    log_info "Cron job added successfully"
    log_info "Monitor will run every minute and log to /var/log/system-monitor.log"
}

test_installation() {
    log_info "Testing installation..."
    
    cd "$INSTALL_DIR"
    if python3 system_monitor.py --once; then
        log_info "Installation test passed!"
    else
        log_error "Installation test failed"
        exit 1
    fi
}

send_test_alert() {
    log_info "Sending test alert..."
    cd "$INSTALL_DIR"
    if python3 system_monitor.py --test-webhook; then
        log_info "Test alert sent successfully!"
    else
        log_warn "Test alert failed - check your webhook URL configuration"
    fi
}

uninstall() {
    log_info "Uninstalling system monitor..."
    
    # Remove cron job
    if crontab -l 2>/dev/null | grep -q "system_monitor.py"; then
        log_info "Removing cron job..."
        crontab -l 2>/dev/null | grep -v "system_monitor.py" | crontab -
    fi
    
    # Remove installation directory
    if [[ -d "$INSTALL_DIR" ]]; then
        log_info "Removing installation directory..."
        rm -rf "$INSTALL_DIR"
    fi
    
    # Remove log file
    if [[ -f "/var/log/system-monitor.log" ]]; then
        log_info "Removing log file..."
        rm -f "/var/log/system-monitor.log"
    fi
    
    log_info "System monitor uninstalled successfully"
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -w|--webhook-url)
                WEBHOOK_URL="$2"
                shift 2
                ;;
            -u|--uninstall)
                uninstall
                exit 0
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                # If it's not an option (doesn't start with -), treat as webhook URL
                if [[ -z "$WEBHOOK_URL" ]]; then
                    WEBHOOK_URL="$1"
                    shift
                else
                    log_error "Multiple webhook URLs provided: '$WEBHOOK_URL' and '$1'"
                    show_help
                    exit 1
                fi
                ;;
        esac
    done
    
    log_info "Starting system monitor installation..."
    
    check_requirements
    install_python_packages
    create_install_directory
    copy_files
    configure_webhook
    setup_cron
    test_installation
    
    if [[ -n "$WEBHOOK_URL" ]]; then
        send_test_alert
    fi
    
    log_info "Installation completed successfully!"
    log_info ""
    log_info "Configuration file: $INSTALL_DIR/monitor_config.json"
    log_info "Log file: /var/log/system-monitor.log"
    log_info ""
    log_info "To view logs: tail -f /var/log/system-monitor.log"
    log_info "To test webhook: cd $INSTALL_DIR && python3 system_monitor.py --test-webhook"
    log_info "To uninstall: $0 --uninstall"
    
    if [[ -z "$WEBHOOK_URL" ]]; then
        log_warn "Don't forget to configure your webhook URL in $INSTALL_DIR/monitor_config.json"
    fi
}

main "$@"


