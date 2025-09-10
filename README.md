# System Monitor

A lightweight Python script that monitors CPU, memory, and disk usage on Linux servers and sends webhook alerts when thresholds are exceeded for a specified duration.

## 🚀 **Ready-to-Use One-Liner Installation**

```bash
curl -sSL https://raw.githubusercontent.com/ved123/_LinCheck/main/install.sh | sudo bash -s "YOUR_WEBHOOK_URL_HERE"
```

**Example:**
```bash
curl -sSL https://raw.githubusercontent.com/ved123/_LinCheck/main/install.sh | sudo bash -s "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
```

## Features

- **Multi-resource monitoring**: CPU, memory, and disk usage
- **Configurable thresholds**: Set custom thresholds for each resource (default: 90%)
- **Duration-based alerts**: Only sends alerts if usage stays above threshold for 15 minutes (configurable)
- **Webhook notifications**: Sends detailed alerts via HTTP webhook with hostname and IP
- **State persistence**: Remembers monitoring state across reboots
- **Anti-spam protection**: Prevents duplicate alerts for 3 hours
- **Easy installation**: One-command installation with cron setup
- **Flexible deployment**: Run as cron job or daemon

## Quick Start

### 🚀 One-Line Installation

```bash
curl -sSL https://raw.githubusercontent.com/ved123/_LinCheck/main/quick-install.sh | sudo bash -s "https://your-webhook-url.com/alerts"
```

### 📦 Manual Installation

```bash
# Download the scripts to your server
wget https://raw.githubusercontent.com/ved123/_LinCheck/main/system_monitor.py
wget https://raw.githubusercontent.com/ved123/_LinCheck/main/install.sh
wget https://raw.githubusercontent.com/ved123/_LinCheck/main/monitor_config.json

# Make scripts executable
chmod +x install.sh system_monitor.py

# Install with webhook URL
sudo ./install.sh "https://your-webhook-url.com/alerts"
```

### 2. Configure Webhook URL

If you didn't provide the webhook URL during installation, edit the config file:

```bash
sudo nano /opt/system-monitor/monitor_config.json
```

Update the `webhook_url` field with your webhook endpoint.

### 3. Test the Installation

```bash
# Test a single check
sudo /opt/system-monitor/system_monitor.py --once

# Send a test webhook alert
sudo /opt/system-monitor/system_monitor.py --test-webhook

# View logs
tail -f /var/log/system-monitor.log
```

## Configuration

The monitor is configured via `/opt/system-monitor/monitor_config.json`:

```json
{
  "webhook_url": "https://your-webhook-url.com/alerts",
  "cpu_threshold": 90,
  "memory_threshold": 90,
  "disk_threshold": 90,
  "sustained_threshold_minutes": 15,
  "check_interval_seconds": 60,
  "disk_partitions": ["/", "/var", "/home"]
}
```

### Configuration Options

- `webhook_url`: HTTP endpoint to receive alert notifications
- `cpu_threshold`: CPU usage percentage threshold (0-100)
- `memory_threshold`: Memory usage percentage threshold (0-100)
- `disk_threshold`: Disk usage percentage threshold (0-100)
- `sustained_threshold_minutes`: Minutes of sustained high usage before alerting
- `check_interval_seconds`: Seconds between checks (daemon mode only)
- `disk_partitions`: Array of mount points to monitor

## Webhook Payload

When an alert is triggered, the following JSON payload is sent to your webhook:

```json
{
  "timestamp": "2024-01-15T14:30:45.123456",
  "hostname": "web-server-01",
  "ip_address": "10.0.1.15",
  "alert_type": "cpu",
  "current_value": 95.2,
  "threshold": 90,
  "message": "🚨 CPU ALERT: cpu usage is 95.2% (threshold: 90%)",
  "partition": null
}
```

For disk alerts, the `partition` field contains the mount point (e.g., "/var").

## Usage Examples

### Cron Job (Recommended)

The installation script automatically sets up a cron job that runs every minute:

```bash
* * * * * cd /opt/system-monitor && python3 system_monitor.py --once >> /var/log/system-monitor.log 2>&1
```

### Manual Execution

```bash
# Run a single check
python3 system_monitor.py --once

# Run as daemon (continuous monitoring)
python3 system_monitor.py --daemon

# Test webhook
python3 system_monitor.py --test-webhook

# Use custom config file
python3 system_monitor.py --config /path/to/custom_config.json --once
```

### Integration Examples

#### Slack Webhook

Create a Slack app and use the webhook URL:

```json
{
  "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
}
```

#### Discord Webhook

Use a Discord channel webhook:

```json
{
  "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
}
```

#### Custom HTTP Endpoint

Any HTTP endpoint that accepts JSON POST requests:

```json
{
  "webhook_url": "https://your-monitoring-system.com/api/alerts"
}
```

## Monitoring Multiple Servers

To deploy across multiple servers:

```bash
# One-liner deployment to multiple servers
WEBHOOK_URL="https://your-webhook-url.com/alerts"
SERVERS=("server1.example.com" "server2.example.com" "server3.example.com")

for server in "${SERVERS[@]}"; do
    echo "Deploying to $server..."
    ssh root@$server "curl -sSL https://raw.githubusercontent.com/ved123/_LinCheck/main/quick-install.sh | bash -s '$WEBHOOK_URL'"
done
```

#### Alternative: Manual deployment script
```bash
# Create deployment script
cat > deploy.sh << 'EOF'
#!/bin/bash
SERVERS=("server1.example.com" "server2.example.com" "server3.example.com")
WEBHOOK_URL="https://your-webhook-url.com/alerts"

for server in "${SERVERS[@]}"; do
    echo "Deploying to $server..."
    scp system_monitor.py install.sh monitor_config.json root@$server:/tmp/
    ssh root@$server "cd /tmp && ./install.sh '$WEBHOOK_URL'"
done
EOF

chmod +x deploy.sh
./deploy.sh
```

## Troubleshooting

### Check if Monitor is Running

```bash
# Check cron job
crontab -l | grep system_monitor

# Check recent logs
tail -20 /var/log/system-monitor.log

# Check system status
ps aux | grep system_monitor
```

### Common Issues

1. **Webhook not working**: Verify URL and network connectivity
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"test":"message"}' YOUR_WEBHOOK_URL
   ```

2. **Permission errors**: Ensure script runs as root
   ```bash
   sudo /opt/system-monitor/system_monitor.py --once
   ```

3. **Missing dependencies**: Install required packages
   ```bash
   pip3 install psutil requests
   ```

### Debug Mode

Enable verbose logging by modifying the script or checking logs:

```bash
# Watch logs in real-time
tail -f /var/log/system-monitor.log

# Check cron logs
grep CRON /var/log/syslog | tail -10
```

## Uninstallation

```bash
sudo ./install.sh --uninstall
```

This removes:
- Cron job
- Installation directory (`/opt/system-monitor`)
- Log file (`/var/log/system-monitor.log`)

## Requirements

- Linux server (tested on Ubuntu, CentOS, RHEL)
- Python 3.6+
- pip3
- Internet access for webhook notifications
- Root access for installation

## License

MIT License - feel free to modify and distribute.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on multiple distributions
5. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs: `/var/log/system-monitor.log`
- Test with `--test-webhook` flag
- Verify configuration in `/opt/system-monitor/monitor_config.json`

