#!/usr/bin/env python3
"""
System Monitor Script
Monitors CPU, memory, and disk usage and sends webhook alerts when thresholds are exceeded for 15 minutes.
"""

import os
import json
import time
import socket
import psutil
import requests
import argparse
from datetime import datetime, timedelta
from pathlib import Path

class SystemMonitor:
    def __init__(self, config_file="monitor_config.json"):
        self.config_file = config_file
        self.state_file = "/tmp/system_monitor_state.json"
        self.config = self.load_config()
        self.state = self.load_state()
        
    def load_config(self):
        """Load configuration from JSON file"""
        default_config = {
            "webhook_url": "",
            "cpu_threshold": 90,
            "memory_threshold": 90,
            "disk_threshold": 90,
            "sustained_threshold_minutes": 15,
            "check_interval_seconds": 60,
            "disk_partitions": ["/"]  # Monitor root partition by default
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            # Create default config file
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default config file: {self.config_file}")
            print("Please edit the config file and set your webhook_url before running.")
            return default_config
    
    def load_state(self):
        """Load previous state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading state: {e}")
        
        return {
            "cpu_high_since": None,
            "memory_high_since": None,
            "disk_high_since": {},
            "last_alert_sent": {}
        }
    
    def save_state(self):
        """Save current state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def get_ec2_metadata(self):
        """Get EC2 instance metadata if running on AWS"""
        ec2_info = {
            "instance_id": None,
            "instance_name": None,
            "instance_type": None,
            "availability_zone": None,
            "region": None
        }
        
        try:
            # EC2 metadata endpoint
            metadata_url = "http://169.254.169.254/latest/meta-data"
            headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
            
            # Get token for IMDSv2
            token_response = requests.put(
                f"{metadata_url}/../api/token",
                headers=headers,
                timeout=2
            )
            
            if token_response.status_code == 200:
                token = token_response.text
                auth_headers = {"X-aws-ec2-metadata-token": token}
            else:
                # Fallback to IMDSv1
                auth_headers = {}
            
            # Get instance ID
            try:
                response = requests.get(f"{metadata_url}/instance-id", headers=auth_headers, timeout=2)
                if response.status_code == 200:
                    ec2_info["instance_id"] = response.text
            except:
                pass
            
            # Get instance type
            try:
                response = requests.get(f"{metadata_url}/instance-type", headers=auth_headers, timeout=2)
                if response.status_code == 200:
                    ec2_info["instance_type"] = response.text
            except:
                pass
            
            # Get availability zone
            try:
                response = requests.get(f"{metadata_url}/placement/availability-zone", headers=auth_headers, timeout=2)
                if response.status_code == 200:
                    az = response.text
                    ec2_info["availability_zone"] = az
                    ec2_info["region"] = az[:-1]  # Remove last character to get region
            except:
                pass
            
            # Get instance name from tags (requires EC2 describe-tags permission)
            if ec2_info["instance_id"]:
                try:
                    # Try to get instance name from EC2 API
                    import boto3
                    ec2 = boto3.client('ec2', region_name=ec2_info["region"])
                    response = ec2.describe_tags(
                        Filters=[
                            {'Name': 'resource-id', 'Values': [ec2_info["instance_id"]]},
                            {'Name': 'key', 'Values': ['Name']}
                        ]
                    )
                    if response['Tags']:
                        ec2_info["instance_name"] = response['Tags'][0]['Value']
                except:
                    # If boto3 not available or no permissions, try alternative methods
                    pass
                
        except Exception as e:
            # Not running on EC2 or metadata service unavailable
            pass
        
        return ec2_info
    
    def get_system_info(self):
        """Get hostname, IP address, and EC2 info if available"""
        hostname = socket.gethostname()
        try:
            # Get primary IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "unknown"
        
        # Get EC2 metadata if available
        ec2_info = self.get_ec2_metadata()
        
        return hostname, ip_address, ec2_info
    
    def get_cpu_usage(self):
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=1)
    
    def get_memory_usage(self):
        """Get current memory usage percentage"""
        memory = psutil.virtual_memory()
        return memory.percent
    
    def get_disk_usage(self, partition="/"):
        """Get disk usage percentage for specified partition"""
        try:
            disk = psutil.disk_usage(partition)
            return disk.percent
        except Exception as e:
            print(f"Error getting disk usage for {partition}: {e}")
            return 0
    
    def send_webhook_alert(self, alert_type, current_value, hostname, ip_address, ec2_info, partition=None):
        """Send webhook notification"""
        if not self.config["webhook_url"]:
            print("Webhook URL not configured. Skipping alert.")
            return False
        
        timestamp = datetime.now().isoformat()
        
        # Build server identification string
        server_id = hostname
        if ec2_info["instance_name"]:
            server_id = f"{ec2_info['instance_name']} ({hostname})"
        elif ec2_info["instance_id"]:
            server_id = f"{hostname} ({ec2_info['instance_id']})"
        
        if partition:
            message = f"🚨 DISK ALERT on {server_id}: {partition} usage is {current_value:.1f}% (threshold: {self.config['disk_threshold']}%)"
            alert_key = f"disk_{partition}"
        else:
            threshold = self.config[f"{alert_type}_threshold"]
            message = f"🚨 {alert_type.upper()} ALERT on {server_id}: {alert_type} usage is {current_value:.1f}% (threshold: {threshold}%)"
            alert_key = alert_type
        
        payload = {
            "timestamp": timestamp,
            "hostname": hostname,
            "ip_address": ip_address,
            "alert_type": alert_type,
            "current_value": current_value,
            "threshold": self.config[f"{alert_type}_threshold"] if not partition else self.config["disk_threshold"],
            "message": message,
            "partition": partition,
            "ec2_info": ec2_info
        }
        
        try:
            response = requests.post(
                self.config["webhook_url"],
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"Alert sent successfully: {message}")
                self.state["last_alert_sent"][alert_key] = timestamp
                return True
            else:
                print(f"Failed to send alert. HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending webhook: {e}")
            return False
    
    def send_test_message(self, hostname, ip_address, ec2_info):
        """Send a friendly test message showing current system status"""
        if not self.config["webhook_url"]:
            print("Webhook URL not configured. Skipping test message.")
            return False
        
        # Get current system stats
        cpu_usage = self.get_cpu_usage()
        memory_usage = self.get_memory_usage()
        disk_usage = self.get_disk_usage("/")
        
        # Build server identification
        server_name = hostname
        if ec2_info["instance_name"]:
            server_name = ec2_info["instance_name"]
        elif ec2_info["instance_id"]:
            server_name = f"{hostname} ({ec2_info['instance_id']})"
        
        # Create friendly test message
        message = f"✅ Server '{server_name}' added to monitoring\n"
        message += f"Current status: CPU {cpu_usage:.1f}% | Memory {memory_usage:.1f}% | Disk {disk_usage:.1f}%"
        
        # Simple payload that works with most webhooks
        payload = {
            "text": message,
            "username": "System Monitor",
            "icon_emoji": ":computer:",
            "attachments": [
                {
                    "color": "good",
                    "fields": [
                        {
                            "title": "Server",
                            "value": server_name,
                            "short": True
                        },
                        {
                            "title": "IP Address", 
                            "value": ip_address,
                            "short": True
                        },
                        {
                            "title": "CPU Usage",
                            "value": f"{cpu_usage:.1f}%",
                            "short": True
                        },
                        {
                            "title": "Memory Usage",
                            "value": f"{memory_usage:.1f}%", 
                            "short": True
                        },
                        {
                            "title": "Disk Usage",
                            "value": f"{disk_usage:.1f}%",
                            "short": True
                        }
                    ]
                }
            ]
        }
        
        # Add EC2 info if available
        if ec2_info["instance_type"]:
            payload["attachments"][0]["fields"].append({
                "title": "Instance Type",
                "value": ec2_info["instance_type"],
                "short": True
            })
        
        if ec2_info["availability_zone"]:
            payload["attachments"][0]["fields"].append({
                "title": "Availability Zone", 
                "value": ec2_info["availability_zone"],
                "short": True
            })
        
        try:
            response = requests.post(
                self.config["webhook_url"],
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"Test message sent successfully: {message.split(chr(10))[0]}")
                return True
            else:
                print(f"Failed to send test message. HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending test message: {e}")
            return False
    
    def should_send_alert(self, alert_key, current_time):
        """Check if enough time has passed since last alert to avoid spam"""
        last_alert = self.state["last_alert_sent"].get(alert_key)
        if not last_alert:
            return True
        
        last_alert_time = datetime.fromisoformat(last_alert)
        # Send alert again after 3 hours to avoid spam but ensure we don't miss ongoing issues
        return current_time - last_alert_time > timedelta(hours=3)
    
    def check_thresholds(self):
        """Check if thresholds are exceeded for the required duration"""
        current_time = datetime.now()
        hostname, ip_address, ec2_info = self.get_system_info()
        alert_duration = timedelta(minutes=self.config["sustained_threshold_minutes"])
        
        # Check CPU
        cpu_usage = self.get_cpu_usage()
        if cpu_usage >= self.config["cpu_threshold"]:
            if not self.state["cpu_high_since"]:
                self.state["cpu_high_since"] = current_time.isoformat()
                print(f"CPU usage high: {cpu_usage:.1f}% - starting timer")
            else:
                high_since = datetime.fromisoformat(self.state["cpu_high_since"])
                if current_time - high_since >= alert_duration:
                    if self.should_send_alert("cpu", current_time):
                        self.send_webhook_alert("cpu", cpu_usage, hostname, ip_address, ec2_info)
        else:
            if self.state["cpu_high_since"]:
                print(f"CPU usage returned to normal: {cpu_usage:.1f}%")
            self.state["cpu_high_since"] = None
        
        # Check Memory
        memory_usage = self.get_memory_usage()
        if memory_usage >= self.config["memory_threshold"]:
            if not self.state["memory_high_since"]:
                self.state["memory_high_since"] = current_time.isoformat()
                print(f"Memory usage high: {memory_usage:.1f}% - starting timer")
            else:
                high_since = datetime.fromisoformat(self.state["memory_high_since"])
                if current_time - high_since >= alert_duration:
                    if self.should_send_alert("memory", current_time):
                        self.send_webhook_alert("memory", memory_usage, hostname, ip_address, ec2_info)
        else:
            if self.state["memory_high_since"]:
                print(f"Memory usage returned to normal: {memory_usage:.1f}%")
            self.state["memory_high_since"] = None
        
        # Check Disk partitions
        for partition in self.config["disk_partitions"]:
            disk_usage = self.get_disk_usage(partition)
            partition_key = partition.replace("/", "_root" if partition == "/" else "")
            
            if disk_usage >= self.config["disk_threshold"]:
                if partition not in self.state["disk_high_since"]:
                    self.state["disk_high_since"][partition] = current_time.isoformat()
                    print(f"Disk usage high on {partition}: {disk_usage:.1f}% - starting timer")
                else:
                    high_since = datetime.fromisoformat(self.state["disk_high_since"][partition])
                    if current_time - high_since >= alert_duration:
                        alert_key = f"disk_{partition_key}"
                        if self.should_send_alert(alert_key, current_time):
                            self.send_webhook_alert("disk", disk_usage, hostname, ip_address, ec2_info, partition)
            else:
                if partition in self.state["disk_high_since"]:
                    print(f"Disk usage returned to normal on {partition}: {disk_usage:.1f}%")
                    del self.state["disk_high_since"][partition]
        
        # Save state after checks
        self.save_state()
    
    def run_once(self):
        """Run a single check cycle"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running system check...")
        
        # Display current usage
        cpu_usage = self.get_cpu_usage()
        memory_usage = self.get_memory_usage()
        
        print(f"CPU: {cpu_usage:.1f}% | Memory: {memory_usage:.1f}%", end="")
        
        for partition in self.config["disk_partitions"]:
            disk_usage = self.get_disk_usage(partition)
            print(f" | Disk {partition}: {disk_usage:.1f}%", end="")
        
        print()  # New line
        
        # Check thresholds
        self.check_thresholds()
    
    def run_daemon(self):
        """Run as daemon with continuous monitoring"""
        print("Starting system monitor daemon...")
        print(f"Thresholds: CPU {self.config['cpu_threshold']}%, Memory {self.config['memory_threshold']}%, Disk {self.config['disk_threshold']}%")
        print(f"Alert after {self.config['sustained_threshold_minutes']} minutes of sustained high usage")
        print(f"Alert cooldown: 3 hours between duplicate alerts")
        print(f"Check interval: {self.config['check_interval_seconds']} seconds")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                self.run_once()
                time.sleep(self.config["check_interval_seconds"])
        except KeyboardInterrupt:
            print("\nStopping monitor...")


def main():
    parser = argparse.ArgumentParser(description="System Monitor with Webhook Alerts")
    parser.add_argument("--config", default="monitor_config.json", help="Configuration file path")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron)")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--test-webhook", action="store_true", help="Send test webhook")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.config)
    
    if args.test_webhook:
        hostname, ip_address, ec2_info = monitor.get_system_info()
        # Send a friendly test message instead of alarm format
        monitor.send_test_message(hostname, ip_address, ec2_info)
    elif args.once:
        monitor.run_once()
    elif args.daemon:
        monitor.run_daemon()
    else:
        # Default: run once (suitable for cron)
        monitor.run_once()


if __name__ == "__main__":
    main()

