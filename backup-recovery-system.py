#!/usr/bin/env python3
"""
Backup and Recovery Automation System
Automated backup and recovery for critical services and data
"""

import os
import sys
import json
import shutil
import tarfile
import sqlite3
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/backup-recovery.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BACKUP_CONFIG = {
    "backup_root": "/var/backups/services",
    "retention_days": 7,
    "critical_services": {
        "conflost": {
            "paths": ["/var/conflost.com"],
            "databases": [],
            "priority": "critical"
        },
        "temp188": {
            "paths": ["/var/temp188.com"],
            "databases": [],
            "priority": "critical"
        },
        "entertheconvo": {
            "paths": ["/var/entertheconvo.com/entertheconvo-backend"],
            "databases": ["/var/entertheconvo.com/entertheconvo-backend/entertheconvo.db"],
            "priority": "critical"
        },
        "claudexml": {
            "paths": ["/var/claudexml.com"],
            "databases": [],
            "priority": "medium"
        },
        "claude-play": {
            "paths": ["/var/claude-play.com"],
            "databases": [],
            "priority": "medium"
        }
    },
    "system_data": {
        "monitoring_db": "/var/log/service-monitoring.db",
        "analytics_db": "/var/log/site-analytics.db", 
        "system_health_db": "/var/log/system-health.db",
        "nginx_configs": "/etc/nginx",
        "ssl_certs": "/etc/letsencrypt"
    },
    "exclude_patterns": [
        "*.log",
        "*.tmp", 
        "__pycache__",
        ".git",
        "node_modules",
        "*.pyc"
    ]
}

class BackupRecoverySystem:
    def __init__(self):
        self.config = BACKUP_CONFIG
        self.backup_root = Path(self.config["backup_root"])
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.init_backup_database()
    
    def init_backup_database(self):
        """Initialize backup tracking database"""
        try:
            db_path = self.backup_root / "backup_history.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service_name TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    size_mb REAL,
                    duration_seconds INTEGER,
                    status TEXT,
                    error_message TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recovery_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service_name TEXT NOT NULL,
                    backup_timestamp TEXT NOT NULL,
                    recovery_path TEXT NOT NULL,
                    status TEXT,
                    error_message TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Backup database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize backup database: {e}")
    
    def log_backup_operation(self, service_name: str, backup_type: str, backup_path: str, 
                           size_mb: float, duration: int, status: str, error: str = None):
        """Log backup operation to database"""
        try:
            db_path = self.backup_root / "backup_history.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO backup_history 
                (service_name, backup_type, backup_path, size_mb, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (service_name, backup_type, backup_path, size_mb, duration, status, error))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log backup operation: {e}")
    
    def create_service_backup(self, service_name: str) -> bool:
        """Create backup for a specific service"""
        if service_name not in self.config["critical_services"]:
            logger.error(f"Service {service_name} not configured for backup")
            return False
        
        service_config = self.config["critical_services"][service_name]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"🔄 Creating backup for {service_name}")
        start_time = datetime.now()
        
        try:
            # Create service backup directory
            service_backup_dir = self.backup_root / service_name / timestamp
            service_backup_dir.mkdir(parents=True, exist_ok=True)
            
            total_size = 0
            
            # Backup service files
            for path_str in service_config["paths"]:
                path = Path(path_str)
                if not path.exists():
                    logger.warning(f"Path {path} does not exist, skipping")
                    continue
                
                backup_file = service_backup_dir / f"{path.name}_files.tar.gz"
                logger.info(f"  📁 Backing up {path} to {backup_file}")
                
                # Create tar archive with compression
                with tarfile.open(backup_file, "w:gz") as tar:
                    # Add exclude filter
                    def exclude_filter(tarinfo):
                        for pattern in self.config["exclude_patterns"]:
                            if pattern.replace("*", "") in tarinfo.name:
                                return None
                        return tarinfo
                    
                    tar.add(path, arcname=path.name, filter=exclude_filter)
                
                total_size += backup_file.stat().st_size / (1024 * 1024)  # MB
            
            # Backup databases
            for db_path_str in service_config.get("databases", []):
                db_path = Path(db_path_str)
                if not db_path.exists():
                    logger.warning(f"Database {db_path} does not exist, skipping")
                    continue
                
                backup_file = service_backup_dir / f"{db_path.name}"
                logger.info(f"  🗄️ Backing up database {db_path} to {backup_file}")
                
                # Copy database file
                shutil.copy2(db_path, backup_file)
                total_size += backup_file.stat().st_size / (1024 * 1024)  # MB
            
            # Create backup manifest
            manifest = {
                "service": service_name,
                "timestamp": timestamp,
                "paths_backed_up": service_config["paths"],
                "databases_backed_up": service_config.get("databases", []),
                "backup_size_mb": total_size,
                "created_at": datetime.now().isoformat()
            }
            
            manifest_file = service_backup_dir / "backup_manifest.json"
            with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            duration = int((datetime.now() - start_time).total_seconds())
            
            # Log successful backup
            self.log_backup_operation(service_name, "full", str(service_backup_dir), 
                                    total_size, duration, "success")
            
            logger.info(f"✅ Backup completed for {service_name}: {total_size:.1f}MB in {duration}s")
            return True
            
        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds())
            error_msg = str(e)
            
            # Log failed backup
            self.log_backup_operation(service_name, "full", str(service_backup_dir) if 'service_backup_dir' in locals() else "", 
                                    0, duration, "failed", error_msg)
            
            logger.error(f"❌ Backup failed for {service_name}: {e}")
            return False
    
    def create_system_backup(self) -> bool:
        """Create backup of system data (databases, configs, etc.)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info("🔄 Creating system data backup")
        start_time = datetime.now()
        
        try:
            # Create system backup directory
            system_backup_dir = self.backup_root / "system" / timestamp
            system_backup_dir.mkdir(parents=True, exist_ok=True)
            
            total_size = 0
            
            # Backup monitoring databases
            for db_name, db_path in self.config["system_data"].items():
                if db_name.endswith("_db"):
                    path = Path(db_path)
                    if path.exists():
                        backup_file = system_backup_dir / path.name
                        logger.info(f"  🗄️ Backing up {db_name}: {path}")
                        shutil.copy2(path, backup_file)
                        total_size += backup_file.stat().st_size / (1024 * 1024)
            
            # Backup nginx configuration
            nginx_path = Path(self.config["system_data"]["nginx_configs"])
            if nginx_path.exists():
                backup_file = system_backup_dir / "nginx_configs.tar.gz"
                logger.info(f"  ⚙️ Backing up nginx configs")
                with tarfile.open(backup_file, "w:gz") as tar:
                    tar.add(nginx_path, arcname="nginx")
                total_size += backup_file.stat().st_size / (1024 * 1024)
            
            # Backup SSL certificates (if exists)
            ssl_path = Path(self.config["system_data"]["ssl_certs"])
            if ssl_path.exists():
                backup_file = system_backup_dir / "ssl_certs.tar.gz"
                logger.info(f"  🔒 Backing up SSL certificates")
                with tarfile.open(backup_file, "w:gz") as tar:
                    tar.add(ssl_path, arcname="letsencrypt")
                total_size += backup_file.stat().st_size / (1024 * 1024)
            
            # Create system manifest
            manifest = {
                "type": "system_backup",
                "timestamp": timestamp,
                "components": list(self.config["system_data"].keys()),
                "backup_size_mb": total_size,
                "created_at": datetime.now().isoformat()
            }
            
            manifest_file = system_backup_dir / "system_manifest.json"
            with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            duration = int((datetime.now() - start_time).total_seconds())
            
            # Log successful backup
            self.log_backup_operation("system", "system", str(system_backup_dir), 
                                    total_size, duration, "success")
            
            logger.info(f"✅ System backup completed: {total_size:.1f}MB in {duration}s")
            return True
            
        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds())
            self.log_backup_operation("system", "system", "", 0, duration, "failed", str(e))
            
            logger.error(f"❌ System backup failed: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        logger.info("🧹 Cleaning up old backups")
        cutoff_date = datetime.now() - timedelta(days=self.config["retention_days"])
        
        cleaned_count = 0
        cleaned_size = 0
        
        for service_dir in self.backup_root.iterdir():
            if not service_dir.is_dir():
                continue
            
            for backup_dir in service_dir.iterdir():
                if not backup_dir.is_dir():
                    continue
                
                try:
                    # Parse timestamp from directory name
                    timestamp_str = backup_dir.name
                    backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if backup_date < cutoff_date:
                        # Calculate size before deletion
                        dir_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                        cleaned_size += dir_size / (1024 * 1024)  # MB
                        
                        # Remove old backup
                        shutil.rmtree(backup_dir)
                        cleaned_count += 1
                        logger.info(f"  🗑️ Removed old backup: {service_dir.name}/{timestamp_str}")
                        
                except (ValueError, OSError) as e:
                    logger.warning(f"Could not process backup directory {backup_dir}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"✅ Cleanup completed: Removed {cleaned_count} old backups ({cleaned_size:.1f}MB)")
        else:
            logger.info("✅ No old backups to clean up")
    
    def list_available_backups(self, service_name: str = None) -> List[Dict]:
        """List available backups for recovery"""
        backups = []
        
        search_dirs = [self.backup_root / service_name] if service_name else self.backup_root.iterdir()
        
        for service_dir in search_dirs:
            if not service_dir.is_dir():
                continue
                
            service = service_dir.name
            
            for backup_dir in service_dir.iterdir():
                if not backup_dir.is_dir():
                    continue
                
                try:
                    manifest_file = backup_dir / (f"{service}_manifest.json" if service != "system" else "system_manifest.json")
                    if not manifest_file.exists():
                        # Try alternative manifest names
                        manifest_file = backup_dir / "backup_manifest.json"
                    
                    if manifest_file.exists():
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                        
                        backups.append({
                            "service": service,
                            "timestamp": backup_dir.name,
                            "path": str(backup_dir),
                            "size_mb": manifest.get("backup_size_mb", 0),
                            "created_at": manifest.get("created_at"),
                            "type": manifest.get("type", "service")
                        })
                        
                except Exception as e:
                    logger.warning(f"Could not read backup manifest for {backup_dir}: {e}")
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def recover_service(self, service_name: str, backup_timestamp: str = None) -> bool:
        """Recover a service from backup"""
        if service_name not in self.config["critical_services"]:
            logger.error(f"Service {service_name} not configured for recovery")
            return False
        
        # Find backup to restore
        if backup_timestamp:
            backup_dir = self.backup_root / service_name / backup_timestamp
        else:
            # Use most recent backup
            backups = self.list_available_backups(service_name)
            if not backups:
                logger.error(f"No backups found for {service_name}")
                return False
            backup_dir = Path(backups[0]["path"])
            backup_timestamp = backups[0]["timestamp"]
        
        if not backup_dir.exists():
            logger.error(f"Backup directory {backup_dir} does not exist")
            return False
        
        logger.info(f"🔄 Starting recovery for {service_name} from {backup_timestamp}")
        
        try:
            service_config = self.config["critical_services"][service_name]
            
            # Stop service before recovery
            logger.info(f"  🛑 Stopping {service_name} service")
            subprocess.run(["python3", "/root/service-cli.py", "stop", service_name], 
                          capture_output=True, check=False)
            
            # Restore files
            for path_str in service_config["paths"]:
                path = Path(path_str)
                backup_file = backup_dir / f"{path.name}_files.tar.gz"
                
                if backup_file.exists():
                    logger.info(f"  📁 Restoring {path} from {backup_file}")
                    
                    # Create backup of current state
                    if path.exists():
                        backup_current = path.parent / f"{path.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.move(path, backup_current)
                        logger.info(f"    💾 Current state backed up to {backup_current}")
                    
                    # Extract backup
                    with tarfile.open(backup_file, "r:gz") as tar:
                        tar.extractall(path.parent)
                        
            # Restore databases
            for db_path_str in service_config.get("databases", []):
                db_path = Path(db_path_str)
                backup_file = backup_dir / db_path.name
                
                if backup_file.exists():
                    logger.info(f"  🗄️ Restoring database {db_path}")
                    
                    # Backup current database
                    if db_path.exists():
                        backup_current = db_path.parent / f"{db_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db_path.suffix}"
                        shutil.copy2(db_path, backup_current)
                        logger.info(f"    💾 Current database backed up to {backup_current}")
                    
                    # Restore database
                    shutil.copy2(backup_file, db_path)
            
            # Start service after recovery
            logger.info(f"  🚀 Starting {service_name} service")
            result = subprocess.run(["python3", "/root/service-cli.py", "start", service_name], 
                                  capture_output=True, text=True)
            
            # Log recovery operation
            db_path = self.backup_root / "backup_history.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO recovery_history 
                (service_name, backup_timestamp, recovery_path, status)
                VALUES (?, ?, ?, ?)
            ''', (service_name, backup_timestamp, str(backup_dir), "success"))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Recovery completed for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Recovery failed for {service_name}: {e}")
            
            # Log failed recovery
            try:
                db_path = self.backup_root / "backup_history.db"
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO recovery_history 
                    (service_name, backup_timestamp, recovery_path, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (service_name, backup_timestamp, str(backup_dir), "failed", str(e)))
                conn.commit()
                conn.close()
            except:
                pass
            
            return False
    
    def backup_all_services(self) -> Dict[str, bool]:
        """Create backups for all configured services"""
        logger.info("🔄 Starting full backup of all services")
        results = {}
        
        # Backup each service
        for service_name in self.config["critical_services"]:
            results[service_name] = self.create_service_backup(service_name)
        
        # Backup system data
        results["system"] = self.create_system_backup()
        
        # Cleanup old backups
        self.cleanup_old_backups()
        
        # Summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        logger.info(f"📊 Backup Summary: {successful}/{total} successful")
        
        return results
    
    def show_backup_status(self):
        """Show current backup status and available backups"""
        print("💾 Backup & Recovery System Status")
        print("=" * 50)
        
        # Show available backups
        all_backups = self.list_available_backups()
        
        if not all_backups:
            print("No backups found")
            return
        
        print(f"Available Backups: {len(all_backups)}")
        print()
        
        # Group by service
        by_service = {}
        for backup in all_backups:
            service = backup["service"]
            if service not in by_service:
                by_service[service] = []
            by_service[service].append(backup)
        
        for service, backups in by_service.items():
            print(f"📦 {service.upper()}:")
            for backup in backups[:3]:  # Show last 3 backups
                age = datetime.now() - datetime.fromisoformat(backup["created_at"])
                age_str = f"{age.days}d" if age.days > 0 else f"{age.seconds//3600}h"
                print(f"  {backup['timestamp'][:8]} | {backup['size_mb']:6.1f}MB | {age_str} ago")
            
            if len(backups) > 3:
                print(f"  ... and {len(backups)-3} more")
            print()

def main():
    """Main CLI interface"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        backup_system = BackupRecoverySystem()
        
        if command == "backup":
            if len(sys.argv) > 2:
                service_name = sys.argv[2]
                if service_name == "all":
                    backup_system.backup_all_services()
                elif service_name == "system":
                    backup_system.create_system_backup()
                else:
                    backup_system.create_service_backup(service_name)
            else:
                backup_system.backup_all_services()
                
        elif command == "recover":
            if len(sys.argv) < 3:
                print("Usage: backup-recovery-system.py recover <service> [timestamp]")
                return
            
            service_name = sys.argv[2]
            timestamp = sys.argv[3] if len(sys.argv) > 3 else None
            backup_system.recover_service(service_name, timestamp)
            
        elif command == "list":
            service_name = sys.argv[2] if len(sys.argv) > 2 else None
            backups = backup_system.list_available_backups(service_name)
            
            for backup in backups:
                print(f"{backup['service']:15} | {backup['timestamp']} | {backup['size_mb']:6.1f}MB")
                
        elif command == "status":
            backup_system.show_backup_status()
            
        elif command == "cleanup":
            backup_system.cleanup_old_backups()
            
        else:
            print("Usage: backup-recovery-system.py [backup [service|all|system]|recover <service> [timestamp]|list [service]|status|cleanup]")
    else:
        # Default: create backup of all services
        backup_system = BackupRecoverySystem()
        backup_system.backup_all_services()

if __name__ == "__main__":
    main()