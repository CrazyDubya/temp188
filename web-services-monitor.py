#!/usr/bin/env python3
"""
Web Services Monitor and Auto-Restart Script
Monitors all web applications and services, auto-restarts failed ones
"""

import os
import sys
import json
import time
import subprocess
import requests
import logging
import sqlite3
import ssl
import socket
from datetime import datetime, timedelta
from pathlib import Path
import calendar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/web-services-monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Monitoring database
MONITORING_DB = '/var/log/service-monitoring.db'

def log_service_metric(service, response_time_ms, status_code, is_healthy, endpoint=None, error_message=None):
    """Log service performance metrics to database"""
    try:
        conn = sqlite3.connect(MONITORING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO service_metrics 
            (service, response_time_ms, status_code, is_healthy, endpoint, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (service, response_time_ms, status_code, is_healthy, endpoint, error_message))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log metric for {service}: {e}")

def log_service_event(service, event_type, details, previous_state=None, new_state=None):
    """Log service state change events"""
    try:
        conn = sqlite3.connect(MONITORING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO service_events 
            (service, event_type, details, previous_state, new_state)
            VALUES (?, ?, ?, ?, ?)
        ''', (service, event_type, details, previous_state, new_state))
        conn.commit()
        conn.close()
        logger.info(f"Event logged: {service} - {event_type}")
    except Exception as e:
        logger.error(f"Failed to log event for {service}: {e}")

def check_ssl_certificate(domain):
    """Check SSL certificate expiry for domain"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_remaining = (expiry_date - datetime.now()).days
                
                # Log SSL certificate info
                conn = sqlite3.connect(MONITORING_DB)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO ssl_certificates 
                    (service, domain, expiry_date, days_remaining, is_valid)
                    VALUES (?, ?, ?, ?, ?)
                ''', (domain.replace('.com', ''), domain, expiry_date.date(), days_remaining, days_remaining > 0))
                conn.commit()
                conn.close()
                
                return days_remaining, expiry_date
    except Exception as e:
        logger.error(f"SSL check failed for {domain}: {e}")
        return None, None

# Configuration for all web services
SERVICES_CONFIG = {
    "claudexml": {
        "type": "flask",
        "path": "/var/claudexml.com",
        "script": "app.py",
        "port": 5007,
        "url": "http://localhost:5007",
        "domain": "claudexml.com",
        "process_name": "python3",
        "working_dir": "/var/claudexml.com"
    },
    "temp188": {
        "type": "flask", 
        "path": "/var/temp188.com",
        "script": "app_unified.py",
        "port": 5000,
        "url": "http://localhost:5000",
        "domain": "temp188.com",
        "process_name": "python3",
        "working_dir": "/var/temp188.com"
    },
    "conflost": {
        "type": "flask",
        "path": "/var/conflost.com", 
        "script": "app.py",
        "port": 5006,
        "url": "http://localhost:5006",
        "domain": "conflost.com",
        "process_name": "python3",
        "working_dir": "/var/conflost.com"
    },
    "entertheconvo": {
        "type": "flask",
        "path": "/var/entertheconvo.com",
        "script": "app.py",
        "port": 8082,
        "url": "http://localhost:8082",
        "domain": "entertheconvo.com", 
        "process_name": "python3",
        "working_dir": "/var/entertheconvo.com"
    },
    "claude-play": {
        "type": "node",
        "path": "/var/claude-play.com",
        "script": "server.js", 
        "port": 3001,
        "url": "http://localhost:3001",
        "domain": "claude-play.com",
        "process_name": "node",
        "working_dir": "/var/claude-play.com"
    },
    "aipromptimizer": {
        "type": "static",  # This appears to be a static site
        "path": "/var/aipromptimizer.com",
        "script": "server.js",
        "port": 80,  # Served directly by nginx
        "url": "https://aipromptimizer.com",  # Check the actual domain
        "domain": "aipromptimizer.com",
        "process_name": "nginx", 
        "working_dir": "/var/aipromptimizer.com"
    }
}

# Monthly restart prompt configuration
RESTART_PROMPT_CONFIG = {
    "config_file": "/root/.monthly-restart-config.json",
    "show_for_days": 7,  # Show prompt for 7 days if no action taken
    "silence_until_next_month": True
}

def load_restart_config():
    """Load the monthly restart configuration"""
    config_file = RESTART_PROMPT_CONFIG["config_file"]
    default_config = {
        "last_prompt_shown": None,
        "delayed_until": None,
        "silenced_until": None,
        "first_login_this_month": None
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception:
            return default_config
    
    return default_config

def save_restart_config(config):
    """Save the monthly restart configuration"""
    config_file = RESTART_PROMPT_CONFIG["config_file"]
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save restart config: {e}")

def get_first_of_current_month():
    """Get the first day of the current month"""
    now = datetime.now()
    return datetime(now.year, now.month, 1)

def get_first_of_next_month():
    """Get the first day of next month"""
    now = datetime.now()
    if now.month == 12:
        return datetime(now.year + 1, 1, 1)
    else:
        return datetime(now.year, now.month + 1, 1)

def should_show_restart_prompt():
    """Determine if the monthly restart prompt should be shown"""
    config = load_restart_config()
    now = datetime.now()
    first_of_month = get_first_of_current_month()
    
    # Check if restart is delayed
    if config.get("delayed_until"):
        delayed_until = datetime.fromisoformat(config["delayed_until"])
        if now < delayed_until:
            return False, "delayed"
    
    # Check if silenced
    if config.get("silenced_until"):
        silenced_until = datetime.fromisoformat(config["silenced_until"])
        if now < silenced_until:
            return False, "silenced"
    
    # Check if this is first login this month
    if not config.get("first_login_this_month"):
        # First login this month - show prompt
        config["first_login_this_month"] = now.isoformat()
        config["last_prompt_shown"] = now.isoformat()
        save_restart_config(config)
        return True, "first_login"
    
    first_login = datetime.fromisoformat(config["first_login_this_month"])
    
    # If first login was in a previous month, reset for this month
    if first_login < first_of_month:
        config["first_login_this_month"] = now.isoformat()
        config["last_prompt_shown"] = now.isoformat()
        save_restart_config(config)
        return True, "new_month"
    
    # Check if we should continue showing for 7 days
    if config.get("last_prompt_shown"):
        last_shown = datetime.fromisoformat(config["last_prompt_shown"])
        days_since_shown = (now - last_shown).days
        
        if days_since_shown < RESTART_PROMPT_CONFIG["show_for_days"]:
            return True, "within_7_days"
        else:
            # 7 days passed with no action - silence until next month
            next_month = get_first_of_next_month()
            config["silenced_until"] = next_month.isoformat()
            save_restart_config(config)
            return False, "auto_silenced"
    
    return False, "no_action_needed"

def show_restart_prompt():
    """Show the monthly restart prompt to user"""
    print("\n" + "="*60)
    print("🔄 MONTHLY SERVICE RESTART REQUIRED")
    print("="*60)
    print("It's time for the monthly service maintenance restart.")
    print("This helps ensure optimal performance and clears any accumulated issues.")
    print()
    print("Available commands:")
    print("  web-restart now     - Restart all services immediately")
    print("  web-restart delay   - Delay restart for 30 days (until next month)")
    print()
    print("⚠️  If no action is taken within 7 days, this prompt will be")
    print("   silenced until the 1st of next month.")
    print("="*60)
    print()

def handle_restart_command():
    """Handle restart-related commands"""
    if len(sys.argv) < 2:
        return False
    
    if sys.argv[1] != "restart":
        return False
    
    if len(sys.argv) < 3:
        print("Usage: web-services-monitor.py restart [now|delay]")
        return True
    
    action = sys.argv[2]
    config = load_restart_config()
    
    if action == "now":
        print("🔄 Restarting all services...")
        restart_all_services()
        
        # Clear any delays/silence, reset for next month
        next_month = get_first_of_next_month()
        config["delayed_until"] = None
        config["silenced_until"] = None
        config["last_restart"] = datetime.now().isoformat()
        # Set first_login_this_month to next month so prompt won't show again this month
        config["first_login_this_month"] = next_month.isoformat()
        save_restart_config(config)
        print("✅ All services restarted successfully!")
        print("   Next restart prompt will appear on the 1st of next month.")
        
    elif action == "delay":
        # Delay until next month
        next_month = get_first_of_next_month()
        config["delayed_until"] = next_month.isoformat()
        config["silenced_until"] = None
        save_restart_config(config)
        print(f"⏰ Service restart delayed until {next_month.strftime('%B 1, %Y')}")
        print("   You will be prompted again on the 1st of next month.")
        
    else:
        print("Invalid action. Use 'now' or 'delay'")
        return True
    
    return True

def restart_all_services():
    """Restart all configured services"""
    logger.info("Starting monthly restart of all services")
    
    for service_name, config in SERVICES_CONFIG.items():
        logger.info(f"Restarting {service_name}")
        try:
            if start_service(service_name, config):
                logger.info(f"✅ Successfully restarted {service_name}")
            else:
                logger.error(f"❌ Failed to restart {service_name}")
        except Exception as e:
            logger.error(f"Error restarting {service_name}: {e}")
    
    logger.info("Monthly restart cycle completed")

def check_port_listening(port):
    """Check if a port is listening"""
    try:
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        return f":{port}" in result.stdout and "LISTEN" in result.stdout
    except Exception as e:
        logger.error(f"Error checking port {port}: {e}")
        return False

def check_process_running(service_name, config):
    """Check if the service process is running"""
    try:
        script_name = config['script']
        result = subprocess.run(['pgrep', '-f', script_name], capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except Exception as e:
        logger.error(f"Error checking process for {service_name}: {e}")
        return False

def check_http_response(url, timeout=10, service_name=None):
    """Check if service responds to HTTP requests and track metrics"""
    start_time = time.time()
    response_time_ms = None
    status_code = None
    is_healthy = False
    error_message = None
    
    try:
        response = requests.get(url, timeout=timeout)
        response_time_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code
        # Accept various response codes that indicate the service is running
        is_healthy = response.status_code in [200, 301, 302, 403, 404]  # Include 404 as valid
        
        # Log metrics to database
        if service_name:
            log_service_metric(service_name, response_time_ms, status_code, is_healthy, url)
            
        return is_healthy
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
        error_message = str(e)
        logger.debug(f"HTTP check failed for {url}: {e}")
        
        # Log failed attempt
        if service_name:
            log_service_metric(service_name, response_time_ms, status_code, False, url, error_message)
            
        return False

def install_dependencies(service_name, config):
    """Install required dependencies for a service"""
    working_dir = config['working_dir']
    service_type = config['type']
    
    try:
        if service_type == "flask":
            # Check for requirements.txt
            req_file = os.path.join(working_dir, "requirements.txt")
            if os.path.exists(req_file):
                logger.info(f"Installing Python dependencies for {service_name}")
                subprocess.run(['pip3', 'install', '-r', req_file], check=True)
            
            # Install common Flask dependencies
            common_packages = ['flask', 'flask-sqlalchemy', 'werkzeug']
            for package in common_packages:
                try:
                    subprocess.run(['pip3', 'install', package], check=True)
                except subprocess.CalledProcessError:
                    logger.warning(f"Failed to install {package}")
                    
        elif service_type == "node":
            # Check for package.json
            package_file = os.path.join(working_dir, "package.json")
            if os.path.exists(package_file):
                logger.info(f"Installing Node.js dependencies for {service_name}")
                subprocess.run(['npm', 'install'], cwd=working_dir, check=True)
                
    except Exception as e:
        logger.error(f"Error installing dependencies for {service_name}: {e}")

def start_service(service_name, config):
    """Start a web service"""
    working_dir = config['working_dir']
    script = config['script'] 
    service_type = config['type']
    
    try:
        # Ensure working directory exists
        if not os.path.exists(working_dir):
            logger.error(f"Working directory {working_dir} does not exist for {service_name}")
            return False
            
        # Install dependencies first
        install_dependencies(service_name, config)
        
        script_path = os.path.join(working_dir, script)
        if not os.path.exists(script_path):
            logger.error(f"Script {script_path} does not exist for {service_name}")
            return False
            
        # Kill any existing processes
        stop_service(service_name, config)
        time.sleep(2)
        
        # Start the service
        if service_type == "flask":
            cmd = ['python3', script_path]
        elif service_type == "node":
            cmd = ['node', script_path]
        else:
            logger.error(f"Unknown service type {service_type} for {service_name}")
            return False
            
        logger.info(f"Starting {service_name} with command: {' '.join(cmd)}")
        
        # Start process in background with proper logging
        log_file = f"/var/log/{service_name}.log"
        with open(log_file, 'a') as f:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            
        # Wait a moment and check if it started
        time.sleep(3)
        if check_port_listening(config['port']):
            logger.info(f"Successfully started {service_name} on port {config['port']}")
            return True
        else:
            logger.error(f"Failed to start {service_name} - port {config['port']} not listening")
            return False
            
    except Exception as e:
        logger.error(f"Error starting {service_name}: {e}")
        return False

def stop_service(service_name, config):
    """Stop a web service"""
    try:
        script_name = config['script']
        # Kill processes by script name
        subprocess.run(['pkill', '-f', script_name], capture_output=True)
        logger.info(f"Stopped {service_name}")
        return True
    except Exception as e:
        logger.error(f"Error stopping {service_name}: {e}")
        return False

def check_service_health(service_name, config):
    """Comprehensive health check for a service"""
    port = config['port']
    url = config['url']
    
    # Check 1: Port listening
    port_ok = check_port_listening(port)
    
    # Check 2: Process running
    process_ok = check_process_running(service_name, config)
    
    # Check 3: HTTP response
    http_ok = check_http_response(url, service_name=service_name)
    
    # Check SSL certificate if domain configured
    ssl_days_remaining = None
    if 'domain' in config:
        ssl_days_remaining, _ = check_ssl_certificate(config['domain'])
        if ssl_days_remaining is not None and ssl_days_remaining < 30:
            logger.warning(f"SSL certificate for {config['domain']} expires in {ssl_days_remaining} days")
    
    health_status = {
        'service': service_name,
        'port_listening': port_ok,
        'process_running': process_ok, 
        'http_responding': http_ok,
        'healthy': port_ok and process_ok and http_ok,
        'ssl_days_remaining': ssl_days_remaining,
        'timestamp': datetime.now().isoformat()
    }
    
    return health_status

def get_service_failure_history(service_name, hours=24):
    """Get recent failure history for a service"""
    try:
        conn = sqlite3.connect(MONITORING_DB)
        cursor = conn.cursor()
        since = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT COUNT(*) as failure_count, 
                   MIN(timestamp) as first_failure,
                   MAX(timestamp) as last_failure
            FROM service_events 
            WHERE service = ? AND event_type IN ('failure', 'restart_attempt') 
            AND timestamp > ?
        ''', (service_name, since.isoformat()))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'failure_count': result[0] if result else 0,
            'first_failure': result[1] if result else None,
            'last_failure': result[2] if result else None
        }
    except Exception as e:
        logger.error(f"Error getting failure history for {service_name}: {e}")
        return {'failure_count': 0, 'first_failure': None, 'last_failure': None}

def should_attempt_restart(service_name, config):
    """Determine if a service should be restarted based on failure history"""
    # Get recent failure history
    history = get_service_failure_history(service_name, hours=24)
    
    # Don't restart if too many recent failures (circuit breaker)
    max_failures_per_day = config.get('max_restart_attempts', 10)
    if history['failure_count'] >= max_failures_per_day:
        logger.warning(f"Service {service_name} has failed {history['failure_count']} times in 24h, skipping restart")
        return False, "too_many_failures"
    
    # Check if last failure was recent (avoid restart loops)
    if history['last_failure']:
        last_failure = datetime.fromisoformat(history['last_failure'])
        min_restart_interval = config.get('min_restart_interval_minutes', 5)
        if (datetime.now() - last_failure).seconds < min_restart_interval * 60:
            return False, "too_recent"
    
    return True, "ok"

def enhanced_service_restart(service_name, config):
    """Enhanced service restart with dependency checks and recovery verification"""
    logger.info(f"🔄 Enhanced restart sequence for {service_name}")
    
    # Step 1: Graceful shutdown
    if not stop_service(service_name, config):
        logger.warning(f"Graceful shutdown failed for {service_name}, forcing kill")
        subprocess.run(['pkill', '-9', '-f', config['script']], capture_output=True)
        time.sleep(2)
    
    # Step 2: Clean up resources
    if config.get('cleanup_command'):
        try:
            subprocess.run(config['cleanup_command'], shell=True, timeout=30)
        except Exception as e:
            logger.warning(f"Cleanup command failed for {service_name}: {e}")
    
    # Step 3: Check dependencies
    if config.get('check_dependencies', True):
        install_dependencies(service_name, config)
    
    # Step 4: Start service
    if start_service(service_name, config):
        # Step 5: Verify recovery with progressive checks
        for attempt in range(3):
            time.sleep(5 * (attempt + 1))  # Progressive delay: 5s, 10s, 15s
            health = check_service_health(service_name, config)
            
            if health['healthy']:
                log_service_event(service_name, 'restart_success', 
                                f"Service successfully restarted and verified healthy after {attempt + 1} attempts")
                logger.info(f"✅ {service_name} restart successful after {(attempt + 1) * 5}s")
                return True
            
            logger.info(f"🔍 Restart verification attempt {attempt + 1}/3 failed, retrying...")
        
        log_service_event(service_name, 'restart_failed', 
                         "Service restart completed but health verification failed")
        logger.error(f"❌ {service_name} restart failed - service not healthy after 30s")
        return False
    
    log_service_event(service_name, 'restart_failed', "Service failed to start")
    logger.error(f"❌ {service_name} restart failed - service did not start")
    return False

def monitor_services(restart_failed=True):
    """Enhanced monitoring with intelligent restart logic"""
    logger.info("🔍 Starting enhanced service monitoring cycle")
    
    # Load previous status for comparison
    status_file = "/var/log/web-services-status.json"
    previous_status = {}
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                previous_status = json.load(f)
        except:
            pass
    
    results = {}
    
    for service_name, config in SERVICES_CONFIG.items():
        logger.info(f"Checking {service_name}...")
        
        health = check_service_health(service_name, config)
        results[service_name] = health
        
        # Check for status changes and log events
        previous_health = previous_status.get(service_name, {}).get('healthy', None)
        current_health = health['healthy']
        
        if previous_health is not None and previous_health != current_health:
            if current_health:
                log_service_event(service_name, 'recovery', 'Service recovered and is now healthy', 
                                'unhealthy', 'healthy')
            else:
                log_service_event(service_name, 'failure', 'Service became unhealthy', 
                                'healthy', 'unhealthy')
        
        if health['healthy']:
            logger.info(f"✅ {service_name} is healthy")
        else:
            logger.warning(f"❌ {service_name} is unhealthy: {health}")
            
            if restart_failed:
                # Use intelligent restart logic
                should_restart, reason = should_attempt_restart(service_name, config)
                
                if should_restart:
                    logger.info(f"🔄 Attempting enhanced restart for {service_name}")
                    log_service_event(service_name, 'restart_attempt', f"Attempting enhanced restart for unhealthy service")
                    
                    if enhanced_service_restart(service_name, config):
                        # Update health status after successful restart
                        health = check_service_health(service_name, config)
                        results[service_name] = health
                        logger.info(f"✅ Enhanced restart successful for {service_name}")
                    else:
                        logger.error(f"❌ Enhanced restart failed for {service_name}")
                else:
                    logger.warning(f"⏭️ Skipping restart for {service_name}: {reason}")
                    log_service_event(service_name, 'restart_skipped', f"Restart skipped: {reason}")
                        
    # Check and send intelligent alerts
    try:
        sys.path.append('/root')
        from intelligent_alerting import IntelligentAlertManager
        alerter = IntelligentAlertManager()
        alerter.check_and_send_alerts()
    except Exception as e:
        logger.debug(f"Intelligent alerting failed: {e}")
                        
    # Save results to status file
    status_file = "/var/log/web-services-status.json"
    with open(status_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    return results

def setup_systemd_services():
    """Create systemd service files for web applications"""
    logger.info("Setting up systemd services...")
    
    for service_name, config in SERVICES_CONFIG.items():
        if config['type'] == 'flask':
            service_content = f"""[Unit]
Description={service_name.title()} Flask Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={config['working_dir']}
ExecStart=/usr/bin/python3 {config['script']}
Restart=always
RestartSec=3
Environment=PYTHONPATH={config['working_dir']}

[Install]
WantedBy=multi-user.target
"""
        else:  # node
            service_content = f"""[Unit]
Description={service_name.title()} Node.js Application  
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={config['working_dir']}
ExecStart=/usr/bin/node {config['script']}
Restart=always
RestartSec=3
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
"""
        
        service_file = f"/etc/systemd/system/{service_name}.service"
        try:
            with open(service_file, 'w') as f:
                f.write(service_content)
            logger.info(f"Created systemd service file for {service_name}")
        except Exception as e:
            logger.error(f"Failed to create service file for {service_name}: {e}")

def main():
    """Main function"""
    # Handle restart commands first
    if handle_restart_command():
        return
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "check":
            results = monitor_services(restart_failed=False)
            for service, health in results.items():
                status = "✅ HEALTHY" if health['healthy'] else "❌ UNHEALTHY"
                print(f"{service}: {status}")
                
        elif command == "restart-all":
            restart_all_services()
                
        elif command == "setup-systemd":
            setup_systemd_services()
            
        elif command.startswith("restart-"):
            service_name = command[8:]  # Remove "restart-" prefix
            if service_name in SERVICES_CONFIG:
                start_service(service_name, SERVICES_CONFIG[service_name])
            else:
                print(f"Unknown service: {service_name}")
                
        elif command == "install-deps":
            for service_name, config in SERVICES_CONFIG.items():
                install_dependencies(service_name, config)
        
        elif command == "prompt-check":
            # Check if monthly restart prompt should be shown
            should_show, reason = should_show_restart_prompt()
            if should_show:
                show_restart_prompt()
            else:
                print(f"No restart prompt needed (reason: {reason})")
                
        else:
            print("Usage: web-services-monitor.py [check|restart-all|restart-<service>|setup-systemd|install-deps|restart|prompt-check]")
    else:
        # Default: monitor and restart failed services
        monitor_services(restart_failed=True)

if __name__ == "__main__":
    main()