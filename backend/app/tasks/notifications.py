import asyncio
import logging
import json
import smtplib
from email.mime.text import MIMEText
from celery import shared_task
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.redis import redis_client
from app.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger("NotificationTask")

email_circuit_breaker = CircuitBreaker(name="EmailProvider", failure_threshold=3, recovery_timeout=15.0)
push_circuit_breaker = CircuitBreaker(name="PushProvider", failure_threshold=3, recovery_timeout=15.0)

def run_async(coro):
    """Run an async coroutine from a sync Celery task context.

    Uses asyncio.run() which creates a fresh event loop per call — the correct
    pattern for Celery workers where no event loop is running (Python 3.10+).
    """
    return asyncio.run(coro)

async def _db_log_notification(event_id: str, order_id: int, tenant_id: int, channel: str, event_type: str, status: str, error_message: str = None):
    """Inserts a notification record into the PostgreSQL database."""
    from app.db.session import AsyncSessionLocal
    from app.models.notification_log import NotificationLog, NotificationStatus
    
    async with AsyncSessionLocal() as db:
        log_entry = NotificationLog(
            event_id=event_id,
            order_id=order_id,
            tenant_id=tenant_id,
            channel=channel,
            event_type=event_type,
            status=NotificationStatus(status),
            error_message=error_message
        )
        db.add(log_entry)
        await db.commit()

async def _get_tenant_preferences(tenant_id: int):
    """Retrieves tenant's plan preferences from PostgreSQL database."""
    from app.db.session import AsyncSessionLocal
    from app.models.tenant import Tenant
    from sqlalchemy.future import select
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalars().first()
        if tenant:
            return tenant.notification_preferences
        return None

# SendGrid Mock Client / SMTP Mock Fallback
def _send_email_mock(to_address: str, subject: str, body: str):
    logger.info(f"[Email Notification] Sending mock email to {to_address}...")
    # Standard SendGrid API key check (e.g. if configured)
    sg_api_key = getattr(settings, 'SENDGRID_API_KEY', None)
    if sg_api_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            message = Mail(
                from_email='no-reply@dep-logix.com',
                to_emails=to_address,
                subject=subject,
                plain_text_content=body
            )
            sg = SendGridAPIClient(sg_api_key)
            sg.send(message)
            logger.info("[Email Notification] Successfully sent via SendGrid.")
            return True
        except Exception as e:
            logger.error(f"[Email Notification] SendGrid delivery failed: {e}. Falling back to SMTP...")
            
    # smtplib SMTP mock fallback
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'no-reply@dep-logix.com'
        msg['To'] = to_address
        
        # Connect to local smtp port for testing (using mock server or just log if offline)
        with smtplib.SMTP('localhost', 1025) as server:
            server.sendmail('no-reply@dep-logix.com', [to_address], msg.as_string())
        logger.info("[Email Notification] Successfully sent via local SMTP.")
        return True
    except Exception as smtp_err:
        logger.warning(f"[Email Notification] Local SMTP server not available ({smtp_err}). Mock logged successfully to console.")
        return True

# FCM Mock Client / Push
def _send_push_mock(token: str, title: str, body: str):
    logger.info(f"[Push Notification] Sending mock push to FCM Token {token}: {title} - {body}")
    # Firebase SDK integration logic placeholder
    firebase_cred = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
    if firebase_cred:
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(firebase_cred)
                firebase_admin.initialize_app(cred)
                
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=token,
            )
            messaging.send(message)
            logger.info("[Push Notification] Successfully sent via Firebase Cloud Messaging.")
            return True
        except Exception as e:
            logger.error(f"[Push Notification] Firebase FCM delivery failed: {e}.")
            return False
    return True

@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True, queue="notifications")
def send_notification_task(self, event_id: str, event_type: str, order_id: int, tenant_id: int, pushed_at: float = None):
    """
    Asynchronously processes notification triggers across channel streams (WebSockets, Push, Email).
    Implements Redis-based idempotency checks and audit log bookkeeping.
    """
    logger.info(f"Processing notification event {event_type} (ID: {event_id}) for Order #{order_id}, pushed_at={pushed_at}")
    
    # 1. Fetch preferences
    preferences = run_async(_get_tenant_preferences(tenant_id))
    if not preferences:
        preferences = {
            "ASSIGNED": ["WEBSOCKET", "PUSH"],
            "PICKED_UP": ["WEBSOCKET", "PUSH"],
            "NEAR_DELIVERY": ["PUSH"],
            "DELIVERED": ["WEBSOCKET", "PUSH", "EMAIL"]
        }
        
    enabled_channels = preferences.get(event_type, [])
    if not enabled_channels:
        logger.info(f"No enabled channels for event {event_type}. Skipping.")
        return
        
    # Messages mapping based on event type
    messages = {
        "ASSIGNED": {
            "title": "Driver Assigned",
            "body": f"Your order #{order_id} has been assigned to a driver and is on the way."
        },
        "PICKED_UP": {
            "title": "Order Picked Up",
            "body": f"The driver has picked up your order #{order_id} from the merchant."
        },
        "NEAR_DELIVERY": {
            "title": "Driver Arriving Soon",
            "body": f"Your driver is less than 500m away with order #{order_id}!"
        },
        "DELIVERED": {
            "title": "Order Delivered",
            "body": f"Order #{order_id} has been successfully delivered. Thank you!"
        }
    }
    
    msg_content = messages.get(event_type, {"title": "Update", "body": f"Status update for order #{order_id}"})
    
    for channel in enabled_channels:
        # 2. Redis Idempotency Check (Protecting against duplicate events on same order/status)
        idempotency_key = f"sent:order:{order_id}:{event_type}:{channel}"
        
        # Try to set key in redis with a 1-day TTL
        is_duplicate = not run_async(redis_client.set(idempotency_key, "1", nx=True, ex=86400))
        if is_duplicate:
            logger.warning(f"Duplicate attempt detected for {idempotency_key}. Ignoring.")
            continue
            
        try:
            # 3. Deliver to appropriate channel
            if channel == "WEBSOCKET":
                # WebSocket sends work by publishing to the Redis channel
                pub_payload = {
                    "delivery_id": order_id,
                    "event_type": event_type,
                    "title": msg_content["title"],
                    "body": msg_content["body"],
                    "status": event_type
                }
                run_async(redis_client.publish(f"delivery:{order_id}", json.dumps(pub_payload)))
                run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "SUCCESS"))
                
            elif channel == "EMAIL":
                to_email = f"customer_order_{order_id}@test.com"
                
                def _run_email():
                    success = _send_email_mock(to_email, msg_content["title"], msg_content["body"])
                    if not success:
                        raise Exception("Email delivery failed")
                    run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "SUCCESS"))
                    return True

                def _fallback_email():
                    logger.warning(f"Email provider failed or circuit OPEN. Falling back to WebSocket for Order #{order_id}.")
                    pub_payload = {
                        "delivery_id": order_id,
                        "event_type": event_type,
                        "title": f"[Fallback] {msg_content['title']}",
                        "body": msg_content["body"],
                        "status": event_type
                    }
                    run_async(redis_client.publish(f"delivery:{order_id}", json.dumps(pub_payload)))
                    run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "DEGRADED", "Fallback to WebSocket due to Provider Outage"))
                    return True

                email_circuit_breaker.call_sync(_run_email, _fallback_email)
                    
            elif channel == "PUSH":
                mock_token = f"fcm_token_tenant_{tenant_id}_order_{order_id}"
                
                def _run_push():
                    success = _send_push_mock(mock_token, msg_content["title"], msg_content["body"])
                    if not success:
                        raise Exception("Push delivery failed")
                    run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "SUCCESS"))
                    return True

                def _fallback_push():
                    logger.warning(f"Push provider failed or circuit OPEN. Falling back to WebSocket for Order #{order_id}.")
                    pub_payload = {
                        "delivery_id": order_id,
                        "event_type": event_type,
                        "title": f"[Fallback] {msg_content['title']}",
                        "body": msg_content["body"],
                        "status": event_type
                    }
                    run_async(redis_client.publish(f"delivery:{order_id}", json.dumps(pub_payload)))
                    run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "DEGRADED", "Fallback to WebSocket due to Provider Outage"))
                    return True

                push_circuit_breaker.call_sync(_run_push, _fallback_push)
                    
        except Exception as err:
            logger.error(f"Failed delivering notification via {channel}: {err}")
            
            # Log failure to DB
            run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "FAILED", str(err)))
            
            # Handle retry/DLQ threshold checks
            if self.request.retries >= self.max_retries:
                # Max retries reached, move to Dead Letter Queue list in Redis
                dlq_payload = {
                    "event_id": event_id,
                    "event_type": event_type,
                    "order_id": order_id,
                    "tenant_id": tenant_id,
                    "channel": channel,
                    "error": str(err),
                    "retries": self.request.retries
                }
                run_async(redis_client.lpush("notifications:dlq", json.dumps(dlq_payload)))
                logger.error(f"Notification {event_id} on {channel} moved to Dead Letter Queue (notifications:dlq)")
            else:
                # Log RETRY state and re-raise to let Celery retry
                run_async(_db_log_notification(event_id, order_id, tenant_id, channel, event_type, "RETRY", str(err)))
                raise err
