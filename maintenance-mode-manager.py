#!/usr/bin/env python3
"""
Maintenance Mode and Scheduled Downtime Manager
Manages planned maintenance windows, service downtime, and maintenance notifications
"""

import os
import sys
import json
import logging
import sqlite3
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/maintenance-mode.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MAINTENANCE_CONFIG = {
    "database": "/var/log/maintenance-schedules.db",
    "maintenance_page_template": "/root/maintenance-page.html",
    "nginx_maintenance_config": "/etc/nginx/sites-available/maintenance",
    "services": {
        "conflost": {"domain": "conflost.com", "port": 5006, "priority": "critical"},
        "temp188": {"domain": "temp188.com", "port": 5000, "priority": "critical"},
        "claudexml": {"domain": "claudexml.com", "port": 5007, "priority": "medium"},
        "entertheconvo": {"domain": "entertheconvo.com", "port": 8082, "priority": "critical"},
        "claude-play": {"domain": "claude-play.com", "port": 3001, "priority": "medium"},
        "aipromptimizer": {"domain": "aipromptimizer.com", "port": 80, "priority": "medium"}
    }
}

class MaintenanceModeManager:
    def __init__(self):
        self.config = MAINTENANCE_CONFIG
        self.db_path = self.config["database"]
        self.init_database()
        self.create_maintenance_assets()
    
    def init_database(self):
        """Initialize maintenance scheduling database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create maintenance schedules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    scheduled_start DATETIME NOT NULL,
                    scheduled_end DATETIME NOT NULL,
                    actual_start DATETIME,
                    actual_end DATETIME,
                    status TEXT DEFAULT 'scheduled',
                    created_by TEXT DEFAULT 'system',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notification_sent BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Create maintenance logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    details TEXT,
                    status TEXT,
                    FOREIGN KEY (schedule_id) REFERENCES maintenance_schedules (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Maintenance database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize maintenance database: {e}")
    
    def create_maintenance_assets(self):
        """Create maintenance page template and nginx config"""
        try:
            # Create maintenance page HTML template
            maintenance_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔧 Maintenance Mode - {service_name}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .maintenance-container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 50px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 600px;
            margin: 20px;
        }
        .maintenance-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 20px;
            font-weight: 300;
        }
        .service-name {
            color: #FFD700;
            font-weight: bold;
        }
        .description {
            font-size: 1.2em;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        .time-info {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .time-label {
            font-size: 0.9em;
            margin-bottom: 5px;
            opacity: 0.8;
        }
        .time-value {
            font-size: 1.1em;
            font-weight: bold;
        }
        .status-info {
            margin-top: 30px;
            font-size: 0.9em;
            opacity: 0.8;
        }
        @media (max-width: 768px) {
            .maintenance-container {
                padding: 30px 20px;
                margin: 10px;
            }
            h1 {
                font-size: 2em;
            }
            .maintenance-icon {
                font-size: 3em;
            }
        }
    </style>
</head>
<body>
    <div class="maintenance-container">
        <div class="maintenance-icon">🔧</div>
        <h1>Scheduled Maintenance</h1>
        <p class="description">
            <span class="service-name">{service_name}</span> is currently undergoing scheduled maintenance 
            to improve performance and add new features.
        </p>
        
        <div class="time-info">
            <div class="time-label">Started:</div>
            <div class="time-value">{start_time}</div>
        </div>
        
        <div class="time-info">
            <div class="time-label">Expected to complete:</div>
            <div class="time-value">{end_time}</div>
        </div>
        
        <div class="status-info">
            <p>We apologize for any inconvenience. Please check back soon!</p>
            <p>For urgent matters, contact: admin@conflost.com</p>
        </div>
    </div>
</body>
</html>'''
            
            with open(self.config["maintenance_page_template"], 'w') as f:
                f.write(maintenance_html)
            
            logger.info("Maintenance page template created")
            
        except Exception as e:
            logger.error(f"Failed to create maintenance assets: {e}")
    
    def schedule_maintenance(self, service_name: str, title: str, description: str, 
                           start_time: datetime, end_time: datetime, created_by: str = "admin") -> int:
        """Schedule a maintenance window"""
        try:
            if service_name not in self.config["services"]:
                raise ValueError(f"Unknown service: {service_name}")
            
            if start_time >= end_time:
                raise ValueError("Start time must be before end time")
            
            if start_time <= datetime.now():
                raise ValueError("Start time must be in the future")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO maintenance_schedules 
                (service_name, title, description, scheduled_start, scheduled_end, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (service_name, title, description, start_time.isoformat(), 
                  end_time.isoformat(), created_by))
            
            schedule_id = cursor.lastrowid
            
            # Log the scheduling action
            cursor.execute('''
                INSERT INTO maintenance_logs (schedule_id, action, details, status)
                VALUES (?, ?, ?, ?)
            ''', (schedule_id, "scheduled", f"Maintenance scheduled by {created_by}", "success"))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📅 Maintenance scheduled for {service_name}: {title}")
            logger.info(f"   Start: {start_time}")
            logger.info(f"   End: {end_time}")
            
            return schedule_id
            
        except Exception as e:
            logger.error(f"Failed to schedule maintenance: {e}")
            raise
    
    def get_active_maintenance(self) -> List[Dict]:
        """Get currently active maintenance windows"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                SELECT id, service_name, title, description, scheduled_start, scheduled_end, 
                       actual_start, status
                FROM maintenance_schedules 
                WHERE status IN ('active', 'started') 
                   OR (status = 'scheduled' AND scheduled_start <= ? AND scheduled_end >= ?)
                ORDER BY scheduled_start
            ''', (now, now))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "service_name": row[1],
                    "title": row[2],
                    "description": row[3],
                    "scheduled_start": row[4],
                    "scheduled_end": row[5],
                    "actual_start": row[6],
                    "status": row[7]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get active maintenance: {e}")
            return []
    
    def get_upcoming_maintenance(self, hours_ahead: int = 24) -> List[Dict]:
        """Get maintenance scheduled within the next N hours"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            future = (now + timedelta(hours=hours_ahead)).isoformat()
            
            cursor.execute('''
                SELECT id, service_name, title, description, scheduled_start, scheduled_end, status
                FROM maintenance_schedules 
                WHERE status = 'scheduled' AND scheduled_start <= ? AND scheduled_start > ?
                ORDER BY scheduled_start
            ''', (future, now.isoformat()))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "service_name": row[1],
                    "title": row[2],
                    "description": row[3],
                    "scheduled_start": row[4],
                    "scheduled_end": row[5],
                    "status": row[6]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get upcoming maintenance: {e}")
            return []
    
    def start_maintenance(self, schedule_id: int) -> bool:
        """Start a scheduled maintenance window"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get maintenance details
            cursor.execute('''
                SELECT service_name, title, scheduled_start, scheduled_end, status
                FROM maintenance_schedules WHERE id = ?
            ''', (schedule_id,))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Maintenance schedule {schedule_id} not found")
            
            service_name, title, scheduled_start, scheduled_end, status = result
            
            if status not in ['scheduled', 'active']:
                raise ValueError(f"Cannot start maintenance in status: {status}")
            
            logger.info(f"🔧 Starting maintenance for {service_name}: {title}")
            
            # Update status to active
            cursor.execute('''
                UPDATE maintenance_schedules 
                SET status = 'active', actual_start = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (schedule_id,))
            
            # Log the start action
            cursor.execute('''
                INSERT INTO maintenance_logs (schedule_id, action, details, status)
                VALUES (?, ?, ?, ?)
            ''', (schedule_id, "started", f"Maintenance started for {service_name}", "success"))
            
            conn.commit()
            conn.close()
            
            # Stop the service
            self.stop_service_for_maintenance(service_name)
            
            # Enable maintenance page
            self.enable_maintenance_page(service_name, scheduled_start, scheduled_end)
            
            logger.info(f"✅ Maintenance started for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start maintenance: {e}")
            
            # Log the failure
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO maintenance_logs (schedule_id, action, details, status)
                    VALUES (?, ?, ?, ?)
                ''', (schedule_id, "start_failed", str(e), "failed"))
                conn.commit()
                conn.close()
            except:
                pass
            
            return False
    
    def end_maintenance(self, schedule_id: int) -> bool:
        """End a maintenance window"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get maintenance details
            cursor.execute('''
                SELECT service_name, title, status
                FROM maintenance_schedules WHERE id = ?
            ''', (schedule_id,))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Maintenance schedule {schedule_id} not found")
            
            service_name, title, status = result
            
            if status != 'active':
                raise ValueError(f"Cannot end maintenance in status: {status}")
            
            logger.info(f"🔧 Ending maintenance for {service_name}: {title}")
            
            # Update status to completed
            cursor.execute('''
                UPDATE maintenance_schedules 
                SET status = 'completed', actual_end = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (schedule_id,))
            
            # Log the end action
            cursor.execute('''
                INSERT INTO maintenance_logs (schedule_id, action, details, status)
                VALUES (?, ?, ?, ?)
            ''', (schedule_id, "completed", f"Maintenance completed for {service_name}", "success"))
            
            conn.commit()
            conn.close()
            
            # Disable maintenance page
            self.disable_maintenance_page(service_name)
            
            # Start the service
            self.start_service_after_maintenance(service_name)
            
            logger.info(f"✅ Maintenance completed for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to end maintenance: {e}")
            
            # Log the failure
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO maintenance_logs (schedule_id, action, details, status)
                    VALUES (?, ?, ?, ?)
                ''', (schedule_id, "end_failed", str(e), "failed"))
                conn.commit()
                conn.close()
            except:
                pass
            
            return False
    
    def stop_service_for_maintenance(self, service_name: str):
        """Stop service for maintenance"""
        try:
            logger.info(f"  🛑 Stopping {service_name} for maintenance")
            result = subprocess.run(["python3", "/root/service-cli.py", "stop", service_name], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"  ✅ {service_name} stopped successfully")
            else:
                logger.warning(f"  ⚠️ Failed to stop {service_name}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error stopping service {service_name}: {e}")
    
    def start_service_after_maintenance(self, service_name: str):
        """Start service after maintenance"""
        try:
            logger.info(f"  🚀 Starting {service_name} after maintenance")
            result = subprocess.run(["python3", "/root/service-cli.py", "start", service_name], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"  ✅ {service_name} started successfully")
            else:
                logger.warning(f"  ⚠️ Failed to start {service_name}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error starting service {service_name}: {e}")
    
    def enable_maintenance_page(self, service_name: str, start_time: str, end_time: str):
        """Enable maintenance page for a service"""
        try:
            # Create service-specific maintenance page
            with open(self.config["maintenance_page_template"], 'r') as f:
                template = f.read()
            
            # Format dates for display
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            
            maintenance_page = template.format(
                service_name=service_name.title(),
                start_time=start_dt.strftime("%Y-%m-%d %H:%M UTC"),
                end_time=end_dt.strftime("%Y-%m-%d %H:%M UTC")
            )
            
            # Write maintenance page
            maintenance_file = f"/var/www/maintenance_{service_name}.html"
            with open(maintenance_file, 'w') as f:
                f.write(maintenance_page)
            
            logger.info(f"  📄 Maintenance page created: {maintenance_file}")
            
            # Note: In a real deployment, you would also configure nginx to serve 
            # the maintenance page instead of proxying to the service
            
        except Exception as e:
            logger.error(f"Failed to enable maintenance page for {service_name}: {e}")
    
    def disable_maintenance_page(self, service_name: str):
        """Disable maintenance page for a service"""
        try:
            maintenance_file = f"/var/www/maintenance_{service_name}.html"
            if os.path.exists(maintenance_file):
                os.remove(maintenance_file)
                logger.info(f"  🗑️ Maintenance page removed: {maintenance_file}")
            
            # Note: In a real deployment, you would also reconfigure nginx to 
            # proxy back to the service
            
        except Exception as e:
            logger.error(f"Failed to disable maintenance page for {service_name}: {e}")
    
    def check_scheduled_maintenance(self):
        """Check for scheduled maintenance that should start now"""
        now = datetime.now()
        upcoming = self.get_upcoming_maintenance(hours_ahead=1)  # Check next hour
        
        for maintenance in upcoming:
            scheduled_start = datetime.fromisoformat(maintenance["scheduled_start"])
            
            # If maintenance should start within the next 5 minutes
            if (scheduled_start - now).total_seconds() <= 300:
                logger.info(f"⏰ Auto-starting scheduled maintenance: {maintenance['title']}")
                self.start_maintenance(maintenance["id"])
        
        # Check for maintenance that should end
        active = self.get_active_maintenance()
        for maintenance in active:
            if maintenance["status"] == "active":
                scheduled_end = datetime.fromisoformat(maintenance["scheduled_end"])
                
                # If maintenance should have ended
                if now >= scheduled_end:
                    logger.info(f"⏰ Auto-ending completed maintenance: {maintenance['title']}")
                    self.end_maintenance(maintenance["id"])
    
    def show_maintenance_status(self):
        """Show current maintenance status"""
        print("🔧 Maintenance Mode Manager Status")
        print("=" * 50)
        
        # Active maintenance
        active = self.get_active_maintenance()
        if active:
            print(f"🚨 Active Maintenance ({len(active)}):")
            for maintenance in active:
                start_time = datetime.fromisoformat(maintenance["scheduled_start"])
                end_time = datetime.fromisoformat(maintenance["scheduled_end"])
                print(f"  {maintenance['service_name']:15} | {maintenance['title']}")
                print(f"  {'':15}   {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}")
                print()
        else:
            print("✅ No active maintenance")
        
        # Upcoming maintenance
        upcoming = self.get_upcoming_maintenance(hours_ahead=72)  # Next 3 days
        if upcoming:
            print(f"📅 Upcoming Maintenance ({len(upcoming)}):")
            for maintenance in upcoming:
                start_time = datetime.fromisoformat(maintenance["scheduled_start"])
                end_time = datetime.fromisoformat(maintenance["scheduled_end"])
                time_until = start_time - datetime.now()
                hours_until = int(time_until.total_seconds() / 3600)
                
                print(f"  {maintenance['service_name']:15} | {maintenance['title']}")
                print(f"  {'':15}   {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')} (in {hours_until}h)")
                print()
        else:
            print("📅 No upcoming maintenance scheduled")

def main():
    """Main CLI interface"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        manager = MaintenanceModeManager()
        
        if command == "schedule":
            if len(sys.argv) < 7:
                print("Usage: maintenance-mode-manager.py schedule <service> <title> <description> <start_time> <end_time>")
                print("Time format: YYYY-MM-DD HH:MM")
                return
            
            service_name = sys.argv[2]
            title = sys.argv[3]
            description = sys.argv[4]
            start_time_str = sys.argv[5] + " " + sys.argv[6]
            end_time_str = sys.argv[7] + " " + sys.argv[8] if len(sys.argv) > 8 else start_time_str
            
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
                end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
                
                schedule_id = manager.schedule_maintenance(service_name, title, description, 
                                                         start_time, end_time)
                print(f"✅ Maintenance scheduled with ID: {schedule_id}")
                
            except ValueError as e:
                print(f"❌ Error: {e}")
                
        elif command == "start":
            if len(sys.argv) < 3:
                print("Usage: maintenance-mode-manager.py start <schedule_id>")
                return
            
            schedule_id = int(sys.argv[2])
            if manager.start_maintenance(schedule_id):
                print(f"✅ Maintenance {schedule_id} started")
            else:
                print(f"❌ Failed to start maintenance {schedule_id}")
                
        elif command == "end":
            if len(sys.argv) < 3:
                print("Usage: maintenance-mode-manager.py end <schedule_id>")
                return
            
            schedule_id = int(sys.argv[2])
            if manager.end_maintenance(schedule_id):
                print(f"✅ Maintenance {schedule_id} completed")
            else:
                print(f"❌ Failed to end maintenance {schedule_id}")
                
        elif command == "status":
            manager.show_maintenance_status()
            
        elif command == "check":
            manager.check_scheduled_maintenance()
            
        else:
            print("Usage: maintenance-mode-manager.py [schedule|start|end|status|check]")
    else:
        # Default: check for scheduled maintenance
        manager = MaintenanceModeManager()
        manager.check_scheduled_maintenance()

if __name__ == "__main__":
    main()