from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pulseiq",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scheduled-incremental-civic-ingestion": {
            "task": "app.workers.tasks.scheduled_incremental_ingestion",
            "schedule": 180.0,  # Every 3 minutes for live operational telemetry
        },
        "hourly-cluster-trend-refresh": {
            "task": "app.workers.tasks.recompute_clusters_and_trends",
            "schedule": crontab(minute=15),
        },
    },
)
