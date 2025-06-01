#!/bin/bash
# Setup Analytics Tracking System

echo "🔍 Setting up Analytics Tracking System..."

# Make analytics tracker executable
chmod +x /root/analytics-tracker.py

# Install Python dependencies if needed
pip3 install flask requests sqlite3 > /dev/null 2>&1 || echo "Dependencies already installed"

# Start analytics tracker as daemon
echo "📊 Starting analytics tracker on port 8081..."
nohup python3 /root/analytics-tracker.py > /var/log/analytics-tracker-startup.log 2>&1 &
ANALYTICS_PID=$!

# Wait a moment for it to start
sleep 2

# Check if it's running
if lsof -i :8081 > /dev/null; then
    echo "✅ Analytics tracker started successfully (PID: $ANALYTICS_PID)"
else
    echo "❌ Failed to start analytics tracker"
    exit 1
fi

# Add nginx route for analytics pixel
echo "🌐 Adding nginx route for analytics pixel..."

# Add analytics route to conflost nginx config
NGINX_CONFIG="/etc/nginx/sites-enabled/conflost.com"
ANALYTICS_ROUTE="    # Analytics Tracking Pixel
    location /analytics-pixel.gif {
        proxy_pass http://localhost:8081/pixel.gif;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Prevent caching
        add_header Cache-Control \"no-cache, no-store, must-revalidate\";
        add_header Pragma \"no-cache\";
        add_header Expires \"0\";
    }"

# Check if route already exists
if grep -q "analytics-pixel.gif" "$NGINX_CONFIG"; then
    echo "⚠️  Analytics route already exists in nginx config"
else
    # Add route before the # Web Services Monitoring Dashboard section
    sed -i '/# Web Services Monitoring Dashboard/i\\n'"$ANALYTICS_ROUTE"'\n' "$NGINX_CONFIG"
    echo "✅ Added analytics route to nginx config"
fi

# Test nginx configuration
if nginx -t > /dev/null 2>&1; then
    echo "✅ Nginx configuration test passed"
    systemctl reload nginx
    echo "✅ Nginx reloaded"
else
    echo "❌ Nginx configuration test failed"
    exit 1
fi

# Create tracking pixel snippets for each site
echo "📝 Creating tracking pixel snippets for each site..."

SITES=("claudexml" "temp188" "conflost" "entertheconvo" "claude-play" "aipromptimizer")

for site in "${SITES[@]}"; do
    SNIPPET_FILE="/root/tracking-snippet-${site}.html"
    sed "s/SITE_NAME_PLACEHOLDER/${site}/g" /root/tracking-pixel-snippet.html > "$SNIPPET_FILE"
    echo "  📄 Created snippet: $SNIPPET_FILE"
done

echo ""
echo "🎉 Analytics tracking system setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Add tracking snippets to each website"
echo "2. Test tracking: curl https://conflost.com/analytics-pixel.gif?site=test"
echo "3. View analytics in dashboard: https://conflost.com/monitor"
echo ""
echo "📁 Files created:"
echo "  • /root/analytics-tracker.py (tracking server)"
echo "  • /root/tracking-snippet-*.html (pixel snippets for each site)"
echo "  • /var/log/site-analytics.db (analytics database)"
echo ""
echo "🔧 Service status:"
echo "  • Analytics tracker: http://localhost:8081"
echo "  • Pixel endpoint: https://conflost.com/analytics-pixel.gif"
echo "  • Analytics API: http://localhost:8081/analytics"