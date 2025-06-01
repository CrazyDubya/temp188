#!/usr/bin/env python3
"""
System Health Monitor
Tracks resource usage, system metrics, and overall health
"""

import os
import sys
import json
import psutil
import sqlite3
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/system-health-monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
HEALTH_CONFIG = {
    "database": "/var/log/system-health.db",
    "thresholds": {
        "cpu_warning": 80.0,      # CPU usage %
        "cpu_critical": 95.0,
        "memory_warning": 85.0,    # Memory usage %
        "memory_critical": 95.0,
        "disk_warning": 85.0,      # Disk usage %
        "disk_critical": 95.0,
        "load_warning": 4.0,       # Load average (1min)
        "load_critical": 8.0,
        "temp_warning": 70.0,      # Temperature °C
        "temp_critical": 85.0
    },
    "collection_interval": 60,    # seconds
    "retention_days": 30
}

class SystemHealthMonitor:
    def __init__(self):
        self.config = HEALTH_CONFIG
        self.db_path = self.config["database"]
        self.init_database()
    
    def init_database(self):
        """Initialize system health database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create system metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_percent REAL,
                    cpu_count INTEGER,
                    memory_total_gb REAL,
                    memory_used_gb REAL,
                    memory_percent REAL,
                    disk_total_gb REAL,
                    disk_used_gb REAL,
                    disk_percent REAL,
                    load_1min REAL,
                    load_5min REAL,
                    load_15min REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    uptime_seconds INTEGER,
                    process_count INTEGER,
                    temperature_celsius REAL
                )
            ''')
            
            # Create process metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS process_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service_name TEXT,
                    pid INTEGER,
                    cpu_percent REAL,
                    memory_mb REAL,
                    memory_percent REAL,
                    status TEXT,
                    threads INTEGER,
                    open_files INTEGER
                )
            ''')
            
            # Create health alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT,
                    metric_name TEXT,
                    current_value REAL,
                    threshold_value REAL,
                    severity TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("System health database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def get_cpu_info(self) -> Dict:
        """Get CPU information and usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg()
            
            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "load_1min": load_avg[0],
                "load_5min": load_avg[1],
                "load_15min": load_avg[2]
            }
        except Exception as e:
            logger.error(f"Error getting CPU info: {e}")
            return {}
    
    def get_memory_info(self) -> Dict:
        """Get memory information and usage"""
        try:
            memory = psutil.virtual_memory()
            
            return {
                "memory_total_gb": memory.total / (1024**3),
                "memory_used_gb": memory.used / (1024**3),
                "memory_percent": memory.percent
            }
        except Exception as e:
            logger.error(f"Error getting memory info: {e}")
            return {}
    
    def get_disk_info(self) -> Dict:
        """Get disk information and usage"""
        try:
            disk = psutil.disk_usage('/')
            
            return {
                "disk_total_gb": disk.total / (1024**3),
                "disk_used_gb": disk.used / (1024**3),
                "disk_percent": (disk.used / disk.total) * 100
            }
        except Exception as e:
            logger.error(f"Error getting disk info: {e}")
            return {}
    
    def get_network_info(self) -> Dict:
        """Get network statistics"""
        try:
            net_io = psutil.net_io_counters()
            
            return {
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv
            }
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return {}
    
    def get_system_info(self) -> Dict:
        """Get general system information"""
        try:
            uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
            process_count = len(psutil.pids())
            
            return {
                "uptime_seconds": int(uptime.total_seconds()),
                "process_count": process_count
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}
    
    def get_temperature_info(self) -> Dict:
        """Get system temperature (if available)"""
        try:
            # Try to get CPU temperature from thermal sensors
            result = subprocess.run(['sensors', '-u'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'temp1_input' in line or 'Core 0' in line:
                        temp_str = line.split(':')[-1].strip()
                        if temp_str:
                            try:
                                temp = float(temp_str)
                                return {"temperature_celsius": temp}
                            except ValueError:
                                pass
            
            # Fallback: try reading from thermal zone
            thermal_files = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp'
            ]
            
            for thermal_file in thermal_files:
                if os.path.exists(thermal_file):
                    with open(thermal_file, 'r') as f:
                        temp_millicelsius = int(f.read().strip())
                        temp_celsius = temp_millicelsius / 1000.0
                        return {"temperature_celsius": temp_celsius}
            
        except Exception as e:
            logger.debug(f"Could not get temperature info: {e}")
        
        return {"temperature_celsius": None}
    
    def get_service_processes(self) -> List[Dict]:
        """Get process information for monitored services"""
        service_processes = []
        service_keywords = [
            'app.py', 'server.js', 'app_unified.py', 
            'analytics-tracker.py', 'web-status-dashboard.py',
            'nginx', 'python3', 'node'
        ]
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'status', 'num_threads']):
                try:
                    proc_info = proc.info
                    cmdline = ' '.join(proc_info['cmdline'] or [])
                    
                    # Check if this process is related to our services
                    for keyword in service_keywords:
                        if keyword in cmdline.lower() or keyword in proc_info['name'].lower():
                            # Try to determine service name
                            service_name = "unknown"
                            if 'app.py' in cmdline and 'claudexml' in cmdline:
                                service_name = "claudexml"
                            elif 'app.py' in cmdline and 'temp188' in cmdline:
                                service_name = "temp188"
                            elif 'app.py' in cmdline and 'conflost' in cmdline:
                                service_name = "conflost"
                            elif 'app.py' in cmdline and 'entertheconvo' in cmdline:
                                service_name = "entertheconvo"
                            elif 'server.js' in cmdline and 'claude-play' in cmdline:
                                service_name = "claude-play"
                            elif 'analytics-tracker.py' in cmdline:
                                service_name = "analytics-tracker"
                            elif 'web-status-dashboard.py' in cmdline:
                                service_name = "dashboard"
                            elif 'nginx' in proc_info['name'].lower():
                                service_name = "nginx"
                            
                            # Get open file count safely
                            try:
                                open_files = proc.num_fds()
                            except (psutil.AccessDenied, AttributeError):
                                open_files = None
                            
                            service_processes.append({
                                "service_name": service_name,
                                "pid": proc_info['pid'],
                                "cpu_percent": proc_info['cpu_percent'] or 0.0,
                                "memory_mb": (proc_info['memory_info'].rss / 1024 / 1024) if proc_info['memory_info'] else 0.0,
                                "memory_percent": proc.memory_percent() if hasattr(proc, 'memory_percent') else 0.0,
                                "status": proc_info['status'],
                                "threads": proc_info['num_threads'] or 1,
                                "open_files": open_files
                            })
                            break
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            logger.error(f"Error getting service processes: {e}")
        
        return service_processes
    
    def check_thresholds(self, metrics: Dict) -> List[Dict]:
        """Check if any metrics exceed thresholds"""
        alerts = []
        thresholds = self.config["thresholds"]
        
        # CPU checks
        if metrics.get("cpu_percent"):
            if metrics["cpu_percent"] >= thresholds["cpu_critical"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "cpu_percent",
                    "current_value": metrics["cpu_percent"],
                    "threshold_value": thresholds["cpu_critical"],
                    "severity": "critical"
                })
            elif metrics["cpu_percent"] >= thresholds["cpu_warning"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "cpu_percent",
                    "current_value": metrics["cpu_percent"],
                    "threshold_value": thresholds["cpu_warning"],
                    "severity": "warning"
                })
        
        # Memory checks
        if metrics.get("memory_percent"):
            if metrics["memory_percent"] >= thresholds["memory_critical"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "memory_percent",
                    "current_value": metrics["memory_percent"],
                    "threshold_value": thresholds["memory_critical"],
                    "severity": "critical"
                })
            elif metrics["memory_percent"] >= thresholds["memory_warning"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "memory_percent",
                    "current_value": metrics["memory_percent"],
                    "threshold_value": thresholds["memory_warning"],
                    "severity": "warning"
                })
        
        # Disk checks
        if metrics.get("disk_percent"):
            if metrics["disk_percent"] >= thresholds["disk_critical"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "disk_percent",
                    "current_value": metrics["disk_percent"],
                    "threshold_value": thresholds["disk_critical"],
                    "severity": "critical"
                })
            elif metrics["disk_percent"] >= thresholds["disk_warning"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "disk_percent",
                    "current_value": metrics["disk_percent"],
                    "threshold_value": thresholds["disk_warning"],
                    "severity": "warning"
                })
        
        # Load average checks
        if metrics.get("load_1min"):
            if metrics["load_1min"] >= thresholds["load_critical"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "load_1min",
                    "current_value": metrics["load_1min"],
                    "threshold_value": thresholds["load_critical"],
                    "severity": "critical"
                })
            elif metrics["load_1min"] >= thresholds["load_warning"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "load_1min",
                    "current_value": metrics["load_1min"],
                    "threshold_value": thresholds["load_warning"],
                    "severity": "warning"
                })
        
        # Temperature checks
        if metrics.get("temperature_celsius") and metrics["temperature_celsius"] is not None:
            if metrics["temperature_celsius"] >= thresholds["temp_critical"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "temperature_celsius",
                    "current_value": metrics["temperature_celsius"],
                    "threshold_value": thresholds["temp_critical"],
                    "severity": "critical"
                })
            elif metrics["temperature_celsius"] >= thresholds["temp_warning"]:
                alerts.append({
                    "alert_type": "system_resource",
                    "metric_name": "temperature_celsius",
                    "current_value": metrics["temperature_celsius"],
                    "threshold_value": thresholds["temp_warning"],
                    "severity": "warning"
                })
        
        return alerts
    
    def log_system_metrics(self, metrics: Dict):
        """Log system metrics to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_metrics (
                    cpu_percent, cpu_count, memory_total_gb, memory_used_gb, memory_percent,
                    disk_total_gb, disk_used_gb, disk_percent, load_1min, load_5min, load_15min,
                    network_bytes_sent, network_bytes_recv, uptime_seconds, process_count, temperature_celsius
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.get("cpu_percent"),
                metrics.get("cpu_count"),
                metrics.get("memory_total_gb"),
                metrics.get("memory_used_gb"),
                metrics.get("memory_percent"),
                metrics.get("disk_total_gb"),
                metrics.get("disk_used_gb"),
                metrics.get("disk_percent"),
                metrics.get("load_1min"),
                metrics.get("load_5min"),
                metrics.get("load_15min"),
                metrics.get("network_bytes_sent"),
                metrics.get("network_bytes_recv"),
                metrics.get("uptime_seconds"),
                metrics.get("process_count"),
                metrics.get("temperature_celsius")
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log system metrics: {e}")
    
    def log_process_metrics(self, processes: List[Dict]):
        """Log process metrics to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for proc in processes:
                cursor.execute('''
                    INSERT INTO process_metrics (
                        service_name, pid, cpu_percent, memory_mb, memory_percent, 
                        status, threads, open_files
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    proc.get("service_name"),
                    proc.get("pid"),
                    proc.get("cpu_percent"),
                    proc.get("memory_mb"),
                    proc.get("memory_percent"),
                    proc.get("status"),
                    proc.get("threads"),
                    proc.get("open_files")
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log process metrics: {e}")
    
    def log_health_alerts(self, alerts: List[Dict]):
        """Log health alerts to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for alert in alerts:
                cursor.execute('''
                    INSERT INTO health_alerts (
                        alert_type, metric_name, current_value, threshold_value, severity
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    alert["alert_type"],
                    alert["metric_name"],
                    alert["current_value"],
                    alert["threshold_value"],
                    alert["severity"]
                ))
                
                logger.warning(f"🚨 HEALTH ALERT: {alert['severity'].upper()} - {alert['metric_name']} = {alert['current_value']:.1f} (threshold: {alert['threshold_value']})")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log health alerts: {e}")
    
    def collect_system_health(self):
        """Main function to collect all system health metrics"""
        logger.info("🔍 Collecting system health metrics")
        
        # Collect all metrics
        metrics = {}
        metrics.update(self.get_cpu_info())
        metrics.update(self.get_memory_info())
        metrics.update(self.get_disk_info())
        metrics.update(self.get_network_info())
        metrics.update(self.get_system_info())
        metrics.update(self.get_temperature_info())
        
        # Get process information
        processes = self.get_service_processes()
        
        # Check thresholds and generate alerts
        alerts = self.check_thresholds(metrics)
        
        # Log everything
        self.log_system_metrics(metrics)
        self.log_process_metrics(processes)
        
        if alerts:
            self.log_health_alerts(alerts)
        
        # Print summary
        logger.info(f"💻 System Health Summary:")
        logger.info(f"   CPU: {metrics.get('cpu_percent', 0):.1f}% | Memory: {metrics.get('memory_percent', 0):.1f}% | Disk: {metrics.get('disk_percent', 0):.1f}%")
        logger.info(f"   Load: {metrics.get('load_1min', 0):.2f} | Processes: {metrics.get('process_count', 0)} | Uptime: {metrics.get('uptime_seconds', 0)//3600}h")
        if metrics.get('temperature_celsius'):
            logger.info(f"   Temperature: {metrics['temperature_celsius']:.1f}°C")
        logger.info(f"   Service Processes: {len(processes)} monitored")
        
        if alerts:
            logger.warning(f"⚠️ {len(alerts)} health alerts generated!")
        
        return metrics, processes, alerts
    
    def show_current_status(self):
        """Show current system health status"""
        metrics, processes, alerts = self.collect_system_health()
        
        print("🖥️ System Health Status")
        print("=" * 50)
        
        # System overview
        print(f"CPU Usage: {metrics.get('cpu_percent', 0):.1f}%")
        print(f"Memory Usage: {metrics.get('memory_percent', 0):.1f}% ({metrics.get('memory_used_gb', 0):.1f}GB / {metrics.get('memory_total_gb', 0):.1f}GB)")
        print(f"Disk Usage: {metrics.get('disk_percent', 0):.1f}% ({metrics.get('disk_used_gb', 0):.1f}GB / {metrics.get('disk_total_gb', 0):.1f}GB)")
        print(f"Load Average: {metrics.get('load_1min', 0):.2f} (1m), {metrics.get('load_5min', 0):.2f} (5m), {metrics.get('load_15min', 0):.2f} (15m)")
        
        if metrics.get('temperature_celsius'):
            print(f"Temperature: {metrics['temperature_celsius']:.1f}°C")
        
        uptime_hours = metrics.get('uptime_seconds', 0) // 3600
        uptime_days = uptime_hours // 24
        uptime_hours = uptime_hours % 24
        print(f"Uptime: {uptime_days}d {uptime_hours}h")
        print(f"Processes: {metrics.get('process_count', 0)}")
        
        # Process details
        print(f"\n📊 Service Processes ({len(processes)}):")
        for proc in processes:
            print(f"  {proc['service_name']:15} | PID {proc['pid']:6} | CPU {proc['cpu_percent']:5.1f}% | Memory {proc['memory_mb']:6.1f}MB | {proc['status']}")
        
        # Alerts
        if alerts:
            print(f"\n🚨 Active Alerts ({len(alerts)}):")
            for alert in alerts:
                print(f"  {alert['severity'].upper():8} | {alert['metric_name']:15} | {alert['current_value']:.1f} (threshold: {alert['threshold_value']})")
        else:
            print("\n✅ No active health alerts")

def main():
    """Main CLI interface"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        monitor = SystemHealthMonitor()
        
        if command == "collect":
            monitor.collect_system_health()
        elif command == "status":
            monitor.show_current_status()
        else:
            print("Usage: system-health-monitor.py [collect|status]")
    else:
        # Default: collect metrics
        monitor = SystemHealthMonitor()
        monitor.collect_system_health()

if __name__ == "__main__":
    main()