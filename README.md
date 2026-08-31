# temp188

The server-side platform behind temp188.com and EnterTheConvo — a Flask application plus operations tooling.

## What's here

- `app_unified.py` — the Flask application. Templates in `templates/` cover the dashboard, CSV search, image views and login.
- `resume_marketplace.py` with `templates/resume_marketplace/` — profile setup, document and video upload.
- Operations scripts — `system-health-monitor.py`, `web-services-monitor.py`, `web-status-dashboard.py`, `intelligent-alerting.py`, `backup-recovery-system.py`, `maintenance-mode-manager.py`, `service-cli.py`.
- Analytics — `analytics-tracker.py`, `enhance-analytics-db.py`, `setup-analytics-tracking.sh`, and per-site tracking snippets for temp188, conflost, entertheconvo, claudexml, claude-play and aipromptimizer.
- Infrastructure notes — nginx optimization, a MinIO security fix report, a server security scorecard, hardening recommendations.
- `src/voter_matcher.cpp` — unrelated to the rest of the tree.
- `CLAUDE.md` — testing discipline notes for the EnterTheConvo work, written against reward hacking in test suites.

## Related repositories

`wwwtemp188` contains another `app_unified.py` with a blueprint structure and Celery workers. `webtemp188` is empty. These three cover one product.
