# temp188

The server-side platform behind temp188.com and EnterTheConvo — a Flask application plus operations tooling.

## What's here

- `app_unified.py` — the Flask application. Templates in `templates/` cover the dashboard, CSV search, image views and login.
- `app/blueprints/resume_marketplace.py` with `templates/resume_marketplace/` — profile setup, document and video upload.
- `app/` — merged tree of the former `wwwtemp188` repository: the superset production Flask app with blueprint structure and Celery workers (that repo was archived after the merge). Run the app from inside `app/` so the `blueprints` package imports resolve.
- Operations scripts — `system-health-monitor.py`, `web-services-monitor.py`, `web-status-dashboard.py`, `intelligent-alerting.py`, `backup-recovery-system.py`, `maintenance-mode-manager.py`, `service-cli.py`.
- Analytics — `analytics-tracker.py`, `enhance-analytics-db.py`, `setup-analytics-tracking.sh`, and per-site tracking snippets for temp188, conflost, entertheconvo, claudexml, claude-play and aipromptimizer.
- Infrastructure notes — nginx optimization, a MinIO security fix report, a server security scorecard, hardening recommendations.
- `src/voter_matcher.cpp` — unrelated to the rest of the tree.
- `CLAUDE.md` — testing discipline notes for the EnterTheConvo work, written against reward hacking in test suites.

## Provenance (wave-4 merge, 2026-09-13)

| Source repo | Placed in | Original HEAD |
|---|---|---|
| CrazyDubya/temp188 | `/` (root) | `b4312cccd6646d75f6f1175a837543dee54b6a4a` |
| CrazyDubya/wwwtemp188 | `app/` | `d9b3496e4985913d6399e5c2f6b09d22cb8c74f9` |

Notes:

- `resume_marketplace.py` moved from the root to `app/blueprints/resume_marketplace.py` so that `app/app_unified.py`'s `from blueprints.resume_marketplace import resume_bp` import resolves.
- The blueprint modules `eternalvoice`, `video_chat`, `billing` and `turing_chat` are imported by `app/app_unified.py` but were present in neither source tree; they were not fabricated and remain missing.
- The `webtemp188` repository referenced in an earlier version of this section does not exist (404); that dangling reference has been removed.
