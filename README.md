# temp188

The server-side platform behind temp188.com and EnterTheConvo — a Flask application plus the operations tooling that keeps it running.

## What's here

- `app_unified.py` — the Flask application. Serves the dashboard, CSV search, image views, and login.
- `resume_marketplace.py` and `templates/resume_marketplace/` — profile setup, document and video upload.
- `templates/`, `static/` — Jinja templates and front-end assets.
- Operations scripts: `system-health-monitor.py`, `web-services-monitor.py`, `web-status-dashboard.py`, `intelligent-alerting.py`, `backup-recovery-system.py`, `maintenance-mode-manager.py`, `service-cli.py`.
- Analytics: `analytics-tracker.py`, `enhance-analytics-db.py`, `setup-analytics-tracking.sh`, and per-site tracking snippets.
- Security and infrastructure notes: nginx optimization, MinIO fixes, a server security scorecard, hardening recommendations.

## Related repositories

`wwwtemp188` contains a later revision of the same `app_unified.py` with a blueprint structure and Celery workers. `webtemp188` is empty. These three should be one repository.

## Status

Deployed and maintained by the operations scripts above rather than by frequent commits. `CLAUDE.md` documents the testing discipline used on the EnterTheConvo work.
