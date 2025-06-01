#!/usr/bin/env python3
"""
Web Services Status Dashboard
Provides a simple HTML dashboard showing status of all web services
"""

import json
import os
import logging
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from functools import wraps

app = Flask(__name__)
app.secret_key = 'dashboard_security_key_2025'  # Change this in production

# Setup access logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/dashboard-access.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DASHBOARD_PASSCODE = "0219"

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Log access attempt
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        logger.info(f"Dashboard access attempt from {client_ip} - User-Agent: {user_agent}")
        
        if 'authenticated' not in session:
            logger.warning(f"Unauthorized access attempt from {client_ip}")
            return redirect('/monitor/login')
        return f(*args, **kwargs)
    return decorated_function

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Access</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #f5f5f5; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            max-width: 400px;
            width: 100%;
        }
        .login-title {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        .submit-btn {
            width: 100%;
            background: #007bff;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
        }
        .submit-btn:hover {
            background: #0056b3;
        }
        .error {
            color: #dc3545;
            text-align: center;
            margin-top: 10px;
        }
        .security-note {
            font-size: 0.9em;
            color: #666;
            text-align: center;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2 class="login-title">🔒 Monitoring Dashboard</h2>
        <form method="POST">
            <div class="form-group">
                <label for="passcode">Access Code:</label>
                <input type="password" id="passcode" name="passcode" required>
            </div>
            <button type="submit" class="submit-btn">Access Dashboard</button>
        </form>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <div class="security-note">
            🛡️ Access is logged for security monitoring
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Web Services Status Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .services-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .service-card { 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            border-left: 4px solid #ddd;
        }
        .service-card.healthy { border-left-color: #28a745; }
        .service-card.unhealthy { border-left-color: #dc3545; }
        .service-name { font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }
        .service-status { margin-bottom: 15px; }
        .status-healthy { color: #28a745; font-weight: bold; }
        .status-unhealthy { color: #dc3545; font-weight: bold; }
        .service-details { font-size: 0.9em; color: #666; }
        .service-details div { margin: 5px 0; }
        .check-item { padding: 2px 0; }
        .check-ok { color: #28a745; }
        .check-fail { color: #dc3545; }
        .timestamp { font-size: 0.8em; color: #999; margin-top: 10px; }
        .summary { 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 20px;
            text-align: center;
        }
        .refresh-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px;
        }
        .actions {
            text-align: center;
            margin: 20px 0;
        }
        .nav-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #dee2e6;
        }
        .nav-tab {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-bottom: none;
            padding: 10px 20px;
            margin: 0 5px;
            cursor: pointer;
            text-decoration: none;
            color: #495057;
        }
        .nav-tab.active {
            background: white;
            color: #007bff;
            font-weight: bold;
        }
        .nav-tab:hover {
            background: #e9ecef;
            text-decoration: none;
            color: #007bff;
        }
    </style>
    <script>
        function refreshPage() {
            location.reload();
        }
        // Auto-refresh every 30 seconds
        setTimeout(refreshPage, 30000);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ Web Services Status Dashboard</h1>
            <p>Real-time monitoring of all web applications</p>
        </div>
        
        <div class="nav-tabs">
            <a href="/monitor" class="nav-tab active">Status</a>
            <a href="/monitor/charts" class="nav-tab">Charts</a>
        </div>
        
        <div class="summary">
            <h3>System Overview</h3>
            <p><strong>{{ healthy_count }}</strong> services healthy | <strong>{{ unhealthy_count }}</strong> services need attention</p>
            <p>Last updated: {{ last_update }}</p>
        </div>

        <div class="actions">
            <button class="refresh-btn" onclick="refreshPage()">🔄 Refresh Status</button>
            <button class="refresh-btn" onclick="location.href='/logout'" style="background: #dc3545;">🚪 Logout</button>
        </div>
        
        <div class="services-grid">
            {% for service_name, status in services.items() %}
            <div class="service-card {{ 'healthy' if status.healthy else 'unhealthy' }}">
                <div class="service-name">{{ service_name.title() }}</div>
                <div class="service-status">
                    {% if status.healthy %}
                        <span class="status-healthy">✅ HEALTHY</span>
                    {% else %}
                        <span class="status-unhealthy">❌ UNHEALTHY</span>
                    {% endif %}
                </div>
                
                <div class="service-details">
                    <div><strong>Port:</strong> {{ config[service_name].port if service_name in config else 'Unknown' }}</div>
                    <div><strong>Domain:</strong> {{ config[service_name].domain if service_name in config else 'Unknown' }}</div>
                    <div><strong>Type:</strong> {{ config[service_name].type if service_name in config else 'Unknown' }}</div>
                    
                    {% if service_name in analytics %}
                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                        <div><strong>Visitors:</strong></div>
                        <div style="font-size: 0.85em; color: #666;">
                            Recent: {{ analytics[service_name].recent }} | 
                            Daily: {{ analytics[service_name].daily }} | 
                            Weekly: {{ analytics[service_name].weekly }} | 
                            Monthly: {{ analytics[service_name].monthly }}
                        </div>
                    </div>
                    {% endif %}
                    
                    {% if service_name in monitoring.services %}
                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                        <div><strong>Performance:</strong></div>
                        <div style="font-size: 0.85em; color: #666;">
                            {% if monitoring.services[service_name].avg_response_time %}
                            Avg Response: {{ monitoring.services[service_name].avg_response_time }}ms | 
                            {% endif %}
                            {% if monitoring.services[service_name].ssl_days_remaining %}
                            SSL: {{ monitoring.services[service_name].ssl_days_remaining }} days
                            {% endif %}
                        </div>
                    </div>
                    {% endif %}
                    
                    <div style="margin-top: 10px;">
                        <div class="check-item">
                            Port Listening: 
                            <span class="{{ 'check-ok' if status.port_listening else 'check-fail' }}">
                                {{ '✓' if status.port_listening else '✗' }}
                            </span>
                        </div>
                        <div class="check-item">
                            Process Running: 
                            <span class="{{ 'check-ok' if status.process_running else 'check-fail' }}">
                                {{ '✓' if status.process_running else '✗' }}
                            </span>
                        </div>
                        <div class="check-item">
                            HTTP Responding: 
                            <span class="{{ 'check-ok' if status.http_responding else 'check-fail' }}">
                                {{ '✓' if status.http_responding else '✗' }}
                            </span>
                        </div>
                    </div>
                </div>
                
                <div class="timestamp">
                    Last checked: {{ status.timestamp }}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div style="text-align: center; margin-top: 30px; font-size: 0.9em; color: #666;">
            <p>This dashboard auto-refreshes every 30 seconds</p>
            <p>Monitoring system will automatically restart failed services</p>
        </div>
    </div>
</body>
</html>
"""

# Service configuration (same as monitor script)
SERVICES_CONFIG = {
    "claudexml": {"type": "flask", "port": 5007, "domain": "claudexml.com"},
    "temp188": {"type": "flask", "port": 5000, "domain": "temp188.com"}, 
    "conflost": {"type": "flask", "port": 5006, "domain": "conflost.com"},
    "entertheconvo": {"type": "flask", "port": 8082, "domain": "entertheconvo.com"},
    "claude-play": {"type": "node", "port": 3001, "domain": "claude-play.com"},
    "aipromptimizer": {"type": "static", "port": 80, "domain": "aipromptimizer.com"}
}

@app.route('/login', methods=['GET', 'POST'])
@app.route('/monitor/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        passcode = request.form.get('passcode')
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        if passcode == DASHBOARD_PASSCODE:
            session['authenticated'] = True
            logger.info(f"Successful login from {client_ip}")
            return redirect('/monitor/dashboard')  # Always redirect to /monitor after login
        else:
            logger.warning(f"Failed login attempt from {client_ip} - Wrong passcode")
            return render_template_string(LOGIN_HTML, error="Invalid access code")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@app.route('/monitor/logout')
def logout():
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    session.pop('authenticated', None)
    logger.info(f"User logged out from {client_ip}")
    return redirect('/monitor/login')  # Redirect to /monitor/login path directly

def get_analytics_data():
    """Fetch analytics data from analytics tracker"""
    try:
        response = requests.get('http://localhost:8083/analytics', timeout=2)
        if response.status_code == 200:
            analytics_data = response.json().get('analytics', {})
            logger.info(f"Analytics data fetched: {len(analytics_data)} sites tracked")
            return analytics_data
        else:
            logger.warning(f"Analytics tracker returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Could not fetch analytics: {e}")
    return {}

def get_enhanced_analytics_data():
    """Fetch enhanced analytics summary data"""
    try:
        response = requests.get('http://localhost:8083/analytics/summary', timeout=2)
        if response.status_code == 200:
            enhanced_data = response.json()
            logger.info(f"Enhanced analytics data fetched")
            return enhanced_data
        else:
            logger.warning(f"Enhanced analytics API returned status {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Could not fetch enhanced analytics: {e}")
        return {}

def get_monitoring_data():
    """Fetch enhanced monitoring data from monitoring database"""
    import sqlite3
    monitoring_db = '/var/log/service-monitoring.db'
    data = {}
    
    try:
        conn = sqlite3.connect(monitoring_db)
        cursor = conn.cursor()
        
        # Get latest metrics for each service
        cursor.execute('''
            SELECT service, 
                   AVG(response_time_ms) as avg_response_time,
                   MAX(timestamp) as last_check
            FROM service_metrics 
            WHERE timestamp > datetime('now', '-1 hour')
            GROUP BY service
        ''')
        
        for row in cursor.fetchall():
            service, avg_response, last_check = row
            data[service] = {
                'avg_response_time': int(avg_response) if avg_response else None,
                'last_check': last_check
            }
        
        # Get SSL certificate data
        cursor.execute('''
            SELECT service, days_remaining, last_checked
            FROM ssl_certificates
            WHERE last_checked = (
                SELECT MAX(last_checked) 
                FROM ssl_certificates s2 
                WHERE s2.service = ssl_certificates.service
            )
        ''')
        
        for row in cursor.fetchall():
            service, days_remaining, last_checked = row
            if service in data:
                data[service]['ssl_days_remaining'] = days_remaining
            else:
                data[service] = {'ssl_days_remaining': days_remaining}
        
        # Get recent events
        cursor.execute('''
            SELECT service, event_type, timestamp
            FROM service_events
            WHERE timestamp > datetime('now', '-24 hours')
            ORDER BY timestamp DESC
        ''')
        
        events = []
        for row in cursor.fetchall():
            service, event_type, timestamp = row
            events.append({'service': service, 'event_type': event_type, 'timestamp': timestamp})
        
        conn.close()
        
        return {'services': data, 'recent_events': events}
        
    except Exception as e:
        logger.error(f"Could not fetch monitoring data: {e}")
        return {'services': {}, 'recent_events': []}

@app.route('/monitor/charts')
@require_auth  
def charts():
    # Get analytics data
    analytics = get_analytics_data()
    enhanced_analytics = get_enhanced_analytics_data()
    logger.info(f"Charts page - Analytics data: {analytics}")
    logger.info(f"Charts page - Enhanced analytics: {enhanced_analytics}")
    
    # Read latest status from monitoring script
    status_file = "/var/log/web-services-status.json"
    
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            services = json.load(f)
    else:
        services = {name: {"healthy": False, "port_listening": False, "process_running": False, "http_responding": False, "timestamp": "Never"} for name in SERVICES_CONFIG.keys()}
    
    return render_template_string(CHARTS_HTML, services=services, analytics=analytics, enhanced_analytics=enhanced_analytics, config=SERVICES_CONFIG)

@app.route('/monitor/site/<site_name>')
@require_auth
def site_analytics(site_name):
    """Detailed analytics for a specific site"""
    if site_name not in SERVICES_CONFIG:
        return "Site not found", 404
    
    # Get site-specific enhanced analytics
    try:
        response = requests.get(f'http://localhost:8083/analytics/enhanced/{site_name}', timeout=2)
        if response.status_code == 200:
            site_data = response.json()
        else:
            site_data = {}
    except:
        site_data = {}
    
    # Get basic analytics
    analytics = get_analytics_data()
    site_analytics = analytics.get(site_name, {})
    
    return render_template_string(SITE_ANALYTICS_HTML, 
                                site_name=site_name, 
                                site_data=site_data, 
                                site_analytics=site_analytics,
                                config=SERVICES_CONFIG)

@app.route('/monitor/export/<format>')
@require_auth
def export_analytics(format):
    """Export analytics data in CSV or JSON format"""
    if format not in ['csv', 'json']:
        return "Invalid format", 400
    
    # Get all analytics data
    analytics = get_analytics_data()
    enhanced = get_enhanced_analytics_data()
    
    if format == 'json':
        export_data = {
            'analytics': analytics,
            'enhanced': enhanced,
            'export_time': datetime.now().isoformat()
        }
        response = app.response_class(
            response=json.dumps(export_data, indent=2),
            status=200,
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    
    elif format == 'csv':
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Site', 'Recent', 'Daily', 'Weekly', 'Monthly'])
        
        # Write data
        for site, data in analytics.items():
            writer.writerow([
                site,
                data.get('recent', 0),
                data.get('daily', 0),
                data.get('weekly', 0),
                data.get('monthly', 0)
            ])
        
        response = app.response_class(
            response=output.getvalue(),
            status=200,
            mimetype='text/csv'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response

@app.route('/')
@app.route('/monitor')
@app.route('/dashboard')
@app.route('/monitor/dashboard')
@require_auth
def dashboard():
    # Read latest status from monitoring script
    status_file = "/var/log/web-services-status.json"
    
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            services = json.load(f)
    else:
        # Default empty status
        services = {name: {"healthy": False, "port_listening": False, "process_running": False, "http_responding": False, "timestamp": "Never"} for name in SERVICES_CONFIG.keys()}
    
    # Get analytics data
    analytics = get_analytics_data()
    logger.info(f"Analytics data for template: {analytics}")
    
    # Get enhanced monitoring data
    monitoring_data = get_monitoring_data()
    logger.info(f"Monitoring data fetched: {len(monitoring_data)} services")
    
    # Calculate summary stats
    healthy_count = sum(1 for s in services.values() if s.get('healthy', False))
    unhealthy_count = len(services) - healthy_count
    
    # Get last update time
    if services:
        timestamps = [s.get('timestamp', '') for s in services.values()]
        last_update = max(timestamps) if timestamps else "Never"
    else:
        last_update = "Never"
    
    return render_template_string(
        DASHBOARD_HTML,
        services=services,
        config=SERVICES_CONFIG,
        analytics=analytics,
        monitoring=monitoring_data,
        healthy_count=healthy_count,
        unhealthy_count=unhealthy_count,
        last_update=last_update
    )

CHARTS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>📊 Advanced Analytics Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { 
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 20px;
        }
        .header { 
            text-align: center; 
            margin-bottom: 30px; 
            color: white;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .nav-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 50px;
            padding: 5px;
        }
        .nav-tab {
            background: transparent;
            border: none;
            padding: 12px 30px;
            margin: 0 5px;
            text-decoration: none;
            color: white;
            border-radius: 25px;
            transition: all 0.3s ease;
        }
        .nav-tab.active {
            background: white;
            color: #667eea;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .stat-icon {
            font-size: 2.5em;
            margin-bottom: 15px;
            color: #667eea;
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .chart-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .chart-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
        }
        .chart-grid-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 25px;
        }
        @media (max-width: 1200px) {
            .chart-grid-3 {
                grid-template-columns: 1fr 1fr;
            }
        }
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            .header h1 {
                font-size: 1.8em;
            }
            .header p {
                font-size: 0.9em;
            }
            .nav-tabs {
                flex-direction: column;
                padding: 10px;
            }
            .nav-tab {
                margin: 5px 0;
                text-align: center;
            }
            .stats-grid {
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }
            .stat-card {
                padding: 20px 15px;
            }
            .stat-icon {
                font-size: 2em;
            }
            .stat-number {
                font-size: 1.5em;
            }
            .chart-grid, .chart-grid-3 {
                grid-template-columns: 1fr;
                gap: 20px;
            }
            .chart-container {
                padding: 20px;
            }
            .chart-container h3 {
                font-size: 1.1em;
            }
        }
        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .stat-card {
                padding: 15px;
            }
            .chart-container {
                padding: 15px;
            }
        }
        .filter-panel {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
            justify-content: center;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 150px;
        }
        .filter-label {
            color: white;
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 0.9em;
        }
        .filter-select, .filter-input {
            background: white;
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.9em;
            color: #333;
            min-width: 120px;
        }
        .filter-button {
            background: white;
            color: #667eea;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .filter-button:hover {
            background: #f8f9fa;
            transform: translateY(-2px);
        }
        @media (max-width: 768px) {
            .filter-panel {
                flex-direction: column;
                padding: 15px;
            }
            .filter-group {
                width: 100%;
            }
            .filter-select, .filter-input {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Advanced Analytics Dashboard</h1>
            <p>Comprehensive insights into service performance and visitor behavior</p>
        </div>
        
        <div class="nav-tabs">
            <a href="/monitor" class="nav-tab">Status</a>
            <a href="/monitor/charts" class="nav-tab active">Analytics</a>
        </div>

        <!-- Advanced Filters Panel -->
        <div class="filter-panel">
            <div class="filter-group">
                <div class="filter-label"><i class="fas fa-calendar"></i> Time Range</div>
                <select class="filter-select" id="timeRange">
                    <option value="1h">Last Hour</option>
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d" selected>Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                    <option value="90d">Last 90 Days</option>
                </select>
            </div>
            <div class="filter-group">
                <div class="filter-label"><i class="fas fa-globe"></i> Website</div>
                <select class="filter-select" id="siteFilter">
                    <option value="all">All Sites</option>
                    <option value="conflost">conflost.com</option>
                    <option value="temp188">temp188.com</option>
                    <option value="claudexml">claudexml.com</option>
                    <option value="entertheconvo">entertheconvo.com</option>
                    <option value="claude-play">claude-play.com</option>
                    <option value="aipromptimizer">aipromptimizer.com</option>
                </select>
            </div>
            <div class="filter-group">
                <div class="filter-label"><i class="fas fa-mobile-alt"></i> Device Type</div>
                <select class="filter-select" id="deviceFilter">
                    <option value="all">All Devices</option>
                    <option value="mobile">Mobile</option>
                    <option value="desktop">Desktop</option>
                    <option value="tablet">Tablet</option>
                </select>
            </div>
            <div class="filter-group">
                <div class="filter-label"><i class="fas fa-filter"></i> Apply</div>
                <button class="filter-button" onclick="applyFilters()">
                    <i class="fas fa-search"></i> Update
                </button>
            </div>
            <div class="filter-group">
                <div class="filter-label"><i class="fas fa-download"></i> Export</div>
                <div style="display: flex; gap: 5px;">
                    <a href="/monitor/export/csv" class="filter-button" style="padding: 8px 12px; font-size: 0.8em; text-decoration: none;">
                        <i class="fas fa-file-csv"></i> CSV
                    </a>
                    <a href="/monitor/export/json" class="filter-button" style="padding: 8px 12px; font-size: 0.8em; text-decoration: none;">
                        <i class="fas fa-file-code"></i> JSON
                    </a>
                </div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-users"></i></div>
                <div class="stat-number" id="totalVisitors">0</div>
                <div class="stat-label">Total Visitors Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-mobile-alt"></i></div>
                <div class="stat-number" id="mobileVisitors">0</div>
                <div class="stat-label">Mobile Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-desktop"></i></div>
                <div class="stat-number" id="desktopVisitors">0</div>
                <div class="stat-label">Desktop Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-server"></i></div>
                <div class="stat-number" id="healthyServices">0</div>
                <div class="stat-label">Healthy Services</div>
            </div>
        </div>

        <div class="chart-grid-3">
            <div class="chart-container">
                <h3>Device Types</h3>
                <canvas id="deviceChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3>Browser Distribution</h3>
                <canvas id="browserChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3>Traffic Sources</h3>
                <canvas id="referrerChart"></canvas>
            </div>
        </div>

        <div class="chart-grid">
            <div class="chart-container">
                <h3>Service Uptime Status</h3>
                <canvas id="uptimeChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3>Recent Traffic by Service</h3>
                <canvas id="trafficChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        const services = {{ services|tojson }};
        const analytics = {{ analytics|tojson }};
        const enhanced = {{ enhanced_analytics|tojson }};
        
        document.getElementById("totalVisitors").textContent = 
            enhanced.daily_trends?.reduce((sum, day) => sum + day.count, 0) || 0;
        
        const mobileCount = enhanced.total_devices?.find(d => d.name === "mobile")?.count || 0;
        const desktopCount = enhanced.total_devices?.find(d => d.name === "desktop")?.count || 0;
        
        document.getElementById("mobileVisitors").textContent = mobileCount;
        document.getElementById("desktopVisitors").textContent = desktopCount;
        document.getElementById("healthyServices").textContent = 
            Object.values(services).filter(s => s.healthy).length;

        new Chart(document.getElementById("deviceChart"), {
            type: "doughnut",
            data: {
                labels: enhanced.total_devices?.map(d => d.name) || [],
                datasets: [{
                    data: enhanced.total_devices?.map(d => d.count) || [],
                    backgroundColor: ["#FF6B6B", "#4ECDC4", "#45B7D1"]
                }]
            }
        });

        new Chart(document.getElementById("browserChart"), {
            type: "bar",
            data: {
                labels: enhanced.total_browsers?.map(b => b.name) || [],
                datasets: [{
                    data: enhanced.total_browsers?.map(b => b.count) || [],
                    backgroundColor: "#667eea"
                }]
            }
        });

        new Chart(document.getElementById("referrerChart"), {
            type: "polarArea",
            data: {
                labels: enhanced.top_referrers?.map(r => r.domain) || [],
                datasets: [{
                    data: enhanced.top_referrers?.map(r => r.count) || [],
                    backgroundColor: ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"]
                }]
            }
        });

        new Chart(document.getElementById("uptimeChart"), {
            type: "bar",
            data: {
                labels: Object.keys(services),
                datasets: [{
                    data: Object.keys(services).map(name => services[name].healthy ? 100 : 0),
                    backgroundColor: Object.keys(services).map(name => services[name].healthy ? "#28a745" : "#dc3545")
                }]
            }
        });

        new Chart(document.getElementById("trafficChart"), {
            type: "line",
            data: {
                labels: Object.keys(analytics),
                datasets: [{
                    data: Object.keys(analytics).map(name => analytics[name].recent || 0),
                    borderColor: "#667eea",
                    backgroundColor: "rgba(102, 126, 234, 0.1)",
                    fill: true
                }]
            }
        });

        // Filter functionality
        function applyFilters() {
            const timeRange = document.getElementById('timeRange').value;
            const siteFilter = document.getElementById('siteFilter').value;
            const deviceFilter = document.getElementById('deviceFilter').value;
            
            // Build query parameters
            const params = new URLSearchParams();
            if (timeRange !== '7d') params.append('timeRange', timeRange);
            if (siteFilter !== 'all') params.append('site', siteFilter);
            if (deviceFilter !== 'all') params.append('device', deviceFilter);
            
            // Reload with filters
            const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
            window.location.href = newUrl;
        }

        // Parse URL parameters and set filter states
        function initializeFilters() {
            const urlParams = new URLSearchParams(window.location.search);
            
            if (urlParams.has('timeRange')) {
                document.getElementById('timeRange').value = urlParams.get('timeRange');
            }
            if (urlParams.has('site')) {
                document.getElementById('siteFilter').value = urlParams.get('site');
            }
            if (urlParams.has('device')) {
                document.getElementById('deviceFilter').value = urlParams.get('device');
            }
        }

        // Initialize filters on page load
        initializeFilters();

        // Auto-refresh with current filters
        setTimeout(() => window.location.reload(), 30000);
    </script>
</body>
</html>
"""

SITE_ANALYTICS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>📊 {{ site_name|title }} Analytics - Detailed View</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; color: white; }
        .nav-tabs {
            display: flex; justify-content: center; margin-bottom: 30px;
            background: rgba(255,255,255,0.1); border-radius: 50px; padding: 5px;
        }
        .nav-tab {
            background: transparent; border: none; padding: 12px 30px; margin: 0 5px;
            text-decoration: none; color: white; border-radius: 25px; transition: all 0.3s ease;
        }
        .nav-tab:hover { background: rgba(255,255,255,0.2); color: white; text-decoration: none; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .stat-icon { font-size: 2.5em; margin-bottom: 15px; color: #667eea; }
        .stat-number { font-size: 2em; font-weight: bold; color: #333; }
        .chart-container { background: white; padding: 30px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        .full-width { grid-column: 1 / -1; }
        .metric-list { list-style: none; padding: 0; }
        .metric-item { padding: 10px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
        @media (max-width: 768px) { .chart-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {{ site_name|title }}.com Analytics</h1>
            <p>Detailed insights for {{ config[site_name].domain if site_name in config else site_name }}</p>
        </div>
        
        <div class="nav-tabs">
            <a href="/monitor" class="nav-tab">Status</a>
            <a href="/monitor/charts" class="nav-tab">Overview</a>
            <a href="/monitor/site/{{ site_name }}" class="nav-tab" style="background: white; color: #667eea;">{{ site_name|title }}</a>
        </div>

        <!-- Site Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-eye"></i></div>
                <div class="stat-number">{{ site_analytics.recent or 0 }}</div>
                <div class="stat-label">Recent Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-calendar-day"></i></div>
                <div class="stat-number">{{ site_analytics.daily or 0 }}</div>
                <div class="stat-label">Daily Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-calendar-week"></i></div>
                <div class="stat-number">{{ site_analytics.weekly or 0 }}</div>
                <div class="stat-label">Weekly Visitors</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-calendar"></i></div>
                <div class="stat-number">{{ site_analytics.monthly or 0 }}</div>
                <div class="stat-label">Monthly Visitors</div>
            </div>
        </div>

        <!-- Detailed Charts -->
        <div class="chart-grid">
            <div class="chart-container">
                <h3><i class="fas fa-mobile-alt"></i> Device Breakdown</h3>
                <canvas id="siteDeviceChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3><i class="fas fa-browser"></i> Browser Usage</h3>
                <canvas id="siteBrowserChart"></canvas>
            </div>
        </div>

        <div class="chart-grid">
            <div class="chart-container">
                <h3><i class="fas fa-link"></i> Traffic Sources</h3>
                <canvas id="siteReferrerChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3><i class="fas fa-clock"></i> Hourly Traffic Pattern</h3>
                <canvas id="hourlyTrafficChart"></canvas>
            </div>
        </div>

        <!-- Data Tables -->
        <div class="chart-container full-width">
            <h3><i class="fas fa-list"></i> Detailed Metrics</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                <div>
                    <h4>Top Referrers</h4>
                    <ul class="metric-list">
                        {% for ref in site_data.referrers[:5] %}
                        <li class="metric-item">
                            <span>{{ ref.domain }}</span>
                            <strong>{{ ref.count }} visits</strong>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
                <div>
                    <h4>Browser Statistics</h4>
                    <ul class="metric-list">
                        {% for browser in site_data.browsers[:5] %}
                        <li class="metric-item">
                            <span>{{ browser.name|title }}</span>
                            <strong>{{ browser.count }} visits</strong>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <script>
        const siteData = {{ site_data|tojson }};
        
        // Site Device Chart
        if (siteData.devices && siteData.devices.length > 0) {
            new Chart(document.getElementById('siteDeviceChart'), {
                type: 'doughnut',
                data: {
                    labels: siteData.devices.map(d => d.name.charAt(0).toUpperCase() + d.name.slice(1)),
                    datasets: [{
                        data: siteData.devices.map(d => d.count),
                        backgroundColor: ['#FF6B6B', '#4ECDC4', '#45B7D1']
                    }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
            });
        }

        // Site Browser Chart
        if (siteData.browsers && siteData.browsers.length > 0) {
            new Chart(document.getElementById('siteBrowserChart'), {
                type: 'bar',
                data: {
                    labels: siteData.browsers.map(b => b.name.charAt(0).toUpperCase() + b.name.slice(1)),
                    datasets: [{
                        data: siteData.browsers.map(b => b.count),
                        backgroundColor: '#667eea'
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        }

        // Site Referrer Chart
        if (siteData.referrers && siteData.referrers.length > 0) {
            new Chart(document.getElementById('siteReferrerChart'), {
                type: 'polarArea',
                data: {
                    labels: siteData.referrers.map(r => r.domain),
                    datasets: [{
                        data: siteData.referrers.map(r => r.count),
                        backgroundColor: ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
                    }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
            });
        }

        // Hourly Traffic Chart
        if (siteData.hourly_traffic && siteData.hourly_traffic.length > 0) {
            new Chart(document.getElementById('hourlyTrafficChart'), {
                type: 'line',
                data: {
                    labels: siteData.hourly_traffic.map(h => h.hour + ':00'),
                    datasets: [{
                        label: 'Visitors',
                        data: siteData.hourly_traffic.map(h => h.count),
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: { 
                    responsive: true, 
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } }
                }
            });
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)