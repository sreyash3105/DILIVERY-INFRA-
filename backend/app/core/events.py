import uuid
import logging
import time
from app.tasks.notifications import send_notification_task
from app.tasks.analytics import process_delivery_analytics_task

logger = logging.getLogger("EventDispatcher")

def dispatch_event(event_type: str, order_id: int, tenant_id: int):
    """
    Emits an event and queues corresponding background tasks via Celery.
    Asynchronous and non-blocking for FastAPI request handlers.
    """
    event_id = str(uuid.uuid4())
    logger.info(f"Dispatching event {event_type} (ID: {event_id}) for Order #{order_id}")
    
    now_ts = time.time()
    
    # 1. Trigger notification task (handles email, push, and websocket checks)
    send_notification_task.delay(
        event_id=event_id,
        event_type=event_type,
        order_id=order_id,
        tenant_id=tenant_id,
        pushed_at=now_ts
    )
    
    # 2. Trigger analytics processing when order is completed (delivered)
    if event_type == "DELIVERED":
        process_delivery_analytics_task.delay(order_id, pushed_at=now_ts)

