#!/usr/bin/env python3
"""
Intelligent Alerting System
Monitors service health and sends intelligent alerts with auto-silence and escalation
"""

import os
import sys
import json
import time
import logging
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/intelligent-alerting.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
ALERTING_CONFIG = {
    "database": "/var/log/service-monitoring.db",
    "config_file": "/root/.alerting-config.json",
    "email_config": {
        "smtp_server": "localhost",
        "smtp_port": 25,
        "from_email": "alerts@conflost.com",
        "to_emails": ["admin@conflost.com"]  # Configure these for real use
    },
    "escalation_levels": {
        "warning": {
            "threshold_minutes": 5,
            "max_alerts_per_hour": 2,
            "silence_duration_hours": 1
        },
        "critical": {
            "threshold_minutes": 15,
            "max_alerts_per_hour": 1,
            "silence_duration_hours": 4
        },
        "emergency": {
            "threshold_minutes": 30,
            "max_alerts_per_hour": 1,
            "silence_duration_hours": 12
        }
    },
    "service_priorities": {
        "conflost": "critical",
        "temp188": "critical", 
        "claudexml": "warning",
        "entertheconvo": "critical",
        "claude-play": "warning",
        "aipromptimizer": "warning"
    }
}

class IntelligentAlertManager:
    def __init__(self):
        self.config = ALERTING_CONFIG
        self.monitoring_db = self.config["database"]
        self.alert_config_file = self.config["config_file"]
        self.alert_history = self.load_alert_config()
        
    def load_alert_config(self) -> Dict:
        """Load alert configuration and history"""
        default_config = {
            "last_alerts": {},  # service -> last alert timestamp
            "silenced_until": {},  # service -> silence end timestamp
            "escalation_level": {},  # service -> current escalation level
            "alert_counts": {},  # service -> {hour: count} for rate limiting
            "total_sent": 0,
            "last_cleanup": datetime.now().isoformat()
        }
        
        if os.path.exists(self.alert_config_file):
            try:
                with open(self.alert_config_file, 'r') as f:
                    config = json.load(f)
                    # Ensure all required keys exist
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            except Exception as e:
                logger.error(f"Error loading alert config: {e}")
        
        return default_config
    
    def save_alert_config(self):
        """Save alert configuration and history"""
        try:
            with open(self.alert_config_file, 'w') as f:
                json.dump(self.alert_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving alert config: {e}")
    
    def cleanup_old_data(self):
        """Clean up old alert history data"""
        now = datetime.now()
        last_cleanup = datetime.fromisoformat(self.alert_history.get("last_cleanup", now.isoformat()))
        
        # Clean up every 24 hours
        if (now - last_cleanup).total_seconds() >= 24 * 3600:
            logger.info("🧹 Cleaning up old alert data")
            
            # Remove old alert counts (keep only last 24 hours)
            cutoff_hour = (now - timedelta(hours=24)).strftime("%Y-%m-%d-%H")
            
            for service in list(self.alert_history["alert_counts"].keys()):
                service_counts = self.alert_history["alert_counts"][service]
                cleaned_counts = {
                    hour: count for hour, count in service_counts.items()
                    if hour >= cutoff_hour
                }
                self.alert_history["alert_counts"][service] = cleaned_counts
            
            # Remove expired silences
            for service in list(self.alert_history["silenced_until"].keys()):
                silence_end = datetime.fromisoformat(self.alert_history["silenced_until"][service])
                if now >= silence_end:
                    del self.alert_history["silenced_until"][service]
                    logger.info(f"🔊 Silence expired for {service}")
            
            self.alert_history["last_cleanup"] = now.isoformat()
            self.save_alert_config()
    
    def is_service_silenced(self, service_name: str) -> bool:
        """Check if a service is currently silenced"""
        if service_name not in self.alert_history["silenced_until"]:
            return False
        
        silence_end = datetime.fromisoformat(self.alert_history["silenced_until"][service_name])
        return datetime.now() < silence_end
    
    def get_service_priority(self, service_name: str) -> str:
        """Get the priority level for a service"""
        return self.config["service_priorities"].get(service_name, "warning")
    
    def get_escalation_level(self, service_name: str, downtime_minutes: int) -> str:
        """Determine escalation level based on downtime"""
        priority = self.get_service_priority(service_name)
        
        if priority == "critical":
            if downtime_minutes >= 30:
                return "emergency"
            elif downtime_minutes >= 15:
                return "critical"
            else:
                return "warning"
        else:  # warning priority services
            if downtime_minutes >= 60:
                return "critical"
            elif downtime_minutes >= 30:
                return "warning"
            else:
                return "info"
    
    def check_rate_limits(self, service_name: str, escalation_level: str) -> bool:
        """Check if we can send an alert based on rate limits"""
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        
        # Initialize service alert counts if needed
        if service_name not in self.alert_history["alert_counts"]:
            self.alert_history["alert_counts"][service_name] = {}
        
        service_counts = self.alert_history["alert_counts"][service_name]
        current_count = service_counts.get(current_hour, 0)
        
        # Get rate limit for this escalation level
        escalation_config = self.config["escalation_levels"].get(escalation_level, 
                                                               self.config["escalation_levels"]["warning"])
        max_per_hour = escalation_config["max_alerts_per_hour"]
        
        return current_count < max_per_hour
    
    def record_alert_sent(self, service_name: str):
        """Record that an alert was sent for rate limiting"""
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        
        if service_name not in self.alert_history["alert_counts"]:
            self.alert_history["alert_counts"][service_name] = {}
        
        service_counts = self.alert_history["alert_counts"][service_name]
        service_counts[current_hour] = service_counts.get(current_hour, 0) + 1
        
        self.alert_history["last_alerts"][service_name] = datetime.now().isoformat()
        self.alert_history["total_sent"] += 1
        
        self.save_alert_config()
    
    def auto_silence_service(self, service_name: str, escalation_level: str):
        """Auto-silence a service based on escalation level"""
        escalation_config = self.config["escalation_levels"].get(escalation_level, 
                                                               self.config["escalation_levels"]["warning"])
        silence_hours = escalation_config["silence_duration_hours"]
        
        silence_until = datetime.now() + timedelta(hours=silence_hours)
        self.alert_history["silenced_until"][service_name] = silence_until.isoformat()
        
        logger.info(f"🔇 Auto-silenced {service_name} for {silence_hours} hours until {silence_until}")
        self.save_alert_config()
    
    def send_email_alert(self, service_name: str, status: Dict, escalation_level: str, downtime_minutes: int) -> bool:
        """Send email alert"""
        try:
            email_config = self.config["email_config"]
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config["from_email"]
            msg['To'] = ", ".join(email_config["to_emails"])
            
            # Priority and urgency indicators
            priority_emoji = {
                "info": "ℹ️",
                "warning": "⚠️", 
                "critical": "🚨",
                "emergency": "🆘"
            }
            
            emoji = priority_emoji.get(escalation_level, "⚠️")
            service_priority = self.get_service_priority(service_name)
            
            msg['Subject'] = f"{emoji} {escalation_level.upper()}: {service_name} service down ({downtime_minutes}m)"
            
            # Create alert body
            body = f"""
Service Alert - {escalation_level.upper()} Level

Service: {service_name}
Priority: {service_priority}
Downtime: {downtime_minutes} minutes
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Status Details:
- Port Listening: {'✅' if status.get('port_listening') else '❌'}
- Process Running: {'✅' if status.get('process_running') else '❌'}
- HTTP Responding: {'✅' if status.get('http_responding') else '❌'}

Escalation Level: {escalation_level}
Last Checked: {status.get('timestamp', 'Unknown')}

This alert was generated automatically by the Intelligent Alerting System.
The service will be auto-silenced for {self.config['escalation_levels'][escalation_level]['silence_duration_hours']} hours after this alert.

Dashboard: https://conflost.com/monitor
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (in production, configure SMTP properly)
            # For now, just log the alert
            logger.info(f"📧 Would send email alert: {msg['Subject']}")
            logger.info(f"📧 Email body preview: {body[:200]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert for {service_name}: {e}")
            return False
    
    def send_console_alert(self, service_name: str, status: Dict, escalation_level: str, downtime_minutes: int):
        """Send console/log alert"""
        priority_emoji = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "critical": "🚨",
            "emergency": "🆘"
        }
        
        emoji = priority_emoji.get(escalation_level, "⚠️")
        
        logger.warning(f"\n{'='*60}")
        logger.warning(f"{emoji} INTELLIGENT ALERT - {escalation_level.upper()} LEVEL")
        logger.warning(f"{'='*60}")
        logger.warning(f"Service: {service_name}")
        logger.warning(f"Downtime: {downtime_minutes} minutes")
        logger.warning(f"Priority: {self.get_service_priority(service_name)}")
        logger.warning(f"Port Listening: {'✅' if status.get('port_listening') else '❌'}")
        logger.warning(f"Process Running: {'✅' if status.get('process_running') else '❌'}")
        logger.warning(f"HTTP Responding: {'✅' if status.get('http_responding') else '❌'}")
        logger.warning(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.warning(f"{'='*60}\n")
    
    def log_alert_to_database(self, service_name: str, escalation_level: str, downtime_minutes: int, alert_sent: bool):
        """Log alert to monitoring database"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            # Ensure alert_history table exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    escalation_level TEXT NOT NULL,
                    downtime_minutes INTEGER,
                    alert_sent BOOLEAN,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            ''')
            
            cursor.execute('''
                INSERT INTO alert_history 
                (service, escalation_level, downtime_minutes, alert_sent, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (service_name, escalation_level, downtime_minutes, alert_sent, 
                  f"Alert generated by Intelligent Alerting System"))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log alert to database: {e}")
    
    def get_service_downtime(self, service_name: str) -> Optional[int]:
        """Get current downtime in minutes for a service"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            # Get the most recent failure event
            cursor.execute('''
                SELECT timestamp FROM service_events 
                WHERE service = ? AND event_type = 'failure'
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (service_name,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                failure_time = datetime.fromisoformat(result[0])
                downtime = datetime.now() - failure_time
                return int(downtime.total_seconds() / 60)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting downtime for {service_name}: {e}")
            return None
    
    def check_and_send_alerts(self):
        """Main function to check service status and send intelligent alerts"""
        logger.info("🔍 Checking services for intelligent alerting")
        
        # Clean up old data first
        self.cleanup_old_data()
        
        # Read current service status
        status_file = "/var/log/web-services-status.json"
        if not os.path.exists(status_file):
            logger.warning("Service status file not found")
            return
        
        try:
            with open(status_file, 'r') as f:
                services = json.load(f)
        except Exception as e:
            logger.error(f"Error reading service status: {e}")
            return
        
        alerts_sent = 0
        
        for service_name, status in services.items():
            # Skip if service is healthy
            if status.get('healthy', False):
                continue
            
            # Skip if service is silenced
            if self.is_service_silenced(service_name):
                logger.debug(f"Service {service_name} is silenced, skipping alert")
                continue
            
            # Get downtime
            downtime_minutes = self.get_service_downtime(service_name)
            if downtime_minutes is None:
                downtime_minutes = 5  # Default assumption
            
            # Determine escalation level
            escalation_level = self.get_escalation_level(service_name, downtime_minutes)
            
            # Check rate limits
            if not self.check_rate_limits(service_name, escalation_level):
                logger.info(f"Rate limit reached for {service_name}, skipping alert")
                continue
            
            # Send console alert (always)
            self.send_console_alert(service_name, status, escalation_level, downtime_minutes)
            
            # Send email alert (in production)
            email_sent = self.send_email_alert(service_name, status, escalation_level, downtime_minutes)
            
            # Record alert and apply auto-silence
            self.record_alert_sent(service_name)
            self.auto_silence_service(service_name, escalation_level)
            
            # Log to database
            self.log_alert_to_database(service_name, escalation_level, downtime_minutes, email_sent)
            
            alerts_sent += 1
            logger.info(f"🚨 Sent {escalation_level} alert for {service_name} (downtime: {downtime_minutes}m)")
        
        if alerts_sent > 0:
            logger.info(f"📊 Intelligent Alerting: Sent {alerts_sent} alerts this cycle")
        else:
            logger.info("✅ Intelligent Alerting: All services healthy or silenced")
    
    def show_alert_status(self):
        """Show current alerting status and configuration"""
        print("🚨 Intelligent Alerting System Status")
        print("=" * 50)
        
        print(f"Total alerts sent: {self.alert_history.get('total_sent', 0)}")
        print(f"Last cleanup: {self.alert_history.get('last_cleanup', 'Never')}")
        print()
        
        print("📊 Service Silencing Status:")
        silenced = self.alert_history.get("silenced_until", {})
        if silenced:
            for service, until_time in silenced.items():
                until_dt = datetime.fromisoformat(until_time)
                remaining = until_dt - datetime.now()
                if remaining.total_seconds() > 0:
                    print(f"  🔇 {service}: silenced for {remaining.seconds // 3600}h {(remaining.seconds % 3600) // 60}m")
        else:
            print("  No services currently silenced")
        
        print()
        print("📈 Recent Alert Counts (this hour):")
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        alert_counts = self.alert_history.get("alert_counts", {})
        
        for service, counts in alert_counts.items():
            current_count = counts.get(current_hour, 0)
            if current_count > 0:
                print(f"  📧 {service}: {current_count} alerts")
        
        print()
        print("⚙️ Service Priorities:")
        for service, priority in self.config["service_priorities"].items():
            emoji = "🔴" if priority == "critical" else "🟡"
            print(f"  {emoji} {service}: {priority}")

def main():
    """Main CLI interface"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        alerter = IntelligentAlertManager()
        
        if command == "check":
            alerter.check_and_send_alerts()
        elif command == "status":
            alerter.show_alert_status()
        elif command == "silence":
            if len(sys.argv) < 4:
                print("Usage: intelligent-alerting.py silence <service> <hours>")
                return
            
            service_name = sys.argv[2]
            hours = int(sys.argv[3])
            
            silence_until = datetime.now() + timedelta(hours=hours)
            alerter.alert_history["silenced_until"][service_name] = silence_until.isoformat()
            alerter.save_alert_config()
            
            print(f"🔇 Silenced {service_name} for {hours} hours until {silence_until}")
            
        elif command == "unsilence":
            if len(sys.argv) < 3:
                print("Usage: intelligent-alerting.py unsilence <service>")
                return
            
            service_name = sys.argv[2]
            if service_name in alerter.alert_history["silenced_until"]:
                del alerter.alert_history["silenced_until"][service_name]
                alerter.save_alert_config()
                print(f"🔊 Unsilenced {service_name}")
            else:
                print(f"Service {service_name} is not silenced")
                
        else:
            print("Usage: intelligent-alerting.py [check|status|silence <service> <hours>|unsilence <service>]")
    else:
        # Default: run alert check
        alerter = IntelligentAlertManager()
        alerter.check_and_send_alerts()

if __name__ == "__main__":
    main()