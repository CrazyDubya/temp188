#!/usr/bin/env python3
"""
Initialize monitoring database with enhanced schema
"""

import sqlite3
from datetime import datetime

DB_PATH = '/var/log/service-monitoring.db'

def init_monitoring_database():
    """Create comprehensive monitoring database schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Service metrics table - response times, status codes, health
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service VARCHAR(50) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            response_time_ms INTEGER,
            status_code INTEGER,
            is_healthy BOOLEAN,
            endpoint VARCHAR(200),
            error_message TEXT
        )
    ''')
    
    # Service events table - state changes, downtime, alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service VARCHAR(50) NOT NULL,
            event_type VARCHAR(20) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            previous_state VARCHAR(20),
            new_state VARCHAR(20)
        )
    ''')
    
    # SSL certificate tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ssl_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service VARCHAR(50) NOT NULL,
            domain VARCHAR(100) NOT NULL,
            expiry_date DATE,
            days_remaining INTEGER,
            last_checked DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_valid BOOLEAN
        )
    ''')
    
    # Alert history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service VARCHAR(50) NOT NULL,
            alert_type VARCHAR(30) NOT NULL,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            acknowledged BOOLEAN DEFAULT FALSE,
            resolved_at DATETIME
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_service_time ON service_metrics(service, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_service_time ON service_events(service, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ssl_service ON ssl_certificates(service)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_service_time ON alert_history(service, timestamp)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ Monitoring database initialized at {DB_PATH}")
    
    # Verify tables created
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"✅ Created tables: {', '.join(tables)}")

if __name__ == '__main__':
    init_monitoring_database()