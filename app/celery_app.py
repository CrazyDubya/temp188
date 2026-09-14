"""
Celery Application Configuration for temp188.com
Handles async background tasks for Whisper STT processing
"""

from celery import Celery

# Initialize Celery with Redis broker and backend
celery_app = Celery(
    'temp188_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute max for any task
    task_soft_time_limit=240,  # 4 minute soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time on 2-core CPU
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory cleanup)
)

# Import tasks explicitly to ensure they're registered
from blueprints import tasks  # noqa: F401
