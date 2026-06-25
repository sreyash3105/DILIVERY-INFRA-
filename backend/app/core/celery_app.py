import ssl
from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "delivery_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.notifications",
        "app.tasks.analytics"
    ]
)

# Apply SSL configuration if using secure Redis URL (rediss://)
if settings.REDIS_URL.startswith("rediss://"):
    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE}
    )

# Celery Configuration settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task acknowledgement tuning for crash recovery
    task_acks_late=True,
    worker_reject_on_worker_lost=True,
    
    # Task routing queues configuration
    task_routes={
        "app.tasks.notifications.*": {"queue": "notifications"},
        "app.tasks.analytics.*": {"queue": "analytics"},
    },
    
    # Celery Beat schedules
    beat_schedule={
        "hourly-tenant-usage-aggregation": {
            "task": "app.tasks.analytics.hourly_usage_aggregation_task",
            "schedule": 3600.0, # Every hour
        }
    }
)
