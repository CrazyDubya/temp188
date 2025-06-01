#!/usr/bin/env python3
"""
Enhance analytics database schema for advanced tracking
"""

import sqlite3
from datetime import datetime

ANALYTICS_DB = '/var/log/site-analytics.db'

def enhance_analytics_schema():
    """Add new columns and tables for enhanced analytics"""
    conn = sqlite3.connect(ANALYTICS_DB)
    cursor = conn.cursor()
    
    # Add new columns to existing visits table
    new_columns = [
        ('country_code', 'VARCHAR(2)'),
        ('is_bot', 'BOOLEAN DEFAULT FALSE'),
        ('referrer_domain', 'VARCHAR(100)'),
        ('ip_hash', 'VARCHAR(64)'),
        ('browser', 'VARCHAR(50)'),
        ('os', 'VARCHAR(50)'),
        ('device_type', 'VARCHAR(20)')
    ]
    
    for column_name, column_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE visits ADD COLUMN {column_name} {column_type}')
            print(f"✅ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"⚠️  Column {column_name} already exists")
            else:
                print(f"❌ Error adding {column_name}: {e}")
    
    # Create hourly analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hourly_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site VARCHAR(50) NOT NULL,
            hour_timestamp DATETIME NOT NULL,
            visit_count INTEGER DEFAULT 0,
            unique_visitors INTEGER DEFAULT 0,
            UNIQUE(site, hour_timestamp)
        )
    ''')
    print("✅ Created hourly_analytics table")
    
    # Create page popularity table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_popularity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site VARCHAR(50) NOT NULL,
            page_path VARCHAR(500) NOT NULL,
            visit_count INTEGER DEFAULT 1,
            last_visited DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(site, page_path)
        )
    ''')
    print("✅ Created page_popularity table")
    
    # Create referrer analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrer_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site VARCHAR(50) NOT NULL,
            referrer_domain VARCHAR(100) NOT NULL,
            visit_count INTEGER DEFAULT 1,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(site, referrer_domain)
        )
    ''')
    print("✅ Created referrer_analytics table")
    
    # Create geographic analytics table  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geographic_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site VARCHAR(50) NOT NULL,
            country_code VARCHAR(2) NOT NULL,
            visit_count INTEGER DEFAULT 1,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(site, country_code)
        )
    ''')
    print("✅ Created geographic_analytics table")
    
    # Create indexes for better performance
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_visits_is_bot ON visits(is_bot)',
        'CREATE INDEX IF NOT EXISTS idx_visits_country ON visits(country_code)',
        'CREATE INDEX IF NOT EXISTS idx_visits_referrer ON visits(referrer_domain)',
        'CREATE INDEX IF NOT EXISTS idx_hourly_site_hour ON hourly_analytics(site, hour_timestamp)',
        'CREATE INDEX IF NOT EXISTS idx_page_popularity_site ON page_popularity(site, visit_count DESC)',
        'CREATE INDEX IF NOT EXISTS idx_referrer_site ON referrer_analytics(site, visit_count DESC)',
        'CREATE INDEX IF NOT EXISTS idx_geo_site ON geographic_analytics(site, visit_count DESC)'
    ]
    
    for index_sql in indexes:
        cursor.execute(index_sql)
    
    print("✅ Created performance indexes")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Analytics database enhanced at {ANALYTICS_DB}")

if __name__ == '__main__':
    enhance_analytics_schema()