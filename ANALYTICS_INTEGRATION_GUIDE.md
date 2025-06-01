# Analytics Integration Guide

## 🎯 Overview

A lightweight, privacy-focused analytics system that tracks visitor counts across all monitored websites and displays the data in your existing dashboard at `conflost.com/monitor`.

## 🚀 Quick Setup

1. **Install the system**:
   ```bash
   sudo /root/setup-analytics-tracking.sh
   ```

2. **Add tracking pixels to each website** (see site-specific instructions below)

3. **View analytics** in your dashboard at `https://conflost.com/monitor`

## 📊 What It Tracks

- **Recent visitors** (last hour)
- **Daily visitors** (last 24 hours) 
- **Weekly visitors** (last 7 days)
- **Monthly visitors** (last 30 days)

## 🔒 Privacy Features

- No cookies or persistent tracking
- Filters out bots and crawlers
- 1x1 transparent pixel (invisible to users)
- Automatic cleanup of old data (90+ days)
- GDPR-friendly minimal data collection

## 📝 Integration Instructions by Site

### 🔬 Claude XML (claudexml.com)
Add to `/var/claudexml.com/templates/base.html` or main template:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=claudexml&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

### 🌡️ Temp188 (temp188.com)
Add to `/var/temp188.com/templates/base.html`:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=temp188&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

### 📱 Conflost (conflost.com)
Add to `/var/conflost.com/templates/base.html`:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=conflost&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

### 💬 EnterTheConvo (entertheconvo.com)
Add to `/var/entertheconvo.com/templates/index.html` and `/var/entertheconvo.com/entertheconvo-backend/public/index.html`:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=entertheconvo&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

### 🎮 Claude Play (claude-play.com)
Add to main HTML template:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=claude-play&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

### 🤖 AI Promptimizer (aipromptimizer.com)
Add to main HTML template:
```html
<!-- Add before closing </body> tag -->
<script>
(function() {
    var pixel = new Image(1, 1);
    pixel.src = 'https://conflost.com/analytics-pixel.gif?site=aipromptimizer&page=' + 
                encodeURIComponent(window.location.pathname) + '&t=' + Date.now();
    pixel.style.position = 'absolute';
    pixel.style.left = '-9999px';
    pixel.style.visibility = 'hidden';
    if (document.body) document.body.appendChild(pixel);
})();
</script>
```

## 🧪 Testing

1. **Test pixel endpoint**:
   ```bash
   curl -I https://conflost.com/analytics-pixel.gif?site=test
   ```

2. **Check analytics data**:
   ```bash
   curl http://localhost:8081/analytics/test
   ```

3. **View in dashboard**: Visit `https://conflost.com/monitor`

## 🔧 System Components

- **Analytics Tracker**: `/root/analytics-tracker.py` (port 8081)
- **Database**: `/var/log/site-analytics.db` (SQLite)
- **Logs**: `/var/log/analytics-tracker.log`
- **Dashboard Integration**: Updated `/root/web-status-dashboard.py`

## 📈 Dashboard Display

The monitoring dashboard now shows visitor counts for each service:
- Recent visitors (last hour)
- Daily visitors (last 24 hours) 
- Weekly visitors (last 7 days)

## 🛠️ Maintenance

- **View logs**: `tail -f /var/log/analytics-tracker.log`
- **Check database**: `sqlite3 /var/log/site-analytics.db "SELECT COUNT(*) FROM visits;"`
- **Restart tracker**: `pkill -f analytics-tracker.py && python3 /root/analytics-tracker.py &`

## 🔒 Security Notes

- Analytics tracker only listens on localhost (port 8081)
- Pixel endpoint exposed through nginx proxy
- No sensitive data collected (just timestamps, site names, basic request info)
- Automatic data cleanup after 90 days