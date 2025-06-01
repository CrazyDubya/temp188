#!/usr/bin/env python3
"""
Lightweight Analytics Tracker for Website Monitoring
Serves 1x1 pixel and records visitor statistics
"""

import os
import json
import sqlite3
import hashlib
import re
from datetime import datetime, timedelta
from flask import Flask, request, Response, jsonify
import logging
from urllib.parse import urlparse

app = Flask(__name__)

# Database setup
DB_PATH = '/var/log/site-analytics.db'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/analytics-tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def hash_ip(ip_address):
    """Create privacy-friendly hash of IP address"""
    if not ip_address:
        return None
    # Add salt and hash for privacy
    salt = "analytics_privacy_salt_2025"
    return hashlib.sha256(f"{ip_address}{salt}".encode()).hexdigest()[:16]

def detect_bot(user_agent):
    """Enhanced bot detection"""
    if not user_agent:
        return True
    
    user_agent_lower = user_agent.lower()
    
    # Common bot indicators
    bot_indicators = [
        'bot', 'crawler', 'spider', 'monitor', 'uptime', 'check', 'scan',
        'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider',
        'yandexbot', 'facebookexternalhit', 'twitterbot', 'linkedinbot',
        'whatsapp', 'telegram', 'discord', 'curl', 'wget', 'python',
        'requests', 'httpie', 'postman', 'insomnia', 'pingdom',
        'statuscake', 'newrelic', 'datadog', 'headless', 'phantom',
        'selenium', 'playwright', 'puppeteer'
    ]
    
    return any(indicator in user_agent_lower for indicator in bot_indicators)

def parse_user_agent(user_agent):
    """Simple user agent parsing for browser, OS, device type"""
    if not user_agent:
        return None, None, 'unknown'
    
    ua_lower = user_agent.lower()
    
    # Browser detection
    browser = 'unknown'
    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        browser = 'chrome'
    elif 'firefox' in ua_lower:
        browser = 'firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'safari'
    elif 'edg' in ua_lower:
        browser = 'edge'
    elif 'opera' in ua_lower:
        browser = 'opera'
    
    # OS detection
    os = 'unknown'
    if 'windows' in ua_lower:
        os = 'windows'
    elif 'mac os' in ua_lower or 'macos' in ua_lower:
        os = 'macos'
    elif 'linux' in ua_lower:
        os = 'linux'
    elif 'android' in ua_lower:
        os = 'android'
    elif 'ios' in ua_lower or 'iphone' in ua_lower or 'ipad' in ua_lower:
        os = 'ios'
    
    # Device type detection
    device_type = 'desktop'
    if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
        device_type = 'mobile'
    elif 'tablet' in ua_lower or 'ipad' in ua_lower:
        device_type = 'tablet'
    
    return browser, os, device_type

def extract_referrer_domain(referrer):
    """Extract domain from referrer URL"""
    if not referrer:
        return None
    
    try:
        parsed = urlparse(referrer)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain if domain else None
    except:
        return None

def get_country_from_ip(ip_address):
    """Basic country detection (placeholder for now)"""
    # This is a simplified version - in production you'd use a GeoIP service
    # For now, we'll return None and implement later if needed
    return None

def update_hourly_analytics(site, timestamp):
    """Update hourly analytics aggregation"""
    try:
        # Round to hour
        hour_timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO hourly_analytics (site, hour_timestamp, visit_count, unique_visitors)
            VALUES (?, ?, 1, 1)
            ON CONFLICT(site, hour_timestamp) 
            DO UPDATE SET 
                visit_count = visit_count + 1,
                unique_visitors = unique_visitors + 1
        ''', (site, hour_timestamp))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating hourly analytics: {e}")

def update_page_popularity(site, page_path):
    """Update page popularity tracking"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO page_popularity (site, page_path, visit_count, last_visited)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(site, page_path)
            DO UPDATE SET 
                visit_count = visit_count + 1,
                last_visited = CURRENT_TIMESTAMP
        ''', (site, page_path))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating page popularity: {e}")

def update_referrer_analytics(site, referrer_domain):
    """Update referrer domain analytics"""
    if not referrer_domain:
        return
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO referrer_analytics (site, referrer_domain, visit_count, last_seen)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(site, referrer_domain)
            DO UPDATE SET 
                visit_count = visit_count + 1,
                last_seen = CURRENT_TIMESTAMP
        ''', (site, referrer_domain))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating referrer analytics: {e}")

def update_geographic_analytics(site, country_code):
    """Update geographic analytics"""
    if not country_code:
        return
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO geographic_analytics (site, country_code, visit_count, last_seen)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(site, country_code)
            DO UPDATE SET 
                visit_count = visit_count + 1,
                last_seen = CURRENT_TIMESTAMP
        ''', (site, country_code))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating geographic analytics: {e}")

def init_database():
    """Initialize SQLite database for analytics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site VARCHAR(50) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(45),
            user_agent TEXT,
            referer TEXT,
            page_path TEXT
        )
    ''')
    
    # Create index for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_timestamp ON visits(site, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON visits(timestamp)')
    
    conn.commit()
    conn.close()

def cleanup_old_visits():
    """Remove visits older than 3 months to keep database lean"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=90)
        cursor.execute('DELETE FROM visits WHERE timestamp < ?', (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old visit records")
    except Exception as e:
        logger.error(f"Error cleaning up old visits: {e}")

@app.route('/pixel.gif')
@app.route('/analytics-pixel.gif')  # Support legacy endpoint from website templates
def tracking_pixel():
    """Serve 1x1 transparent GIF and record enhanced visit data"""
    try:
        # Get request details
        site = request.args.get('site', 'unknown')
        page = request.args.get('page', '/')
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        referer = request.headers.get('Referer', '')
        
        # Enhanced data processing
        is_bot = detect_bot(user_agent)
        ip_hash = hash_ip(ip_address)
        browser, os, device_type = parse_user_agent(user_agent)
        referrer_domain = extract_referrer_domain(referer)
        country_code = get_country_from_ip(ip_address)
        
        # Always serve pixel, but only record human visits
        if is_bot:
            logger.debug(f"Bot detected: {user_agent[:50]}...")
            return create_pixel_response()
        
        # Record enhanced visit data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO visits (
                site, ip_address, user_agent, referer, page_path,
                country_code, is_bot, referrer_domain, ip_hash,
                browser, os, device_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (site, ip_address, user_agent, referer, page, 
              country_code, is_bot, referrer_domain, ip_hash,
              browser, os, device_type))
        
        conn.commit()
        conn.close()
        
        # Update aggregated analytics
        current_time = datetime.now()
        update_hourly_analytics(site, current_time)
        update_page_popularity(site, page)
        update_referrer_analytics(site, referrer_domain)
        update_geographic_analytics(site, country_code)
        
        logger.info(f"Enhanced visit recorded: {site} from {ip_hash} ({browser}/{os}/{device_type})")
        
    except Exception as e:
        logger.error(f"Error recording enhanced visit: {e}")
    
    return create_pixel_response()

def create_pixel_response():
    """Create 1x1 transparent GIF response"""
    # 1x1 transparent GIF in base64
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x04\x01\x00\x3b'
    
    response = Response(pixel_data, mimetype='image/gif')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/analytics/<site>')
def get_analytics(site):
    """Get analytics data for a specific site"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Recent visitors (last hour)
        cursor.execute('''
            SELECT COUNT(*) FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-1 hour')
        ''', (site,))
        recent = cursor.fetchone()[0]
        
        # Hourly (last 24 hours)
        cursor.execute('''
            SELECT COUNT(*) FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-1 day')
        ''', (site,))
        hourly = cursor.fetchone()[0]
        
        # Daily (last 7 days)
        cursor.execute('''
            SELECT COUNT(*) FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-7 days')
        ''', (site,))
        daily = cursor.fetchone()[0]
        
        # Weekly (last 30 days)
        cursor.execute('''
            SELECT COUNT(*) FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-30 days')
        ''', (site,))
        weekly = cursor.fetchone()[0]
        
        # Monthly (last 90 days)
        cursor.execute('''
            SELECT COUNT(*) FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-90 days')
        ''', (site,))
        monthly = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'site': site,
            'recent': recent,      # Last hour
            'hourly': hourly,      # Last 24 hours
            'daily': daily,        # Last 7 days  
            'weekly': weekly,      # Last 30 days
            'monthly': monthly,    # Last 90 days
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting analytics for {site}: {e}")
        return jsonify({'error': 'Unable to retrieve analytics'}), 500

@app.route('/analytics')
def get_all_analytics():
    """Get analytics summary for all sites"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all sites
        cursor.execute('SELECT DISTINCT site FROM visits ORDER BY site')
        sites = [row[0] for row in cursor.fetchall()]
        
        analytics = {}
        
        for site in sites:
            # Get stats for each site
            cursor.execute('''
                SELECT 
                    COUNT(CASE WHEN timestamp > datetime('now', '-1 hour') THEN 1 END) as recent,
                    COUNT(CASE WHEN timestamp > datetime('now', '-1 day') THEN 1 END) as hourly,
                    COUNT(CASE WHEN timestamp > datetime('now', '-7 days') THEN 1 END) as daily,
                    COUNT(CASE WHEN timestamp > datetime('now', '-30 days') THEN 1 END) as weekly,
                    COUNT(CASE WHEN timestamp > datetime('now', '-90 days') THEN 1 END) as monthly
                FROM visits WHERE site = ?
            ''', (site,))
            
            stats = cursor.fetchone()
            analytics[site] = {
                'recent': stats[0],
                'hourly': stats[1], 
                'daily': stats[2],
                'weekly': stats[3],
                'monthly': stats[4]
            }
        
        conn.close()
        
        return jsonify({
            'analytics': analytics,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting all analytics: {e}")
        return jsonify({'error': 'Unable to retrieve analytics'}), 500

@app.route('/analytics/enhanced/<site>')
def get_enhanced_analytics(site):
    """Get enhanced analytics data for a specific site"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Browser breakdown
        cursor.execute('''
            SELECT browser, COUNT(*) as count
            FROM visits 
            WHERE site = ? AND browser IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY browser
            ORDER BY count DESC
        ''', (site,))
        browsers = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # OS breakdown
        cursor.execute('''
            SELECT os, COUNT(*) as count
            FROM visits 
            WHERE site = ? AND os IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY os
            ORDER BY count DESC
        ''', (site,))
        operating_systems = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Device types
        cursor.execute('''
            SELECT device_type, COUNT(*) as count
            FROM visits 
            WHERE site = ? AND device_type IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY device_type
            ORDER BY count DESC
        ''', (site,))
        devices = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Referrer domains
        cursor.execute('''
            SELECT referrer_domain, COUNT(*) as count
            FROM visits 
            WHERE site = ? AND referrer_domain IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY referrer_domain
            ORDER BY count DESC
            LIMIT 10
        ''', (site,))
        referrers = [{'domain': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Hourly traffic (last 24 hours)
        cursor.execute('''
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM visits 
            WHERE site = ? AND timestamp > datetime('now', '-1 day')
            GROUP BY hour
            ORDER BY hour
        ''', (site,))
        hourly_traffic = [{'hour': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'site': site,
            'browsers': browsers,
            'operating_systems': operating_systems,
            'devices': devices,
            'referrers': referrers,
            'hourly_traffic': hourly_traffic,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting enhanced analytics for {site}: {e}")
        return jsonify({'error': 'Unable to retrieve enhanced analytics'}), 500

@app.route('/analytics/summary')
def get_analytics_summary():
    """Get analytics summary across all sites"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total visitors by device type
        cursor.execute('''
            SELECT device_type, COUNT(*) as count
            FROM visits 
            WHERE device_type IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY device_type
            ORDER BY count DESC
        ''')
        total_devices = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Total visitors by browser
        cursor.execute('''
            SELECT browser, COUNT(*) as count
            FROM visits 
            WHERE browser IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY browser
            ORDER BY count DESC
            LIMIT 10
        ''')
        total_browsers = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Daily visitor trends (last 7 days)
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM visits 
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''')
        daily_trends = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Top referrer domains
        cursor.execute('''
            SELECT referrer_domain, COUNT(*) as count
            FROM visits 
            WHERE referrer_domain IS NOT NULL AND timestamp > datetime('now', '-7 days')
            GROUP BY referrer_domain
            ORDER BY count DESC
            LIMIT 10
        ''')
        top_referrers = [{'domain': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'total_browsers': total_browsers,
            'daily_trends': daily_trends,
            'top_referrers': top_referrers,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        return jsonify({'error': 'Unable to retrieve analytics summary'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Cleanup old visits on startup
    cleanup_old_visits()
    
    logger.info("Starting analytics tracker on port 8083")
    app.run(host='0.0.0.0', port=8083, debug=False)