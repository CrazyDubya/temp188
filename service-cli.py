#!/usr/bin/env python3
"""
Service Management CLI
Provides command-line interface for managing web services
"""

import sys
import argparse
import json
import subprocess
import time
from datetime import datetime
import sqlite3

# Import existing monitoring functions
sys.path.append('/root')
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("web_services_monitor", "/root/web-services-monitor.py")
    monitor_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor_module)
    
    SERVICES_CONFIG = monitor_module.SERVICES_CONFIG
    MONITORING_DB = monitor_module.MONITORING_DB
    check_service_health = monitor_module.check_service_health
    start_service = monitor_module.start_service
    stop_service = monitor_module.stop_service
    enhanced_service_restart = monitor_module.enhanced_service_restart
    log_service_event = monitor_module.log_service_event
    get_service_failure_history = monitor_module.get_service_failure_history
except ImportError:
    # Fallback configuration if import fails
    SERVICES_CONFIG = {
        "claudexml": {"type": "flask", "port": 5007, "domain": "claudexml.com", "script": "app.py", "working_dir": "/var/claudexml.com"},
        "temp188": {"type": "flask", "port": 5000, "domain": "temp188.com", "script": "app.py", "working_dir": "/var/temp188.com"},
        "conflost": {"type": "flask", "port": 5006, "domain": "conflost.com", "script": "app.py", "working_dir": "/var/conflost.com"},
        "entertheconvo": {"type": "flask", "port": 8082, "domain": "entertheconvo.com", "script": "server.js", "working_dir": "/var/entertheconvo.com"},
        "claude-play": {"type": "node", "port": 3001, "domain": "claude-play.com", "script": "server.js", "working_dir": "/var/claude-play.com"},
        "aipromptimizer": {"type": "static", "port": 80, "domain": "aipromptimizer.com", "script": "nginx", "working_dir": "/var/aipromptimizer.com"}
    }
    MONITORING_DB = '/var/log/service-monitoring.db'
    
    def check_service_health(service_name, config):
        print(f"⚠️ Limited functionality - monitoring functions not available")
        return {"healthy": False, "port_listening": False, "process_running": False, "http_responding": False}

def list_services():
    """List all configured services with their status"""
    print("📋 Configured Services:")
    print("=" * 60)
    
    for service_name, config in SERVICES_CONFIG.items():
        health = check_service_health(service_name, config)
        status = "🟢 HEALTHY" if health['healthy'] else "🔴 UNHEALTHY"
        
        print(f"{service_name:15} | {status:12} | Port {config['port']:5} | {config['domain']}")
        
        if not health['healthy']:
            details = []
            if not health['port_listening']:
                details.append("Port not listening")
            if not health['process_running']:
                details.append("Process not running")
            if not health['http_responding']:
                details.append("HTTP not responding")
            
            print(f"{'':15}   Issues: {', '.join(details)}")
    
    print("=" * 60)

def service_status(service_name):
    """Show detailed status for a specific service"""
    if service_name not in SERVICES_CONFIG:
        print(f"❌ Service '{service_name}' not found")
        return False
    
    config = SERVICES_CONFIG[service_name]
    health = check_service_health(service_name, config)
    history = get_service_failure_history(service_name, hours=24)
    
    print(f"📊 Service Status: {service_name}")
    print("=" * 50)
    print(f"Domain: {config['domain']}")
    print(f"Port: {config['port']}")
    print(f"Type: {config['type']}")
    print(f"Script: {config['script']}")
    print(f"Working Dir: {config['working_dir']}")
    print()
    
    status = "🟢 HEALTHY" if health['healthy'] else "🔴 UNHEALTHY"
    print(f"Overall Status: {status}")
    print(f"Port Listening: {'✅' if health['port_listening'] else '❌'}")
    print(f"Process Running: {'✅' if health['process_running'] else '❌'}")
    print(f"HTTP Responding: {'✅' if health['http_responding'] else '❌'}")
    print(f"Last Checked: {health['timestamp']}")
    print()
    
    print("📈 Recent History (24h):")
    print(f"Failure Count: {history['failure_count']}")
    if history['first_failure']:
        print(f"First Failure: {history['first_failure']}")
    if history['last_failure']:
        print(f"Last Failure: {history['last_failure']}")
    
    return health['healthy']

def service_start(service_name):
    """Start a specific service"""
    if service_name not in SERVICES_CONFIG:
        print(f"❌ Service '{service_name}' not found")
        return False
    
    config = SERVICES_CONFIG[service_name]
    print(f"🚀 Starting {service_name}...")
    
    if start_service(service_name, config):
        # Verify startup
        time.sleep(3)
        health = check_service_health(service_name, config)
        
        if health['healthy']:
            print(f"✅ {service_name} started successfully")
            log_service_event(service_name, 'manual_start', 'Service manually started via CLI')
            return True
        else:
            print(f"⚠️ {service_name} started but health check failed")
            return False
    else:
        print(f"❌ Failed to start {service_name}")
        return False

def service_stop(service_name):
    """Stop a specific service"""
    if service_name not in SERVICES_CONFIG:
        print(f"❌ Service '{service_name}' not found")
        return False
    
    config = SERVICES_CONFIG[service_name]
    print(f"🛑 Stopping {service_name}...")
    
    if stop_service(service_name, config):
        print(f"✅ {service_name} stopped successfully")
        log_service_event(service_name, 'manual_stop', 'Service manually stopped via CLI')
        return True
    else:
        print(f"❌ Failed to stop {service_name}")
        return False

def service_restart(service_name, enhanced=True):
    """Restart a specific service"""
    if service_name not in SERVICES_CONFIG:
        print(f"❌ Service '{service_name}' not found")
        return False
    
    config = SERVICES_CONFIG[service_name]
    
    if enhanced:
        print(f"🔄 Enhanced restart for {service_name}...")
        if enhanced_service_restart(service_name, config):
            print(f"✅ {service_name} restarted successfully")
            log_service_event(service_name, 'manual_restart', 'Service manually restarted via CLI (enhanced)')
            return True
        else:
            print(f"❌ Enhanced restart failed for {service_name}")
            return False
    else:
        print(f"🔄 Basic restart for {service_name}...")
        service_stop(service_name)
        time.sleep(2)
        return service_start(service_name)

def service_logs(service_name, lines=50):
    """Show recent logs for a service"""
    if service_name not in SERVICES_CONFIG:
        print(f"❌ Service '{service_name}' not found")
        return
    
    log_file = f"/var/log/{service_name}.log"
    
    try:
        result = subprocess.run(['tail', f'-{lines}', log_file], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"📜 Recent logs for {service_name} (last {lines} lines):")
            print("=" * 60)
            print(result.stdout)
        else:
            print(f"❌ Could not read logs for {service_name}")
    except Exception as e:
        print(f"❌ Error reading logs: {e}")

def restart_all_services():
    """Restart all configured services"""
    print("🔄 Restarting all services...")
    
    results = {}
    for service_name in SERVICES_CONFIG.keys():
        print(f"\n🔄 Restarting {service_name}...")
        results[service_name] = service_restart(service_name)
    
    print("\n📊 Restart Summary:")
    print("=" * 40)
    
    success_count = 0
    for service_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{service_name:15} | {status}")
        if success:
            success_count += 1
    
    print("=" * 40)
    print(f"✅ {success_count}/{len(results)} services restarted successfully")

def system_status():
    """Show comprehensive system status"""
    print("🖥️ System Status Overview")
    print("=" * 60)
    
    # Service status summary
    healthy_count = 0
    total_count = len(SERVICES_CONFIG)
    
    for service_name, config in SERVICES_CONFIG.items():
        health = check_service_health(service_name, config)
        if health['healthy']:
            healthy_count += 1
    
    print(f"Services: {healthy_count}/{total_count} healthy")
    
    # Recent events summary
    try:
        conn = sqlite3.connect(MONITORING_DB)
        cursor = conn.cursor()
        
        # Count events in last 24 hours
        cursor.execute('''
            SELECT event_type, COUNT(*) 
            FROM service_events 
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY event_type
        ''')
        
        events = dict(cursor.fetchall())
        conn.close()
        
        print("\n📈 Recent Activity (24h):")
        for event_type, count in events.items():
            print(f"  {event_type}: {count}")
            
    except Exception as e:
        print(f"⚠️ Could not fetch event history: {e}")
    
    print("\n🔍 Individual Service Status:")
    list_services()

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Web Services Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all services')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show service status')
    status_parser.add_argument('service', nargs='?', help='Service name (optional)')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start a service')
    start_parser.add_argument('service', help='Service name')
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop a service')
    stop_parser.add_argument('service', help='Service name')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart a service')
    restart_parser.add_argument('service', help='Service name (or "all")')
    restart_parser.add_argument('--basic', action='store_true', help='Use basic restart instead of enhanced')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('service', help='Service name')
    logs_parser.add_argument('--lines', '-n', type=int, default=50, help='Number of lines to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute commands
    if args.command == 'list':
        list_services()
    
    elif args.command == 'status':
        if args.service:
            service_status(args.service)
        else:
            system_status()
    
    elif args.command == 'start':
        service_start(args.service)
    
    elif args.command == 'stop':
        service_stop(args.service)
    
    elif args.command == 'restart':
        if args.service == 'all':
            restart_all_services()
        else:
            service_restart(args.service, enhanced=not args.basic)
    
    elif args.command == 'logs':
        service_logs(args.service, args.lines)

if __name__ == '__main__':
    main()