from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "booking",
    broker=settings.redis_url.get_secret_value(),
    backend=settings.redis_url.get_secret_value(),
    include=["app.tasks.holds", "app.tasks.notifications"],
)
celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "release-expired-holds": {
            "task": "booking.release_expired_holds",
            "schedule": 60.0,
        },
        "deliver-notifications": {
            "task": "booking.deliver_notifications",
            "schedule": 2.0,
        },
    },
)
